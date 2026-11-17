import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

from app.core.db import engine
from app.models import Document, DocumentKind, DocumentStatus, get_datetime_utc
from app.services.extraction import ExtractedInvoice
from app.services.processing import (
    INTERRUPTED,
    expire_stale,
    process_invoice,
    to_amount,
    to_date,
)
from tests.utils.invoice import (
    EDF,
    PDF_BYTES,
    FakeExtractor,
    FakeReader,
    create_random_invoice,
)


def reload(db: Session, invoice: Document) -> Document:
    db.expire_all()
    fresh = db.get(Document, invoice.id)
    assert fresh is not None
    return fresh


def test_to_amount_rounds_to_cents() -> None:
    assert to_amount(84.2) == Decimal("84.20")
    assert to_amount(None) is None


def test_to_date_ignores_bad_values() -> None:
    assert to_date("2026-03-04") == date(2026, 3, 4)
    assert to_date("04/03/2026") is None
    assert to_date(None) is None


def test_process_fills_fields(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(invoice.id, engine, FakeReader(), FakeExtractor())
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.ok
    assert invoice.supplier == "EDF"
    assert invoice.document_date == date(2026, 3, 4)
    assert invoice.amount_incl_tax == Decimal("84.20")
    assert invoice.currency == "EUR"
    assert invoice.processed_at is not None


def test_pdf_and_text_are_sent_to_the_ai(db: Session) -> None:
    invoice = create_random_invoice(db)
    extractor = FakeExtractor()
    process_invoice(invoice.id, engine, FakeReader(text="EDF 84,20"), extractor)
    assert extractor.calls == [("EDF 84,20", PDF_BYTES)]


def test_ocr_failure_still_sends_the_pdf(db: Session) -> None:
    invoice = create_random_invoice(db)
    extractor = FakeExtractor()
    process_invoice(invoice.id, engine, FakeReader(error=True), extractor)
    assert extractor.calls == [("", PDF_BYTES)]
    assert reload(db, invoice).status == DocumentStatus.ok


def test_nothing_found_is_unreadable(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(invoice.id, engine, FakeReader(), FakeExtractor(ExtractedInvoice()))
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.unreadable
    assert invoice.issues == ["Champ introuvable : fournisseur, date, montant TTC"]


def test_ambiguous_us_date_sends_to_review(db: Session) -> None:
    invoice = create_random_invoice(db)
    us = EDF.model_copy(
        update={
            "invoice_date_raw": "03/04/2026",
            "invoice_date": "2026-04-03",
            "currency": "USD",
        }
    )
    process_invoice(invoice.id, engine, FakeReader(), FakeExtractor(us))
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.to_check
    assert invoice.issues == [
        "Date « 03/04/2026 » à vérifier : jour et mois peuvent être inversés"
    ]


def test_ai_error_is_kept(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(
        invoice.id, engine, FakeReader(), FakeExtractor(error="quota dépassé")
    )
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.failed
    assert invoice.issues == ["quota dépassé"]


def test_duplicate_for_same_owner(db: Session) -> None:
    first = create_random_invoice(db)
    process_invoice(first.id, engine, FakeReader(), FakeExtractor())
    second = Document(
        kind=DocumentKind.invoice,
        filename="copie.pdf",
        file=b"%PDF",
        owner_id=first.owner_id,
    )
    db.add(second)
    db.commit()
    same_supplier = EDF.model_copy(update={"supplier": "edf"})
    process_invoice(second.id, engine, FakeReader(), FakeExtractor(same_supplier))
    second = reload(db, second)
    assert second.status == DocumentStatus.to_check
    assert second.issues == ["Doublon possible de « facture.pdf »"]


def test_missing_invoice_is_ignored() -> None:
    process_invoice(uuid.uuid4(), engine, FakeReader(), FakeExtractor())


def test_stuck_invoice_becomes_retryable(db: Session) -> None:
    invoice = create_random_invoice(db, status=DocumentStatus.processing)
    invoice.started_at = get_datetime_utc() - timedelta(minutes=11)
    recent = create_random_invoice(db, status=DocumentStatus.processing)
    recent.started_at = get_datetime_utc()
    db.add_all([invoice, recent])
    db.commit()
    expire_stale(db)
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.failed
    assert invoice.issues == [INTERRUPTED]
    assert reload(db, recent).status == DocumentStatus.processing


def test_processing_records_its_start(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(invoice.id, engine, FakeReader(), FakeExtractor())
    assert reload(db, invoice).started_at is not None


def test_credit_note_amounts_become_negative(db: Session) -> None:
    invoice = create_random_invoice(db)
    credit = EDF.model_copy(update={"is_credit_note": True, "invoice_number": "AV-1"})
    process_invoice(invoice.id, engine, FakeReader(), FakeExtractor(credit))
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.ok
    assert invoice.amount_incl_tax == Decimal("-84.20")
    assert invoice.vat_amount == Decimal("-14.03")
