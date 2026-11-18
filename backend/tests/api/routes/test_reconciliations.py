from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_extractor, get_pdf_reader
from app.core.config import settings
from app.main import app
from app.services.extraction import ExtractedDocument
from tests.utils.invoice import (
    PDF_BYTES,
    FakeExtractor,
    FakeReader,
    purchase_documents,
)

DOCUMENTS = f"{settings.API_V1_STR}/documents/"
URL = f"{settings.API_V1_STR}/reconciliations/"


@pytest.fixture(autouse=True)
def fake_ai() -> Generator[None]:
    app.dependency_overrides[get_pdf_reader] = FakeReader
    yield
    app.dependency_overrides.clear()


def deposit(
    client: TestClient, headers: dict[str, str], *documents: ExtractedDocument
) -> None:
    for document in documents:
        app.dependency_overrides[get_extractor] = lambda d=document: FakeExtractor(d)
        r = client.post(
            DOCUMENTS,
            headers=headers,
            files=[("files", ("doc.pdf", PDF_BYTES, "application/pdf"))],
        )
        assert r.status_code == 200, r.text


def find(client: TestClient, headers: dict[str, str], key: str) -> dict[str, Any]:
    r = client.get(f"{URL}{key}", headers=headers)
    assert r.status_code == 200, r.text
    purchase: dict[str, Any] = r.json()
    return purchase


def test_complete_purchase_is_ready_to_pay(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("API-1"))
    purchase = find(client, normal_user_token_headers, "API1")
    assert purchase["status"] == "to_pay"
    assert purchase["order_reference"] == "API-1"
    assert len(purchase["orders"]) == 1
    assert len(purchase["deliveries"]) == 1
    assert len(purchase["invoices"]) == 1
    assert len(purchase["lines"]) == 2


