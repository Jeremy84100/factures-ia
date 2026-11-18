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
