import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import pypdfium2 as pdfium
from sqlalchemy import Engine, and_, func, or_
from sqlalchemy.orm import defer
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError
from sqlmodel import Session, col, select

from app.models import (
    MAX_LINES,
    DeliveryMode,
    Document,
    DocumentKind,
    DocumentLine,
    DocumentStatus,
    LineFields,
    get_datetime_utc,
)
from app.services.checks import (
    NUMBER_ISSUES,
    check_document,
    number_issue,
    review_extraction,
)
from app.services.einvoice import merge_lines, read_einvoice
from app.services.extraction import (
    DocumentExtractor,
    ExtractedDocument,
    ExtractedLine,
    ExtractionError,
)
from app.services.iban import clean_iban, iban_change
from app.services.payment_terms import due_from_terms
from app.services.suppliers import remember

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
QUANTITY_STEP = Decimal("0.001")
PRICE_STEP = Decimal("0.0001")
STALE_AFTER = timedelta(minutes=10)
QUEUED_TOO_LONG = timedelta(hours=1)
MAX_PAGES = 20
INTERRUPTED = "Lecture interrompue par le serveur, relancez-la"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A title that says credit note, in the languages of the suppliers met: a
# safety net read by code, whatever the AI said.
CREDIT_TITLE = re.compile(
    r"\b(avoirs?|note de cr[ée]dit|credit ?notes?|credit memo|gutschrift"
    r"|nota de cr[ée]dito|nota di credito|creditnota)\b",
    re.IGNORECASE,
)
# A self-billed invoice (« Gutschrift (selbst ausgestellt) », autofacturation)
# is written by the buyer but is still an invoice to pay: the AI took one,
# with a positive total, for a credit note four times out of four.
SELF_BILLED = re.compile(r"selbst|self[- ]?bill|autofactur|auto-factur", re.IGNORECASE)
# The customer's own IBAN, masked, on an invoice paid by direct debit.
MASKED_IBAN = re.compile(r"[*•]|X{4}")

KINDS = {
    "facture": DocumentKind.invoice,
    "bon_de_commande": DocumentKind.order,
    "bon_de_livraison": DocumentKind.delivery,
}
DELIVERY_MODES = {
    "retrait": DeliveryMode.pickup,
    "standard": DeliveryMode.standard,
    "express": DeliveryMode.express,
}


def to_decimal(value: float | None, step: Decimal) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(step)
    except InvalidOperation:
        return None


def to_amount(value: float | None) -> Decimal | None:
    return to_decimal(value, CENT)


def to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def to_text(value: str | None, max_length: int) -> str | None:
    return (value or "").strip()[:max_length] or None


def to_email(value: str | None) -> str | None:
    text = (value or "").strip().removeprefix("mailto:")
    return text[:255] if EMAIL.match(text) else None


def to_line(line: ExtractedLine | LineFields, position: int) -> DocumentLine:
    def number(value: float | Decimal | None, step: Decimal) -> Decimal | None:
        return to_decimal(None if value is None else float(value), step)

    return DocumentLine(
        position=position,
        reference=to_text(line.reference, 100),
        description=to_text(line.description, 255),
        quantity=number(line.quantity, QUANTITY_STEP),
        unit=to_text(line.unit, 20),
        unit_price=number(line.unit_price, PRICE_STEP),
        amount_excl_tax=number(line.amount_excl_tax, CENT),
    )


def to_lines(lines: list[ExtractedLine] | list[LineFields]) -> list[DocumentLine]:
    kept = [
        line
        for line in lines
        if line.description or line.reference or line.quantity is not None
    ][:MAX_LINES]
    return [to_line(line, position) for position, line in enumerate(kept)]


def is_credit_title(title: str | None) -> bool:
    return bool(CREDIT_TITLE.search(title or ""))


def is_credit_note(extracted: ExtractedDocument) -> bool:
    if SELF_BILLED.search(extracted.title or ""):
        totals = (extracted.amount_incl_tax, extracted.amount_excl_tax)
        return any(total is not None and total < 0 for total in totals)
    return bool(extracted.is_credit_note) or is_credit_title(extracted.title)


