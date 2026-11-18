import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import Engine, and_, func, or_
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError
from sqlmodel import Session, col, select

from app.models import (
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
from app.services.payment_terms import due_from_terms
from app.services.pdf_reader import PdfReader

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
QUANTITY_STEP = Decimal("0.001")
PRICE_STEP = Decimal("0.0001")
STALE_AFTER = timedelta(minutes=10)
QUEUED_TOO_LONG = timedelta(hours=1)
INTERRUPTED = "Lecture interrompue par le serveur, relancez-la"

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
    ]
    return [to_line(line, position) for position, line in enumerate(kept)]


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
    document.order_reference = to_text(extracted.order_reference, 100)
    document.amount_excl_tax = to_amount(extracted.amount_excl_tax)
    document.vat_amount = to_amount(extracted.vat_amount)
    document.amount_incl_tax = to_amount(extracted.amount_incl_tax)
    document.currency = (extracted.currency or "").upper()[:3] or None
    document.is_credit_note = bool(extracted.is_credit_note)
    document.vat_exemption = to_text(extracted.vat_exemption, 255)
    document.delivery_method = to_text(extracted.delivery_method, 100)
    document.delivery_mode = DELIVERY_MODES.get(extracted.delivery_mode or "")
    document.expected_delivery_date = to_date(extracted.expected_delivery_date)
    document.payment_terms = to_text(extracted.payment_terms, 100)
    document.due_date = to_date(extracted.due_date) or due_from_terms(
        document.payment_terms, document.document_date
    )
    document.lines = to_lines(extracted.lines)
    sign_credit_note(document)


def find_duplicate(session: Session, document: Document) -> Document | None:
    if not document.supplier or not document.number:
        return None
    statement = select(Document).where(
        Document.owner_id == document.owner_id,
        Document.id != document.id,
        Document.kind == document.kind,
        Document.number == document.number,
        func.lower(col(Document.supplier)) == document.supplier.lower(),
    )
    matches = session.exec(statement).all()
    same_amount = [m for m in matches if m.amount_incl_tax == document.amount_incl_tax]
    best = same_amount or matches
    return best[0] if best else None


def expire_stale(session: Session) -> None:
    now = get_datetime_utc()
    since = func.coalesce(Document.started_at, Document.created_at)
    stale = session.exec(
        select(Document).where(
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
        select(Document).where(
            Document.owner_id == deleted.owner_id,
            Document.id != deleted.id,
            Document.kind == deleted.kind,
            Document.status == DocumentStatus.to_check,
            Document.number == deleted.number,
            func.lower(col(Document.supplier)) == deleted.supplier.lower(),
        )
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
    )
    document.status = status
    document.issues = issues


def _finish(
    session: Session, document: Document, status: DocumentStatus, issue: str
) -> None:
    document.status = status
    document.issues = [issue]
    document.processed_at = get_datetime_utc()
    session.add(document)
    session.commit()


def process_document(
    document_id: uuid.UUID,
    engine: Engine,
    reader: PdfReader,
    extractor: DocumentExtractor,
) -> None:
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.processing
        document.started_at = get_datetime_utc()
        session.add(document)
        session.commit()

        try:
            _read(session, document, reader, extractor)
        except StaleDataError, ObjectDeletedError:
            session.rollback()
            logger.info("Document %s supprimé pendant sa lecture", document_id)


def _read(
    session: Session,
    document: Document,
    reader: PdfReader,
    extractor: DocumentExtractor,
) -> None:
    # An e-invoice carries its own figures: no OCR, no AI.
    einvoice = read_einvoice(document.file)
    if einvoice is not None and einvoice.lines:
        extracted = einvoice
    else:
        try:
            text = reader.read(document.file, document.filename)
        except Exception:
            logger.exception("Lecture OCR impossible de %s", document.filename)
            text = ""

        try:
            extracted = extractor.extract(text, document.file)
        except ExtractionError as e:
            _finish(session, document, DocumentStatus.failed, str(e))
            return
        if einvoice is not None:
            extracted = merge_lines(einvoice, extracted)

    apply_extraction(document, extracted)
    document.from_einvoice = einvoice is not None
    run_checks(session, document, review_extraction(extracted))
    document.processed_at = get_datetime_utc()
    session.add(document)
    session.commit()
