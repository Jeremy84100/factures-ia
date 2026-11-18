import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import get_extractor
from app.core.config import settings
from app.main import app
from app.services.extraction import ExtractedDocument
from tests.utils.invoice import EDF, ORDER, PDF_BYTES, FakeExtractor
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email

DOCUMENTS = f"{settings.API_V1_STR}/documents/"
SUPPLIERS = f"{settings.API_V1_STR}/suppliers/"
IBAN = "FR7630006000011234567890189"
OTHER_IBAN = "FR7630004000031234567890143"


@pytest.fixture(autouse=True)
def fake_ai() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def headers(client: TestClient, db: Session) -> dict[str, str]:
    """A user of its own: what one test teaches the app stays there."""
    return authentication_token_from_email(client=client, email=random_email(), db=db)


def deposit(
    client: TestClient, headers: dict[str, str], document: ExtractedDocument
) -> dict[str, Any]:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(document)
    r = client.post(
        DOCUMENTS,
        headers=headers,
        files=[("files", ("doc.pdf", PDF_BYTES, "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    r = client.get(f"{DOCUMENTS}{r.json()['data'][0]['id']}", headers=headers)
    read: dict[str, Any] = r.json()
    return read


def correct(
    client: TestClient, headers: dict[str, str], id: str, **changes: Any
) -> dict[str, Any]:
    r = client.put(f"{DOCUMENTS}{id}", headers=headers, json=changes)
    assert r.status_code == 200, r.text
    corrected: dict[str, Any] = r.json()
    return corrected


def supplier_of(
    client: TestClient, headers: dict[str, str], document: dict[str, Any]
) -> dict[str, Any]:
    r = client.get(f"{SUPPLIERS}{document['supplier_id']}", headers=headers)
    assert r.status_code == 200, r.text
    supplier: dict[str, Any] = r.json()
    return supplier


def test_suppliers_are_listed_with_their_documents(
    client: TestClient, headers: dict[str, str]
) -> None:
    deposit(client, headers, EDF)
    deposit(
        client, headers, EDF.model_copy(update={"supplier": "E.D.F. SA", "number": "2"})
    )
    deposit(client, headers, ORDER)
    r = client.get(SUPPLIERS, headers=headers)
    assert r.status_code == 200
    names = {s["name"]: s for s in r.json()["data"]}
    assert set(names) == {"EDF", "Rexel"}
    assert names["EDF"]["documents"] == 2
    assert names["EDF"]["invoiced_incl_tax"] == "168.40"


def test_a_delivery_method_once_corrected_is_understood(
    client: TestClient, headers: dict[str, str]
) -> None:
    misread = ORDER.model_copy(
        update={"delivery_method": "Livraison dépôt", "delivery_mode": "retrait"}
    )
    first = deposit(client, headers, misread)
    assert first["delivery_mode"] == "pickup"
    corrected = correct(client, headers, first["id"], delivery_mode="standard")
    assert corrected["learned"] == [
        "Chez Rexel, « Livraison dépôt » veut dire livraison standard"
    ]
    second = deposit(client, headers, misread.model_copy(update={"number": "CMD-2"}))
    assert second["delivery_mode"] == "standard"
    rules = supplier_of(client, headers, second)["rules"]
    assert [r["label"] for r in rules] == [
        "« Livraison dépôt » veut dire livraison standard"
    ]


def test_a_supplier_name_once_corrected_is_filed_right(
    client: TestClient, headers: dict[str, str]
) -> None:
    deposit(
        client, headers, EDF.model_copy(update={"supplier": "Électricité de France"})
    )
    wrong = deposit(
        client,
        headers,
        EDF.model_copy(update={"supplier": "Imprimerie Vauclusienne", "number": "2"}),
    )
    corrected = correct(client, headers, wrong["id"], supplier="Électricité de France")
    assert corrected["learned"] == [
        "« Imprimerie Vauclusienne » sera rangé chez Électricité de France"
    ]
    again = deposit(
        client,
        headers,
        EDF.model_copy(update={"supplier": "IMPRIMERIE VAUCLUSIENNE", "number": "3"}),
    )
    assert again["supplier"] == "Électricité de France"
    assert again["supplier_id"] == corrected["supplier_id"]


def test_a_date_once_corrected_tells_how_the_supplier_writes_dates(
    client: TestClient, headers: dict[str, str]
) -> None:
    misread = EDF.model_copy(
        update={
            "supplier": "Fournisseur sans pays",
            "date_raw": "08/01/2026",
            "date": "2026-08-01",
        }
    )
    first = deposit(client, headers, misread)
    corrected = correct(client, headers, first["id"], document_date="2026-01-08")
    assert corrected["learned"] == [
        "Fournisseur sans pays écrit les dates en jour/mois (08/01 = 8 janvier)"
    ]
    second = deposit(
        client,
        headers,
        misread.model_copy(
            update={"number": "2", "date_raw": "09/02/2026", "date": "2026-09-02"}
        ),
    )
    assert second["document_date"] == "2026-02-09"
    assert supplier_of(client, headers, second)["date_order"] == "day_first"


def test_payment_terms_once_given_fill_the_next_invoices(
    client: TestClient, headers: dict[str, str]
) -> None:
    first = deposit(client, headers, EDF)
    corrected = correct(
        client, headers, first["id"], payment_terms="45 jours fin de mois"
    )
    assert (
        "Conditions de paiement de EDF : 45 jours fin de mois" in corrected["learned"]
    )
    second = deposit(client, headers, EDF.model_copy(update={"number": "2"}))
    assert second["payment_terms"] == "45 jours fin de mois"
    assert second["due_date"] == "2026-04-30"


def test_a_confirmed_iban_is_kept_on_the_supplier(
    client: TestClient, headers: dict[str, str]
) -> None:
    deposit(client, headers, EDF.model_copy(update={"iban": OTHER_IBAN}))
    new = deposit(
        client,
        headers,
        EDF.model_copy(update={"number": "2", "date": "2026-04-04", "iban": IBAN}),
    )
    assert any(issue.startswith("Nouvel IBAN") for issue in new["issues"])
    supplier = supplier_of(client, headers, new)
    assert supplier["iban"] == OTHER_IBAN
    # The page shows the new account as not confirmed yet.
    assert supplier["other_ibans"] == [
        {"iban": IBAN, "last_seen": "2026-04-04", "number": "2", "newer": True}
    ]
    r = client.post(f"{DOCUMENTS}{new['id']}/confirm-iban", headers=headers)
    assert r.status_code == 200
    supplier = supplier_of(client, headers, new)
    assert supplier["iban"] == IBAN
    assert supplier["iban_confirmed_at"] is not None
    # Once confirmed, the old account is history.
    [old] = supplier["other_ibans"]
    assert old["iban"] == OTHER_IBAN
    assert old["newer"] is False


def test_editing_a_supplier_updates_its_documents(
    client: TestClient, headers: dict[str, str]
) -> None:
    document = deposit(
        client,
        headers,
        EDF.model_copy(
            update={"supplier": "ACME", "date_raw": "08/01/2026", "date": "2026-08-01"}
        ),
    )
    url = f"{SUPPLIERS}{document['supplier_id']}"
    r = client.put(
        url,
        headers=headers,
        json={"name": "Acme Industrie", "country": "fr", "payment_terms": " 30 jours "},
    )
    assert r.status_code == 200, r.text
    supplier = r.json()
    assert supplier["name"] == "Acme Industrie"
    assert supplier["country"] == "FR"
    assert supplier["payment_terms"] == "30 jours"
    assert [rule["label"] for rule in supplier["rules"]] == [
        "Un nom lu « ACME » est rangé chez Acme Industrie"
    ]
    document = client.get(f"{DOCUMENTS}{document['id']}", headers=headers).json()
    assert document["supplier"] == "Acme Industrie"
    # France writes day first: the date was read again.
    assert document["document_date"] == "2026-01-08"


def test_supplier_checks(client: TestClient, headers: dict[str, str]) -> None:
    document = deposit(client, headers, EDF)
    deposit(client, headers, ORDER)
    url = f"{SUPPLIERS}{document['supplier_id']}"
    assert (
        client.put(url, headers=headers, json={"iban": "FR76 1234"}).status_code == 400
    )
    assert (
        client.put(url, headers=headers, json={"country": "France"}).status_code == 400
    )
    assert (
        client.put(url, headers=headers, json={"email": "pas un mail"}).status_code
        == 400
    )
    assert client.put(url, headers=headers, json={"name": "REXEL"}).status_code == 409
    r = client.put(url, headers=headers, json={"iban": IBAN})
    assert r.json()["iban"] == IBAN
    assert r.json()["iban_confirmed_at"] is not None


def test_a_learned_rule_can_be_forgotten(
    client: TestClient, headers: dict[str, str]
) -> None:
    misread = ORDER.model_copy(
        update={"delivery_method": "Enlèvement chantier", "delivery_mode": "retrait"}
    )
    first = deposit(client, headers, misread)
    correct(client, headers, first["id"], delivery_mode="standard")
    rule = supplier_of(client, headers, first)["rules"][0]
    r = client.delete(
        f"{SUPPLIERS}{first['supplier_id']}/rules/{rule['id']}", headers=headers
    )
    assert r.status_code == 200
    second = deposit(client, headers, misread.model_copy(update={"number": "CMD-3"}))
    assert second["delivery_mode"] == "pickup"


def test_suppliers_are_private(
    client: TestClient,
    headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    document = deposit(client, headers, EDF)
    url = f"{SUPPLIERS}{document['supplier_id']}"
    assert client.get(url, headers=normal_user_token_headers).status_code == 404
    r = client.put(url, headers=normal_user_token_headers, json={"name": "X"})
    assert r.status_code == 404
    assert client.get(f"{SUPPLIERS}{uuid.uuid4()}", headers=headers).status_code == 404


def test_documents_read_before_suppliers_existed_are_filed(
    client: TestClient, headers: dict[str, str], db: Session
) -> None:
    from app.models import Document, DocumentKind, DocumentStatus

    me = client.get(f"{settings.API_V1_STR}/users/me", headers=headers).json()
    old = Document(
        owner_id=uuid.UUID(me["id"]),
        filename="ancien.pdf",
        file=PDF_BYTES,
        kind=DocumentKind.order,
        status=DocumentStatus.ok,
        supplier="Ancien Fournisseur",
        number="CMD-OLD",
    )
    db.add(old)
    db.commit()
    purchases = client.get(
        f"{settings.API_V1_STR}/reconciliations/", headers=headers
    ).json()["data"]
    assert purchases[0]["supplier_id"] is not None
    names = [s["name"] for s in client.get(SUPPLIERS, headers=headers).json()["data"]]
    assert names == ["Ancien Fournisseur"]


def test_the_supplier_page_is_filled_from_its_invoices(
    client: TestClient, headers: dict[str, str]
) -> None:
    first = deposit(
        client,
        headers,
        EDF.model_copy(
            update={
                "iban": OTHER_IBAN,
                "payment_terms": "30 jours fin de mois",
                "supplier_email": "factures@edf.fr",
            }
        ),
    )
    deposit(
        client,
        headers,
        EDF.model_copy(update={"number": "2", "date": "2026-04-04", "iban": IBAN}),
    )
    supplier = supplier_of(client, headers, first)
    assert supplier["email"] == "factures@edf.fr"
    assert supplier["payment_terms"] == "30 jours fin de mois"
    # The first IBAN met: the new one waits for a call.
    assert supplier["iban"] == OTHER_IBAN
    assert supplier["iban_confirmed_at"] is None
    assert supplier["country"] == "FR"