def to_iban(value: str | None) -> str | None:
    if value and MASKED_IBAN.search(value):
        return None
    return clean_iban(value)


def sign_credit_note(document: Document) -> None:
    if not document.is_credit_note:
        return
    for field in ("amount_excl_tax", "vat_amount", "amount_incl_tax"):
        amount = getattr(document, field)
        if amount is not None:
            setattr(document, field, -abs(amount))


def apply_extraction(document: Document, extracted: ExtractedDocument) -> None:
    if document.kind == DocumentKind.unknown:
        document.kind = KINDS.get(extracted.document_type or "", DocumentKind.unknown)
    document.supplier = to_text(extracted.supplier, 255)
    document.number = to_text(extracted.number, 100)
    document.document_date = to_date(extracted.date)
    document.date_raw = to_text(extracted.date_raw, 30)
    document.order_reference = to_text(extracted.order_reference, 100)
    document.amount_excl_tax = to_amount(extracted.amount_excl_tax)
    document.vat_amount = to_amount(extracted.vat_amount)
    document.amount_incl_tax = to_amount(extracted.amount_incl_tax)
    document.currency = (extracted.currency or "").upper()[:3] or None
    document.is_credit_note = is_credit_note(extracted)
    document.vat_exemption = to_text(extracted.vat_exemption, 255)
    document.delivery_method = to_text(extracted.delivery_method, 100)
    document.delivery_mode = DELIVERY_MODES.get(extracted.delivery_mode or "")
    document.expected_delivery_date = to_date(extracted.expected_delivery_date)
    document.payment_terms = to_text(extracted.payment_terms, 100)
    document.due_date = to_date(extracted.due_date) or due_from_terms(
        document.payment_terms, document.document_date
    )
    document.iban = to_iban(extracted.iban)
    document.iban_checked = False
    document.supplier_email = to_email(extracted.supplier_email)
    document.lines = to_lines(extracted.lines)
    sign_credit_note(document)


def find_duplicate(session: Session, document: Document) -> Document | None:
    if not document.supplier or not document.number:
        return None
    statement = (
        select(Document)
        .where(
            Document.owner_id == document.owner_id,
            Document.id != document.id,
            Document.kind == document.kind,
            Document.number == document.number,
            func.lower(col(Document.supplier)) == document.supplier.lower(),
        )
        .options(defer(Document.file))  # type: ignore[arg-type]
    )
    matches = session.exec(statement).all()
    same_amount = [m for m in matches if m.amount_incl_tax == document.amount_incl_tax]
    best = same_amount or matches
    return best[0] if best else None


def invoices_with_iban(session: Session, document: Document) -> list[Document]:
    if document.kind != DocumentKind.invoice or not document.iban:
        return []
    statement = (
        select(Document)
        .where(
            Document.owner_id == document.owner_id,
            Document.kind == DocumentKind.invoice,
            Document.id != document.id,
            col(Document.iban).is_not(None),
        )
        .options(defer(Document.file))  # type: ignore[arg-type]
    )
    if document.supplier_id is not None:
        statement = statement.where(
            or_(
                col(Document.supplier_id) == document.supplier_id,
                col(Document.supplier_id).is_(None),
            )
        )
    return list(session.exec(statement).all())


def expire_stale(session: Session) -> None:
    now = get_datetime_utc()
    since = func.coalesce(Document.started_at, Document.created_at)
    stale = session.exec(
        select(Document)
        .where(
            or_(
                and_(
                    col(Document.status) == DocumentStatus.processing,
                    since < now - STALE_AFTER,
                ),
                and_(
                    col(Document.status) == DocumentStatus.pending,
                    since < now - QUEUED_TOO_LONG,
                ),
            )
        )
        .options(defer(Document.file))  # type: ignore[arg-type]
    ).all()
    for document in stale:
        document.status = DocumentStatus.failed
        document.issues = [INTERRUPTED]
        session.add(document)
    if stale:
        session.commit()


