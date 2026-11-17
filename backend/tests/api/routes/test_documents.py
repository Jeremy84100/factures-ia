from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.deps import get_extractor, get_pdf_reader
from app.core.config import settings
from app.main import app
from app.models import DocumentLine, DocumentStatus
from app.services.extraction import ExtractedDocument
from tests.utils.invoice import (
    EDF,
    ORDER,
    PDF_BYTES,
    FakeExtractor,
    FakeReader,
    create_random_invoice,
)

URL = f"{settings.API_V1_STR}/documents/"


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
    invoice = create_random_invoice(db, status=DocumentStatus.unreadable)
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
        EDF.model_copy(update={"amount_incl_tax": 842.0, "number": "CORR-1"})
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
    invoice = create_random_invoice(db, status=DocumentStatus.processing)
    r = client.put(
        f"{URL}{invoice.id}", headers=superuser_token_headers, json={"supplier": "X"}
    )
    assert r.status_code == 409


def test_retry_blocked_while_processing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    invoice = create_random_invoice(db, status=DocumentStatus.processing)
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
        EDF.model_copy(update={"supplier": "Totaux SARL", "number": None})
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


def test_delete_all_removes_only_my_documents(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    client.delete(URL, headers=normal_user_token_headers)
    mine = upload(
        client, normal_user_token_headers, ("a.pdf", PDF_BYTES), ("b.pdf", PDF_BYTES)
    )
    theirs = upload(client, superuser_token_headers, ("c.pdf", PDF_BYTES))

    response = client.delete(URL, headers=normal_user_token_headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Documents supprimés : 2"}
    for document in mine:
        url = f"{URL}{document['id']}"
        assert client.get(url, headers=normal_user_token_headers).status_code == 404
    url = f"{URL}{theirs[0]['id']}"
    assert client.get(url, headers=superuser_token_headers).status_code == 200


def test_delete_all_by_an_admin_keeps_other_users_documents(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    theirs = upload(client, normal_user_token_headers, ("a.pdf", PDF_BYTES))
    assert client.delete(URL, headers=superuser_token_headers).status_code == 200
    url = f"{URL}{theirs[0]['id']}"
    assert client.get(url, headers=normal_user_token_headers).status_code == 200


def test_delete_all_also_removes_lines(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(ORDER)
    order = upload(client, normal_user_token_headers, ("cmd.pdf", PDF_BYTES))[0]
    lines = select(DocumentLine).where(DocumentLine.document_id == order["id"])
    assert db.exec(lines).all()
    client.delete(URL, headers=normal_user_token_headers)
    db.expire_all()
    assert db.exec(lines).all() == []


def test_deleting_the_original_clears_only_its_duplicates(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    def extractor_for(number: str) -> FakeExtractor:
        return FakeExtractor(EDF.model_copy(update={"number": number}))

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


def test_manual_credit_note_is_signed(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    invoice = create_random_invoice(db, status=DocumentStatus.to_check)
    r = client.put(
        f"{URL}{invoice.id}",
        headers=superuser_token_headers,
        json={
            "supplier": "Avoir SARL",
            "number": "AV-9",
            "document_date": "2026-03-04",
            "amount_excl_tax": "10.00",
            "vat_amount": "2.00",
            "amount_incl_tax": "12.00",
            "is_credit_note": True,
            "vat_exemption": None,
        },
    )
    assert r.status_code == 200
    assert r.json()["amount_incl_tax"] == "-12.00"
    assert r.json()["status"] == "ok"


def use_ai_result(result: ExtractedDocument) -> None:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(result)


def test_upload_sorts_each_document(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    use_ai_result(ORDER.model_copy(update={"number": "SORT-1"}))
    created = upload(client, normal_user_token_headers, ("commande.pdf", PDF_BYTES))
    assert created[0]["kind"] == "unknown"

    r = client.get(f"{URL}{created[0]['id']}", headers=normal_user_token_headers)
    assert r.json()["kind"] == "order"
    assert r.json()["status"] == "ok"
    references = [line["reference"] for line in r.json()["lines"]]
    assert references == ["CAB-3G25", "ICTA-20"]


def test_filter_by_kind(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    use_ai_result(ORDER.model_copy(update={"number": "KIND-1"}))
    upload(client, normal_user_token_headers, ("commande.pdf", PDF_BYTES))
    r = client.get(URL, headers=normal_user_token_headers, params={"kind": "order"})
    assert {item["kind"] for item in r.json()["data"]} == {"order"}


def test_kind_and_order_number_can_be_corrected(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    use_ai_result(
        ORDER.model_copy(update={"document_type": "autre", "number": "BL-77"})
    )
    created = upload(client, normal_user_token_headers, ("scan.pdf", PDF_BYTES))
    url = f"{URL}{created[0]['id']}"
    r = client.get(url, headers=normal_user_token_headers)
    assert r.json()["status"] == "unreadable"

    r = client.put(url, headers=normal_user_token_headers, json={"kind": "delivery"})
    assert r.json()["kind"] == "delivery"
    assert r.json()["issues"] == [
        "Numéro de commande introuvable : à relier à une commande"
    ]

    r = client.put(
        url, headers=normal_user_token_headers, json={"order_reference": "CMD-77"}
    )
    assert r.json()["status"] == "ok"


def test_lines_can_be_corrected(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    use_ai_result(
        ORDER.model_copy(update={"number": "LINES-1", "amount_excl_tax": 120.0})
    )
    created = upload(client, normal_user_token_headers, ("commande.pdf", PDF_BYTES))
    url = f"{URL}{created[0]['id']}"
    r = client.get(url, headers=normal_user_token_headers)
    assert r.json()["status"] == "to_check"

    def line(reference: str, quantity: str, price: str, amount: str) -> dict[str, str]:
        return {
            "reference": reference,
            "quantity": quantity,
            "unit_price": price,
            "amount_excl_tax": amount,
        }

    lines = [
        line("CAB-3G25", "50", "1.19", "59.50"),
        line("ICTA-20", "100", "0.42", "42.00"),
        line("PORT", "1", "18.50", "18.50"),
    ]
    r = client.put(url, headers=normal_user_token_headers, json={"lines": lines})
    assert r.json()["status"] == "ok"
    assert len(r.json()["lines"]) == 3


def test_totals_count_only_invoices(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    use_ai_result(
        ORDER.model_copy(
            update={
                "number": "TOT-1",
                "supplier": "Commande Seule SARL",
                "amount_incl_tax": 121.80,
            }
        )
    )
    upload(client, normal_user_token_headers, ("commande.pdf", PDF_BYTES))
    r = client.get(f"{URL}totals", headers=normal_user_token_headers)
    suppliers = {row["supplier"] for row in r.json()["data"]}
    assert "Commande Seule SARL" not in suppliers


def test_delivery_details_can_be_corrected(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    use_ai_result(ORDER.model_copy(update={"number": "LIV-1"}))
    order = upload(client, normal_user_token_headers, ("commande.pdf", PDF_BYTES))[0]
    url = f"{URL}{order['id']}"
    r = client.put(
        url,
        headers=normal_user_token_headers,
        json={
            "delivery_method": "Express 24 h",
            "delivery_mode": "express",
            "expected_delivery_date": "2026-09-30",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["delivery_mode"] == "express"
    assert data["expected_delivery_date"] == "2026-09-30"
    assert data["issues"] == ["Date de livraison promise avant la date du document"]

    r = client.put(
        url, headers=normal_user_token_headers, json={"delivery_mode": "avion"}
    )
    assert r.status_code == 422


def photo(fmt: str = "JPEG") -> bytes:
    from io import BytesIO

    from PIL import Image

    out = BytesIO()
    Image.new("RGB", (60, 90), "white").save(out, format=fmt)
    return out.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_phone_photo_becomes_a_pdf(
    client: TestClient, normal_user_token_headers: dict[str, str], fmt: str
) -> None:
    created = upload(
        client, normal_user_token_headers, ("bon-livraison.jpg", photo(fmt))
    )
    assert created[0]["filename"] == "bon-livraison.pdf"
    r = client.get(f"{URL}{created[0]['id']}/file", headers=normal_user_token_headers)
    assert r.content.startswith(b"%PDF")


def test_broken_photo_is_refused(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        URL,
        headers=normal_user_token_headers,
        files=[("files", ("photo.jpg", b"\xff\xd8\xff" + b"0" * 50, "image/jpeg"))],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "photo.jpg : photo illisible"


def test_other_files_are_refused(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        URL,
        headers=normal_user_token_headers,
        files=[("files", ("note.txt", b"bonjour", "text/plain"))],
    )
    assert r.status_code == 400
    assert "ni un PDF ni une photo" in r.json()["detail"]
