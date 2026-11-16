import logging
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.models import Invoice, InvoiceStatus, get_datetime_utc
from app.services.checks import check_invoice
from app.services.extraction import ExtractedInvoice, ExtractionError, InvoiceExtractor
from app.services.pdf_reader import PdfReader

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


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


def run_checks(session: Session, invoice: Invoice) -> None:
    status, issues = check_invoice(invoice, find_duplicate(session, invoice))
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
        session.add(invoice)
        session.commit()

        try:
            text = reader.read(invoice.file, invoice.filename)
        except Exception:
            logger.exception("Lecture impossible de %s", invoice.filename)
            _finish(
                session, invoice, InvoiceStatus.unreadable, "Le PDF n'a pas pu être lu"
            )
            return
        if not text.strip():
            _finish(
                session,
                invoice,
                InvoiceStatus.unreadable,
                "Aucun texte trouvé dans le PDF",
            )
            return

        try:
            extracted = extractor.extract(text)
        except ExtractionError as e:
            _finish(session, invoice, InvoiceStatus.failed, str(e))
            return

        apply_extraction(invoice, extracted)
        run_checks(session, invoice)
        invoice.processed_at = get_datetime_utc()
        session.add(invoice)
        session.commit()
