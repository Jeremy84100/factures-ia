import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

from app.core.db import engine
from app.models import Document, DocumentKind, DocumentStatus, get_datetime_utc
from app.services.extraction import ExtractedDocument, ExtractedLine
from app.services.processing import (
    INTERRUPTED,
    expire_stale,
    process_document,
    to_amount,
    to_date,
)
from tests.utils.invoice import (
    CABLE,
    EDF,
    ORDER,
    PDF_BYTES,
    FakeExtractor,
    FakeReader,
    create_random_document,
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
    process_document(invoice.id, engine, FakeReader(), FakeExtractor())
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
    process_document(invoice.id, engine, FakeReader(text="EDF 84,20"), extractor)
    assert extractor.calls == [("EDF 84,20", PDF_BYTES)]


def test_ocr_failure_still_sends_the_pdf(db: Session) -> None:
    invoice = create_random_invoice(db)
    extractor = FakeExtractor()
    process_document(invoice.id, engine, FakeReader(error=True), extractor)
    assert extractor.calls == [("", PDF_BYTES)]
    assert reload(db, invoice).status == DocumentStatus.ok


def test_nothing_found_is_unreadable(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_document(
        invoice.id, engine, FakeReader(), FakeExtractor(ExtractedDocument())
    )
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.unreadable
    assert invoice.issues == ["Champ introuvable : fournisseur, date, montant TTC"]


def test_ambiguous_us_date_sends_to_review(db: Session) -> None:
    invoice = create_random_invoice(db)
    us = EDF.model_copy(
        update={
            "date_raw": "03/04/2026",
            "date": "2026-04-03",
            "currency": "USD",
        }
    )
    process_document(invoice.id, engine, FakeReader(), FakeExtractor(us))
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.to_check
    assert invoice.issues == [
        "Date « 03/04/2026 » à vérifier : jour et mois peuvent être inversés"
    ]


def test_ai_error_is_kept(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_document(
        invoice.id, engine, FakeReader(), FakeExtractor(error="quota dépassé")
    )
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.failed
    assert invoice.issues == ["quota dépassé"]


def test_duplicate_for_same_owner(db: Session) -> None:
    first = create_random_invoice(db)
    process_document(first.id, engine, FakeReader(), FakeExtractor())
    second = Document(
        kind=DocumentKind.invoice,
        filename="copie.pdf",
        file=b"%PDF",
        owner_id=first.owner_id,
    )
    db.add(second)
    db.commit()
    same_supplier = EDF.model_copy(update={"supplier": "edf"})
    process_document(second.id, engine, FakeReader(), FakeExtractor(same_supplier))
    second = reload(db, second)
    assert second.status == DocumentStatus.to_check
    assert second.issues == ["Doublon possible de « facture.pdf »"]


class DeletingExtractor(FakeExtractor):
    """Deletes the document while the AI reads it, like « Tout supprimer »."""

    def __init__(self, document_id: uuid.UUID, error: str | None = None) -> None:
        super().__init__(error=error)
        self.document_id = document_id

    def extract(self, text: str, pdf: bytes) -> ExtractedDocument:
        with Session(engine) as other:
            document = other.get(Document, self.document_id)
            assert document is not None
            other.delete(document)
            other.commit()
        return super().extract(text, pdf)


def test_document_deleted_during_reading_is_dropped(db: Session) -> None:
    document_id = create_random_invoice(db).id
    process_document(document_id, engine, FakeReader(), DeletingExtractor(document_id))
    db.expire_all()
    assert db.get(Document, document_id) is None


def test_document_deleted_during_failed_reading_is_dropped(db: Session) -> None:
    document_id = create_random_invoice(db).id
    extractor = DeletingExtractor(document_id, error="Clé GEMINI_API_KEY manquante")
    process_document(document_id, engine, FakeReader(), extractor)
    db.expire_all()
    assert db.get(Document, document_id) is None


def test_missing_invoice_is_ignored() -> None:
    process_document(uuid.uuid4(), engine, FakeReader(), FakeExtractor())


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
    process_document(invoice.id, engine, FakeReader(), FakeExtractor())
    assert reload(db, invoice).started_at is not None


def test_credit_note_amounts_become_negative(db: Session) -> None:
    invoice = create_random_invoice(db)
    credit = EDF.model_copy(update={"is_credit_note": True, "number": "AV-1"})
    process_document(invoice.id, engine, FakeReader(), FakeExtractor(credit))
    invoice = reload(db, invoice)
    assert invoice.status == DocumentStatus.ok
    assert invoice.amount_incl_tax == Decimal("-84.20")
    assert invoice.vat_amount == Decimal("-14.03")


def test_document_type_is_recognised(db: Session) -> None:
    document = create_random_document(db)
    process_document(document.id, engine, FakeReader(), FakeExtractor(ORDER))
    assert reload(db, document).kind == DocumentKind.order


def test_unknown_type_stays_unknown(db: Session) -> None:
    document = create_random_document(db)
    other = ORDER.model_copy(update={"document_type": "autre"})
    process_document(document.id, engine, FakeReader(), FakeExtractor(other))
    assert reload(db, document).kind == DocumentKind.unknown


def test_type_chosen_by_hand_is_kept_on_retry(db: Session) -> None:
    document = create_random_document(db, kind=DocumentKind.delivery)
    process_document(document.id, engine, FakeReader(), FakeExtractor(ORDER))
    assert reload(db, document).kind == DocumentKind.delivery


def test_lines_are_stored_in_order(db: Session) -> None:
    document = create_random_document(db)
    process_document(document.id, engine, FakeReader(), FakeExtractor(ORDER))
    lines = reload(db, document).lines
    assert [line.reference for line in lines] == ["CAB-3G25", "ICTA-20"]
    assert [line.position for line in lines] == [0, 1]
    assert lines[0].quantity == Decimal("50.000")
    assert lines[0].unit_price == Decimal("1.1900")
    assert lines[0].amount_excl_tax == Decimal("59.50")


def test_empty_lines_are_dropped(db: Session) -> None:
    document = create_random_document(db)
    noisy = ORDER.model_copy(update={"lines": [ExtractedLine(), CABLE]})
    process_document(document.id, engine, FakeReader(), FakeExtractor(noisy))
    assert len(reload(db, document).lines) == 1


def test_reading_again_replaces_the_lines(db: Session) -> None:
    document = create_random_document(db)
    process_document(document.id, engine, FakeReader(), FakeExtractor(ORDER))
    process_document(document.id, engine, FakeReader(), FakeExtractor(ORDER))
    assert len(reload(db, document).lines) == 2


def test_order_reference_is_kept(db: Session) -> None:
    document = create_random_document(db)
    delivery = ORDER.model_copy(
        update={
            "document_type": "bon_de_livraison",
            "number": "BL-88",
            "order_reference": "  CMD-2041 ",
        }
    )
    process_document(document.id, engine, FakeReader(), FakeExtractor(delivery))
    assert reload(db, document).order_reference == "CMD-2041"


def test_same_number_on_another_type_is_not_a_duplicate(db: Session) -> None:
    order = create_random_document(db)
    process_document(order.id, engine, FakeReader(), FakeExtractor(ORDER))
    delivery = Document(
        filename="bl.pdf", file=b"%PDF", owner_id=reload(db, order).owner_id
    )
    db.add(delivery)
    db.commit()
    same_number = ORDER.model_copy(
        update={"document_type": "bon_de_livraison", "order_reference": "CMD-2041"}
    )
    process_document(delivery.id, engine, FakeReader(), FakeExtractor(same_number))
    assert reload(db, delivery).status == DocumentStatus.ok


def test_queued_document_is_not_expired_too_early(db: Session) -> None:
    queued = create_random_document(db)
    queued.created_at = get_datetime_utc() - timedelta(minutes=30)
    old = create_random_document(db)
    old.created_at = get_datetime_utc() - timedelta(minutes=61)
    db.add_all([queued, old])
    db.commit()
    expire_stale(db)
    assert reload(db, queued).status == DocumentStatus.pending
    assert reload(db, old).status == DocumentStatus.failed
