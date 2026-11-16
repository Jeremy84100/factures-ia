from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import get_extractor, get_pdf_reader
from app.core.config import settings
from app.main import app
from app.models import InvoiceStatus
from tests.utils.invoice import (
    EDF,
    PDF_BYTES,
    FakeExtractor,
    FakeReader,
    create_random_invoice,
)

URL = f"{settings.API_V1_STR}/invoices/"


@pytest.fixture(autouse=True)
def fake_ai() -> Generator[None]:
    app.dependency_overrides[get_pdf_reader] = FakeReader
    app.dependency_overrides[get_extractor] = FakeExtractor
    yield
    app.dependency_overrides.clear()


def upload(
    client: TestClient, headers: dict[str, str], *files: tuple[str, bytes]
) -> list[dict[str, object]]:
    r = client.post(
        URL,
        headers=headers,
        files=[("files", (name, data, "application/pdf")) for name, data in files],
    )
    assert r.status_code == 200, r.text
    data: list[dict[str, object]] = r.json()["data"]
    return data


def test_upload_reads_invoices(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = upload(
        client, normal_user_token_headers, ("a.pdf", PDF_BYTES), ("b.pdf", PDF_BYTES)
    )
    assert [invoice["status"] for invoice in created] == ["pending", "pending"]

    first = client.get(f"{URL}{created[0]['id']}", headers=normal_user_token_headers)
    assert first.json()["status"] == "ok"
    assert first.json()["supplier"] == "EDF"
    assert first.json()["amount_incl_tax"] == "84.20"

    second = client.get(f"{URL}{created[1]['id']}", headers=normal_user_token_headers)
    assert second.json()["status"] == "to_check"
    assert second.json()["issues"] == ["Doublon possible de « a.pdf »"]


def test_upload_rejects_non_pdf(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        URL,
        headers=normal_user_token_headers,
        files=[("files", ("notes.txt", b"bonjour", "text/plain"))],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "notes.txt n'est pas un PDF"


def test_upload_needs_login(client: TestClient) -> None:
    r = client.post(URL, files=[("files", ("a.pdf", PDF_BYTES, "application/pdf"))])
    assert r.status_code == 401


def test_list_only_own_invoices(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    other = create_random_invoice(db)
    upload(client, normal_user_token_headers, ("mine.pdf", PDF_BYTES))
    r = client.get(URL, headers=normal_user_token_headers)
    ids = [invoice["id"] for invoice in r.json()["data"]]
    assert str(other.id) not in ids
    assert r.json()["count"] == len(ids)


def test_filter_by_status(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    invoice = create_random_invoice(db, status=InvoiceStatus.unreadable)
    r = client.get(
        URL, headers=superuser_token_headers, params={"status": "unreadable"}
    )
    statuses = {item["status"] for item in r.json()["data"]}
    assert statuses == {"unreadable"}
    assert str(invoice.id) in [item["id"] for item in r.json()["data"]]


def test_other_user_invoice_is_forbidden(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    invoice = create_random_invoice(db)
    r = client.get(f"{URL}{invoice.id}", headers=normal_user_token_headers)
    assert r.status_code == 403


def test_download_file(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = upload(client, normal_user_token_headers, ("edf.pdf", PDF_BYTES))
    r = client.get(f"{URL}{created[0]['id']}/file", headers=normal_user_token_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == PDF_BYTES


def test_manual_correction_runs_checks(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(
        EDF.model_copy(update={"amount_incl_tax": 842.0, "invoice_number": "CORR-1"})
    )
    created = upload(client, normal_user_token_headers, ("edf.pdf", PDF_BYTES))
    url = f"{URL}{created[0]['id']}"
    assert client.get(url, headers=normal_user_token_headers).json()["status"] == (
        "to_check"
    )

    r = client.put(
        url, headers=normal_user_token_headers, json={"amount_incl_tax": "84.20"}
    )
    assert r.json()["status"] == "ok"
    assert r.json()["issues"] == []


def test_correction_blocked_while_processing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    invoice = create_random_invoice(db, status=InvoiceStatus.processing)
    r = client.put(
        f"{URL}{invoice.id}", headers=superuser_token_headers, json={"supplier": "X"}
    )
    assert r.status_code == 409


def test_retry_blocked_while_processing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    invoice = create_random_invoice(db, status=InvoiceStatus.processing)
    r = client.post(f"{URL}{invoice.id}/retry", headers=superuser_token_headers)
    assert r.status_code == 409


def test_retry_after_ai_error(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(error="quota")
    created = upload(client, normal_user_token_headers, ("edf.pdf", PDF_BYTES))
    url = f"{URL}{created[0]['id']}"
    assert client.get(url, headers=normal_user_token_headers).json()["status"] == (
        "failed"
    )

    app.dependency_overrides[get_extractor] = FakeExtractor
    client.post(f"{url}/retry", headers=normal_user_token_headers)
    assert client.get(url, headers=normal_user_token_headers).json()["status"] in (
        "ok",
        "to_check",
    )


def test_supplier_totals(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(
        EDF.model_copy(update={"supplier": "Totaux SARL", "invoice_number": None})
    )
    upload(client, superuser_token_headers, ("a.pdf", PDF_BYTES), ("b.pdf", PDF_BYTES))
    r = client.get(
        f"{URL}totals", headers=superuser_token_headers, params={"year": 2026}
    )
    row = next(item for item in r.json()["data"] if item["supplier"] == "Totaux SARL")
    assert row["count"] == 2
    assert row["total_incl_tax"] == "168.40"


def test_delete_invoice(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    created = upload(client, normal_user_token_headers, ("edf.pdf", PDF_BYTES))
    url = f"{URL}{created[0]['id']}"
    assert client.delete(url, headers=normal_user_token_headers).status_code == 200
    assert client.get(url, headers=normal_user_token_headers).status_code == 404


def test_deleting_the_original_clears_only_its_duplicates(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    def extractor_for(number: str) -> FakeExtractor:
        return FakeExtractor(EDF.model_copy(update={"invoice_number": number}))

    app.dependency_overrides[get_extractor] = lambda: extractor_for("DEL-1")
    original, copy = upload(
        client, normal_user_token_headers, ("a.pdf", PDF_BYTES), ("b.pdf", PDF_BYTES)
    )
    app.dependency_overrides[get_extractor] = lambda: extractor_for("DEL-2")
    other, other_copy = upload(
        client, normal_user_token_headers, ("c.pdf", PDF_BYTES), ("d.pdf", PDF_BYTES)
    )

    def status(invoice: dict[str, object]) -> object:
        url = f"{URL}{invoice['id']}"
        return client.get(url, headers=normal_user_token_headers).json()["status"]

    assert status(copy) == "to_check"
    client.delete(f"{URL}{original['id']}", headers=normal_user_token_headers)
    assert status(copy) == "ok"
    assert status(other_copy) == "to_check"