def test_overbilling_is_a_dispute(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    order, delivery, invoice = purchase_documents("API-2")
    short_cable = delivery.lines[0].model_copy(update={"quantity": 45})
    short = delivery.model_copy(update={"lines": [short_cable, delivery.lines[1]]})
    deposit(client, normal_user_token_headers, order, short, invoice)
    purchase = find(client, normal_user_token_headers, "API2")
    assert purchase["status"] == "dispute"
    assert purchase["lines"][0]["issues"] == [
        "Câble R2V 3G2,5 couronne 100 m : facturé 50, livré 45"
    ]
    assert purchase["gap_excl_tax"] == "5.95"


def test_filter_by_status(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    order, _, _ = purchase_documents("API-3")
    deposit(client, normal_user_token_headers, order)
    r = client.get(URL, headers=normal_user_token_headers, params={"status": "waiting"})
    assert {p["status"] for p in r.json()["data"]} == {"waiting"}
    assert "API3" in [p["key"] for p in r.json()["data"]]


def test_delivery_without_order_number_is_listed_to_link(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    _, delivery, _ = purchase_documents("API-4")
    lost = delivery.model_copy(update={"order_reference": None, "number": "BL-LOST"})
    deposit(client, normal_user_token_headers, lost)
    r = client.get(URL, headers=normal_user_token_headers)
    assert "BL-LOST" in [ref["number"] for ref in r.json()["unlinked"]]


def test_unknown_purchase_is_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{URL}NOPE", headers=normal_user_token_headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Achat introuvable"


def test_purchases_of_other_users_stay_private(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("API-5"))
    r = client.get(f"{URL}API5", headers=superuser_token_headers)
    assert r.status_code == 404


def test_needs_login(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def deposit_dispute(
    client: TestClient, headers: dict[str, str], number: str
) -> tuple[ExtractedDocument, ExtractedDocument, ExtractedDocument]:
    order, delivery, invoice = purchase_documents(number)
    short_cable = delivery.lines[0].model_copy(update={"quantity": 45})
    short = delivery.model_copy(update={"lines": [short_cable, delivery.lines[1]]})
    deposit(client, headers, order, short, invoice)
    return order, short, invoice


def test_email_to_supplier_lists_the_gaps(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit_dispute(client, normal_user_token_headers, "API-6")
    r = client.get(f"{URL}API6/email", headers=normal_user_token_headers)
    assert r.status_code == 200, r.text
    email = r.json()
    assert email["subject"] == "Commande API-6 : écarts sur votre facture n° FA-API-6"
    body = email["body"]
    assert "votre facture n° FA-API-6 du 06/10/2026" in body
    assert "- Câble R2V 3G2,5 couronne 100 m : facturé 50, livré 45" in body
    assert "facturé en trop s'élève à 5,95 € HT" in body
    assert "avoir" in body


def test_no_email_when_everything_matches(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("API-7"))
    r = client.get(f"{URL}API7/email", headers=normal_user_token_headers)
    assert r.status_code == 400


def test_settled_dispute_can_be_paid_and_reopened(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit_dispute(client, normal_user_token_headers, "API-8")
    r = client.post(f"{URL}API8/settle", headers=normal_user_token_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "to_pay"
    assert r.json()["settled_at"]
    # The gaps stay visible, as a record of what was settled.
    assert r.json()["lines"][0]["issues"]

    r = client.get(URL, headers=normal_user_token_headers, params={"status": "dispute"})
    assert "API8" not in [p["key"] for p in r.json()["data"]]

    r = client.delete(f"{URL}API8/settle", headers=normal_user_token_headers)
    assert r.json()["status"] == "dispute"
    assert r.json()["settled_at"] is None


def test_new_gap_reopens_a_settled_dispute(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    order, _, invoice = deposit_dispute(client, normal_user_token_headers, "API-9")
    client.post(f"{URL}API9/settle", headers=normal_user_token_headers)
    again = invoice.model_copy(update={"number": "FA-API-9-BIS"})
    deposit(client, normal_user_token_headers, again)
    purchase = find(client, normal_user_token_headers, "API9")
    assert purchase["status"] == "dispute"
    assert purchase["settled_at"] is None


def test_only_disputes_can_be_settled(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("API-10"))
    r = client.post(f"{URL}API10/settle", headers=normal_user_token_headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "Cet achat n'est pas en litige"


def test_settlements_of_other_users_stay_private(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    deposit_dispute(client, normal_user_token_headers, "API-11")
    r = client.post(f"{URL}API11/settle", headers=superuser_token_headers)
    assert r.status_code == 404
    assert find(client, normal_user_token_headers, "API11")["status"] == "dispute"


def test_paid_purchase_leaves_the_purchases_to_pay(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("API-12"))
    purchase = find(client, normal_user_token_headers, "API12")
    assert purchase["to_pay_incl_tax"] == "121.80"
    assert purchase["due_date"] == "2026-11-05"
    assert purchase["due_date_assumed"] is True

    r = client.post(f"{URL}API12/pay", headers=normal_user_token_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"
    assert r.json()["paid_at"]
    assert r.json()["to_pay_incl_tax"] == "0"

    r = client.delete(f"{URL}API12/pay", headers=normal_user_token_headers)
    assert r.json()["status"] == "to_pay"
    assert r.json()["paid_at"] is None


def test_a_dispute_cannot_be_marked_paid(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit_dispute(client, normal_user_token_headers, "API-13")
    r = client.post(f"{URL}API13/pay", headers=normal_user_token_headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "Cet achat n'est pas encore bon à payer"


def test_payments_of_other_users_stay_private(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("API-14"))
    r = client.post(f"{URL}API14/pay", headers=superuser_token_headers)
    assert r.status_code == 404
    assert find(client, normal_user_token_headers, "API14")["status"] == "to_pay"


def test_due_date_read_from_the_terms(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    order, delivery, invoice = purchase_documents("API-15")
    terms = invoice.model_copy(update={"payment_terms": "45 jours fin de mois"})
    deposit(client, normal_user_token_headers, order, delivery, terms)
    purchase = find(client, normal_user_token_headers, "API15")
    # 06/10 + 45 days = 20/11, then the end of that month.
    assert purchase["due_date"] == "2026-11-30"
    assert purchase["due_date_assumed"] is False


def test_reminder_for_a_late_delivery(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    order, _, _ = purchase_documents("API-16")
    # Another supplier: an unlinked Rexel delivery note from another test
    # would rightly be offered as the missing delivery.
    promised = order.model_copy(
        update={"expected_delivery_date": "2026-10-04", "supplier": "Point P"}
    )
    deposit(client, normal_user_token_headers, promised)
    assert find(client, normal_user_token_headers, "API16")["late"] is True
    r = client.get(f"{URL}API16/email", headers=normal_user_token_headers)
    assert r.status_code == 200, r.text
    email = r.json()
    assert email["subject"] == "Commande API-16 : livraison pas encore reçue"
    assert "dont la livraison était prévue le 04/10/2026" in email["body"]


def test_changed_iban_holds_the_payment(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    _, _, invoice = purchase_documents("API-17")
    usual = invoice.model_copy(
        update={
            "order_reference": None,
            "supplier": "Loueur Iban Test",
            "number": "LIT-1",
            "date": "2026-10-01",
            "iban": "FR76 3000 6000 0112 3456 7890 189",
            "supplier_email": "compta@loueur.example",
        }
    )
    changed = usual.model_copy(
        update={
            "number": "LIT-2",
            "date": "2026-11-01",
            "iban": "FR7699999000120000000000241",
        }
    )
    deposit(client, normal_user_token_headers, usual, changed)
    r = client.get(URL, headers=normal_user_token_headers)
    by_number = {p["order_reference"]: p for p in r.json()["data"]}
    assert by_number["LIT-1"]["status"] == "to_pay"
    assert by_number["LIT-1"]["iban"] == "FR7630006000011234567890189"
    assert by_number["LIT-2"]["status"] == "waiting"
    assert by_number["LIT-2"]["iban_warning"].startswith("Nouvel IBAN")
    assert by_number["LIT-2"]["notes"] == [
        "Facture seule : rien à comparer, elle est vérifiée seule"
    ]

    # The supplier was called: the new IBAN is good.
    invoice_id = by_number["LIT-2"]["iban_document_id"]
    r = client.post(
        f"{DOCUMENTS}{invoice_id}/confirm-iban", headers=normal_user_token_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
    r = client.get(URL, headers=normal_user_token_headers)
    by_number = {p["order_reference"]: p for p in r.json()["data"]}
    assert by_number["LIT-2"]["status"] == "to_pay"
    assert by_number["LIT-2"]["iban_warning"] is None

    key = by_number["LIT-1"]["key"]
    deposit_dispute(client, normal_user_token_headers, "API-18")
    email = client.get(f"{URL}API18/email", headers=normal_user_token_headers).json()
    assert email["to"] is None
    assert key.startswith("FACTURE-")
