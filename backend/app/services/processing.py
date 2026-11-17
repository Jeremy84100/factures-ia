import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.models import Document, DocumentStatus, get_datetime_utc
from app.services.checks import (
    NUMBER_ISSUES,
    check_invoice,
    number_issue,
    review_extraction,
)
from app.services.extraction import ExtractedInvoice, ExtractionError, InvoiceExtractor
from app.services.pdf_reader import PdfReader

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
STALE_AFTER = timedelta(minutes=10)
INTERRUPTED = "Lecture interrompue par le serveur, relancez-la"


def to_amount(value: float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(CENT)
    except InvalidOperation:
        return None


def to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def sign_credit_note(invoice: Document) -> None:
    if not invoice.is_credit_note:
        return
    for field in ("amount_excl_tax", "vat_amount", "amount_incl_tax"):
        amount = getattr(invoice, field)
        if amount is not None:
            setattr(invoice, field, -abs(amount))


def apply_extraction(invoice: Document, extracted: ExtractedInvoice) -> None:
    invoice.supplier = extracted.supplier
    invoice.number = extracted.invoice_number
    invoice.document_date = to_date(extracted.invoice_date)
    invoice.amount_excl_tax = to_amount(extracted.amount_excl_tax)
    invoice.vat_amount = to_amount(extracted.vat_amount)
    invoice.amount_incl_tax = to_amount(extracted.amount_incl_tax)
    invoice.currency = (extracted.currency or "").upper()[:3] or None
    invoice.is_credit_note = bool(extracted.is_credit_note)
    invoice.vat_exemption = (extracted.vat_exemption or "").strip()[:255] or None
    sign_credit_note(invoice)


def find_duplicate(session: Session, invoice: Document) -> Document | None:
    if not invoice.supplier or not invoice.number:
        return None
    statement = select(Document).where(
        Document.owner_id == invoice.owner_id,
        Document.id != invoice.id,
        Document.number == invoice.number,
        func.lower(col(Document.supplier)) == invoice.supplier.lower(),
    )
    matches = session.exec(statement).all()
    same_amount = [m for m in matches if m.amount_incl_tax == invoice.amount_incl_tax]
    best = same_amount or matches
    return best[0] if best else None


def expire_stale(session: Session) -> None:
    cutoff = get_datetime_utc() - STALE_AFTER
    stale = session.exec(
        select(Document).where(
            col(Document.status).in_(
                [DocumentStatus.pending, DocumentStatus.processing]
            ),
            func.coalesce(Document.started_at, Document.created_at) < cutoff,
        )
    ).all()
    for invoice in stale:
        invoice.status = DocumentStatus.failed
        invoice.issues = [INTERRUPTED]
        session.add(invoice)
    if stale:
        session.commit()


def recheck_duplicates_of(session: Session, deleted: Document) -> None:
    if not deleted.supplier or not deleted.number:
        return
    flagged = session.exec(
        select(Document).where(
            Document.owner_id == deleted.owner_id,
            Document.id != deleted.id,
            Document.status == DocumentStatus.to_check,
            Document.number == deleted.number,
            func.lower(col(Document.supplier)) == deleted.supplier.lower(),
        )
    ).all()
    for invoice in flagged:
        issues = [i for i in invoice.issues if not i.startswith(NUMBER_ISSUES)]
        if original := find_duplicate(session, invoice):
            issues.append(number_issue(invoice, original))
        invoice.issues = issues
        invoice.status = DocumentStatus.to_check if issues else DocumentStatus.ok
        session.add(invoice)


def run_checks(
    session: Session, invoice: Document, extraction_issues: list[str] | None = None
) -> None:
    status, issues = check_invoice(
        invoice, find_duplicate(session, invoice), extraction_issues=extraction_issues
    )
    invoice.status = status
    invoice.issues = issues


def _finish(
    session: Session, invoice: Document, status: DocumentStatus, issue: str
) -> None:
    invoice.status = status
    invoice.issues = [issue]
    invoice.processed_at = get_datetime_utc()
    session.add(invoice)
    session.commit()


def process_invoice(
    invoice_id: uuid.UUID,
    engine: Engine,
    reader: PdfReader,
    extractor: InvoiceExtractor,
) -> None:
    with Session(engine) as session:
        invoice = session.get(Document, invoice_id)
        if invoice is None:
            return
        invoice.status = DocumentStatus.processing
        invoice.started_at = get_datetime_utc()
        session.add(invoice)
        session.commit()

        try:
            text = reader.read(invoice.file, invoice.filename)
        except Exception:
            logger.exception("Lecture OCR impossible de %s", invoice.filename)
            text = ""

        try:
            extracted = extractor.extract(text, invoice.file)
        except ExtractionError as e:
            _finish(session, invoice, DocumentStatus.failed, str(e))
            return

        apply_extraction(invoice, extracted)
        run_checks(session, invoice, review_extraction(extracted))
        invoice.processed_at = get_datetime_utc()
        session.add(invoice)
        session.commit()