def recheck_duplicates_of(session: Session, deleted: Document) -> None:
    if not deleted.supplier or not deleted.number:
        return
    flagged = session.exec(
        select(Document)
        .where(
            Document.owner_id == deleted.owner_id,
            Document.id != deleted.id,
            Document.kind == deleted.kind,
            Document.status == DocumentStatus.to_check,
            Document.number == deleted.number,
            func.lower(col(Document.supplier)) == deleted.supplier.lower(),
        )
        .options(defer(Document.file))  # type: ignore[arg-type]
    ).all()
    for document in flagged:
        issues = [i for i in document.issues if not i.startswith(NUMBER_ISSUES)]
        if original := find_duplicate(session, document):
            issues.append(number_issue(document, original))
        document.issues = issues
        document.status = DocumentStatus.to_check if issues else DocumentStatus.ok
        session.add(document)


def run_checks(
    session: Session, document: Document, extraction_issues: list[str] | None = None
) -> None:
    status, issues = check_document(
        document,
        find_duplicate(session, document),
        extraction_issues=extraction_issues,
        iban_issue=iban_change(document, invoices_with_iban(session, document)),
    )
    document.status = status
    document.issues = issues


def pdf_page_count(pdf: bytes) -> int | None:
    try:
        document = pdfium.PdfDocument(pdf)
    except pdfium.PdfiumError:
        return None
    try:
        return len(document)
    finally:
        document.close()


@dataclass(frozen=True)
class ReadOutcome:
    extracted: ExtractedDocument | None = None
    from_einvoice: bool = False
    error_status: DocumentStatus | None = None
    error_message: str | None = None


def extract_document(pdf: bytes, extractor: DocumentExtractor) -> ReadOutcome:
    """Read a PDF into structured data, without touching the database."""
    # An e-invoice carries its own figures: no AI.
    einvoice = read_einvoice(pdf)
    if einvoice is not None and einvoice.lines:
        return ReadOutcome(extracted=einvoice, from_einvoice=True)

    pages = pdf_page_count(pdf)
    if pages is not None and pages > MAX_PAGES:
        return ReadOutcome(
            error_status=DocumentStatus.unreadable,
            error_message=f"Document trop long ({pages} pages, {MAX_PAGES} maximum)",
        )

    # Gemini reads the PDF itself. A text copy made beforehand (Docling)
    # was tried and measured: it did not help, and sometimes misled it.
    try:
        extracted = extractor.extract(pdf)
    except ExtractionError as e:
        return ReadOutcome(error_status=DocumentStatus.failed, error_message=str(e))
    if einvoice is not None:
        extracted = merge_lines(einvoice, extracted)
    return ReadOutcome(extracted=extracted, from_einvoice=einvoice is not None)


def _finish(
    session: Session, document: Document, status: DocumentStatus, issue: str
) -> None:
    document.status = status
    document.issues = [issue]
    document.processed_at = get_datetime_utc()
    session.add(document)
    session.commit()


def save_outcome(session: Session, document: Document, outcome: ReadOutcome) -> None:
    if outcome.extracted is None:
        _finish(
            session,
            document,
            outcome.error_status or DocumentStatus.failed,
            outcome.error_message or "",
        )
        return

    apply_extraction(document, outcome.extracted)
    document.from_einvoice = outcome.from_einvoice
    order = remember(
        session,
        document,
        outcome.extracted.supplier_country,
        due_printed=to_date(outcome.extracted.due_date) is not None,
    )
    run_checks(session, document, review_extraction(outcome.extracted, order))
    document.processed_at = get_datetime_utc()
    session.add(document)
    session.commit()


def process_document(
    document_id: uuid.UUID,
    engine: Engine,
    extractor: DocumentExtractor,
) -> None:
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        pdf = document.file
        document.status = DocumentStatus.processing
        document.started_at = get_datetime_utc()
        session.add(document)
        session.commit()

        outcome = extract_document(pdf, extractor)
        try:
            save_outcome(session, document, outcome)
        except StaleDataError, ObjectDeletedError:
            session.rollback()
            logger.info("Document %s supprimé pendant sa lecture", document_id)
