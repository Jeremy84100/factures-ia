import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.models import Invoice, InvoiceStatus, get_datetime_utc
from app.services.checks import DUPLICATE_OF, check_invoice, review_extraction
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


def apply_extraction(invoice: Invoice, extracted: ExtractedInvoice) -> None:
    invoice.supplier = extracted.supplier
    invoice.invoice_number = extracted.invoice_number
    invoice.invoice_date = to_date(extracted.invoice_date)
    invoice.amount_excl_tax = to_amount(extracted.amount_excl_tax)
    invoice.vat_amount = to_amount(extracted.vat_amount)
    invoice.amount_incl_tax = to_amount(extracted.amount_incl_tax)
    invoice.currency = (extracted.currency or "").upper()[:3] or None


def find_duplicate(session: Session, invoice: Invoice) -> Invoice | None:
    if not invoice.supplier or not invoice.invoice_number:
        return None
    statement = select(Invoice).where(
        Invoice.owner_id == invoice.owner_id,
        Invoice.id != invoice.id,
        Invoice.invoice_number == invoice.invoice_number,
        func.lower(col(Invoice.supplier)) == invoice.supplier.lower(),
    )
    return session.exec(statement).first()


def expire_stale(session: Session) -> None:
    cutoff = get_datetime_utc() - STALE_AFTER
    stale = session.exec(
        select(Invoice).where(
            col(Invoice.status).in_([InvoiceStatus.pending, InvoiceStatus.processing]),
            func.coalesce(Invoice.started_at, Invoice.created_at) < cutoff,
        )
    ).all()
    for invoice in stale:
        invoice.status = InvoiceStatus.failed
        invoice.issues = [INTERRUPTED]
        session.add(invoice)
    if stale:
        session.commit()


def recheck_duplicates_of(session: Session, deleted: Invoice) -> None:
    if not deleted.supplier or not deleted.invoice_number:
        return
    flagged = session.exec(
        select(Invoice).where(
            Invoice.owner_id == deleted.owner_id,
            Invoice.id != deleted.id,
            Invoice.status == InvoiceStatus.to_check,
            Invoice.invoice_number == deleted.invoice_number,
            func.lower(col(Invoice.supplier)) == deleted.supplier.lower(),
        )
    ).all()
    for invoice in flagged:
        issues = [i for i in invoice.issues if not i.startswith(DUPLICATE_OF)]
        if original := find_duplicate(session, invoice):
            issues.append(f"{DUPLICATE_OF} « {original.filename} »")
        invoice.issues = issues
        invoice.status = InvoiceStatus.to_check if issues else InvoiceStatus.ok
        session.add(invoice)


def run_checks(
    session: Session, invoice: Invoice, extraction_issues: list[str] | None = None
) -> None:
    status, issues = check_invoice(
        invoice, find_duplicate(session, invoice), extraction_issues=extraction_issues
    )
    invoice.status = status
    invoice.issues = issues


def _finish(
    session: Session, invoice: Invoice, status: InvoiceStatus, issue: str
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
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            return
        invoice.status = InvoiceStatus.processing
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
            _finish(session, invoice, InvoiceStatus.failed, str(e))
            return

        apply_extraction(invoice, extracted)
        run_checks(session, invoice, review_extraction(extracted))
        invoice.processed_at = get_datetime_utc()
        session.add(invoice)
        session.commit()
