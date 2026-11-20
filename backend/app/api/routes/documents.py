import asyncio
import unicodedata
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

import anyio
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile
from fastapi import File as FileParam
from sqlalchemy.orm import defer, selectinload
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError
from sqlmodel import Session, col, delete, extract, func, select

from app.api.deps import CurrentUser, EngineDep, ExtractorDep, SessionDep
from app.core.config import settings
from app.models import (
    Document,
    DocumentKind,
    DocumentPublic,
    DocumentsPublic,
    DocumentStatus,
    DocumentUpdate,
    LineFields,
    Message,
    Payment,
    Settlement,
    Supplier,
    SupplierTotal,
    SupplierTotals,
    User,
    get_datetime_utc,
)
from app.services.export import build_export
from app.services.iban import clean_iban
from app.services.images import ImageError, image_to_pdf, is_image
from app.services.payment_terms import due_from_terms
from app.services.processing import (
    ReadOutcome,
    expire_stale,
    extract_document,
    process_document,
    recheck_duplicates_of,
    run_checks,
    save_outcome,
    sign_credit_note,
    to_lines,
)
from app.services.suppliers import Before, learn

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024
# Cloud Run answers 32 MB at most; Vercel functions answer 4.5 MB.
MAX_EXPORT_SIZE = 30 * 1024 * 1024
MAX_VERCEL_EXPORT_SIZE = 4 * 1024 * 1024
MAX_CONCURRENT_READS = 5
EXPORTED = (DocumentStatus.ok, DocumentStatus.to_check)
MAX_FILES = 50
BUSY = (DocumentStatus.pending, DocumentStatus.processing)


def to_public(document: Document) -> DocumentPublic:
    public = DocumentPublic.model_validate(document, update={"lines": []})
    public.lines = [LineFields.model_validate(line) for line in document.lines]
    return public


def content_disposition(disposition: str, filename: str) -> str:
    plain = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode()
        .replace('"', "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
        or "document.pdf"
    )
    encoded = quote(filename, safe="")
    return f"{disposition}; filename=\"{plain}\"; filename*=UTF-8''{encoded}"


def get_owned_document(
    session: SessionDep, user: User, id: uuid.UUID, *, include_file: bool = False
) -> Document:
    statement = select(Document).where(Document.id == id)
    if not include_file:
        statement = statement.options(
            defer(Document.file),  # type: ignore[arg-type]
            selectinload(Document.lines),  # type: ignore[arg-type]
        )
    document = session.exec(statement).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")
    if not user.is_superuser and document.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Droits insuffisants")
    return document


@router.get("/", response_model=DocumentsPublic)
def read_documents(
    session: SessionDep,
    current_user: CurrentUser,
    kind: DocumentKind | None = None,
    status: DocumentStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve documents, optionally filtered by kind and status.
    """
    expire_stale(session)
    conditions = []
    if not current_user.is_superuser:
        conditions.append(Document.owner_id == current_user.id)
    if kind:
        conditions.append(Document.kind == kind)
    if status:
        conditions.append(Document.status == status)

    documents = session.exec(
        select(Document)
        .where(*conditions)
        .options(defer(Document.file), selectinload(Document.lines))  # type: ignore[arg-type]
        .order_by(col(Document.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    if skip == 0 and len(documents) < limit:
        count = len(documents)
    else:
        count = session.exec(
            select(func.count()).select_from(Document).where(*conditions)
        ).one()
    return DocumentsPublic(data=[to_public(d) for d in documents], count=count)


async def _extract_all(pdfs: list[bytes], extractor: ExtractorDep) -> list[ReadOutcome]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_READS)

    async def one(pdf: bytes) -> ReadOutcome:
        async with semaphore:
            return await anyio.to_thread.run_sync(extract_document, pdf, extractor)

    return list(await asyncio.gather(*(one(pdf) for pdf in pdfs)))


def _load_in_order(session: Session, ids: list[uuid.UUID]) -> list[Document]:
    rows = session.exec(
        select(Document)
        .where(col(Document.id).in_(ids))
        .options(defer(Document.file), selectinload(Document.lines))  # type: ignore[arg-type]
    ).all()
    by_id = {row.id: row for row in rows}
    return [by_id[id] for id in ids if id in by_id]


@router.post("/", response_model=DocumentsPublic)
async def upload_documents(
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    extractor: ExtractorDep,
    files: Annotated[list[UploadFile], FileParam()],
) -> Any:
    """
    Upload PDF documents of any kind. Each one is sorted, read and checked in
    the background, or before the answer when READ_IN_REQUEST is set.
    """
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"{MAX_FILES} fichiers maximum par envoi"
        )

    contents: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read(MAX_FILE_SIZE + 1)
        name = upload.filename or "document.pdf"
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"{name} dépasse 10 Mo")
        if is_image(data):
            try:
                data = image_to_pdf(data)
            except ImageError:
                raise HTTPException(status_code=400, detail=f"{name} : photo illisible")
            name = f"{Path(name).stem}.pdf"
        elif not data.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400,
                detail=f"{name} n'est ni un PDF ni une photo (JPEG, PNG, WebP)",
            )
        contents.append((name, data))

    now = get_datetime_utc()
    documents = [
        Document(
            filename=name,
            file=data,
            owner_id=current_user.id,
            status=DocumentStatus.processing
            if settings.READ_IN_REQUEST
            else DocumentStatus.pending,
            started_at=now if settings.READ_IN_REQUEST else None,
        )
        for name, data in contents
    ]
    ids = [document.id for document in documents]
    session.add_all(documents)
    session.commit()

    if settings.READ_IN_REQUEST:
        # AI readings run in parallel (network I/O), then results are saved one
        # after the other so two documents of the same new supplier never race.
        outcomes = await _extract_all([data for _, data in contents], extractor)
        saved: list[DocumentPublic] = []
        with Session(engine) as write_session:
            for doc_id, outcome in zip(ids, outcomes, strict=True):
                doc = write_session.exec(
                    select(Document)
                    .where(Document.id == doc_id)
                    .options(defer(Document.file), selectinload(Document.lines))  # type: ignore[arg-type]
                ).first()
                if doc is None:
                    continue
                try:
                    save_outcome(write_session, doc, outcome)
                except StaleDataError, ObjectDeletedError:
                    write_session.rollback()
                    continue
                saved.append(to_public(doc))
        return DocumentsPublic(data=saved, count=len(saved))

    for id in ids:
        background_tasks.add_task(process_document, id, engine, extractor)
    loaded = _load_in_order(session, ids)
    return DocumentsPublic(data=[to_public(d) for d in loaded], count=len(loaded))


@router.get("/totals", response_model=SupplierTotals)
def read_supplier_totals(
    session: SessionDep, current_user: CurrentUser, year: int | None = None
) -> Any:
    """
    Total incl. tax per supplier, counting only validated invoices.
    """
    total = func.sum(Document.amount_incl_tax)
    statement = (
        select(Document.supplier, func.count(), total)
        .where(
            Document.kind == DocumentKind.invoice,
            Document.status == DocumentStatus.ok,
        )
        .group_by(col(Document.supplier))
        .order_by(total.desc())
    )
    if not current_user.is_superuser:
        statement = statement.where(Document.owner_id == current_user.id)
    if year:
        statement = statement.where(extract("year", Document.document_date) == year)

    rows = session.exec(statement).all()
    return SupplierTotals(
        data=[
            SupplierTotal(supplier=supplier, count=count, total_incl_tax=amount)
            for supplier, count, amount in rows
            if supplier is not None and amount is not None
        ]
    )


@router.get("/export", response_class=Response)
def export_invoices(
    session: SessionDep, current_user: CurrentUser, month: str | None = None
) -> Response:
    """
    The invoices and credit notes for the accountant: a spreadsheet and the
    PDFs in one zip. `month` (2026-11) keeps one month only.
    """
    statement = (
        select(Document)
        .where(
            Document.owner_id == current_user.id,
            Document.kind == DocumentKind.invoice,
            col(Document.status).in_(EXPORTED),
        )
        .order_by(col(Document.document_date), col(Document.created_at))
    )
    if month:
        try:
            year, number = (int(part) for part in month.split("-"))
            first = date(year, number, 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Mois invalide (2026-11)")
        after = date(year + number // 12, number % 12 + 1, 1)
        statement = statement.where(
            col(Document.document_date) >= first, col(Document.document_date) < after
        )
    invoices = session.exec(statement).all()
    if not invoices:
        raise HTTPException(status_code=404, detail="Aucune facture à exporter")
    payments = session.exec(select(Payment).where(Payment.owner_id == current_user.id))
    paid_on = {id: p.paid_at for p in payments for id in p.invoice_ids}
    content = build_export(invoices, paid_on)
    limit = MAX_EXPORT_SIZE if settings.READ_IN_REQUEST else MAX_VERCEL_EXPORT_SIZE
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail="Trop de factures pour un seul fichier : exportez mois par mois",
        )
    name = f"factures-{month or 'toutes'}.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/{id}", response_model=DocumentPublic)
def read_document(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get document by ID.
    """
    return to_public(get_owned_document(session, current_user, id))


@router.get("/{id}/file", response_class=Response)
def read_document_file(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Response:
    """
    Download the original PDF.
    """
    document = get_owned_document(session, current_user, id, include_file=True)
    return Response(
        content=document.file,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition("inline", document.filename),
            "Cache-Control": "private, max-age=31536000, immutable",
        },
    )


@router.put("/{id}", response_model=DocumentPublic)
def update_document(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    document_in: DocumentUpdate,
) -> Any:
    """
    Correct a document by hand: kind, fields, order number or lines. Checks
    run again afterwards.
    """
    document = get_owned_document(session, current_user, id)
    if document.status in BUSY:
        raise HTTPException(status_code=409, detail="Document en cours de lecture")
    before = Before.of(document)
    changes = document_in.model_dump(exclude_unset=True, exclude={"lines"})
    if "iban" in changes and clean_iban(changes["iban"]) != document.iban:
        document.iban_checked = False
    if changes.get("kind") is None:
        changes.pop("kind", None)
    document.sqlmodel_update(changes)
    if document_in.lines is not None:
        document.lines = to_lines(document_in.lines)
    document.iban = clean_iban(document.iban)
    if document.due_date is None:
        document.due_date = due_from_terms(
            document.payment_terms, document.document_date
        )
    sign_credit_note(document)
    learned = learn(session, document, before)
    run_checks(session, document)
    session.add(document)
    session.commit()
    session.refresh(document)
    public = to_public(document)
    public.learned = learned
    return public


@router.post("/{id}/confirm-iban", response_model=DocumentPublic)
def confirm_iban(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    The supplier was called and confirmed the new IBAN of this invoice.
    """
    document = get_owned_document(session, current_user, id)
    if document.status in BUSY:
        raise HTTPException(status_code=409, detail="Document en cours de lecture")
    document.iban_checked = True
    supplier = (
        session.get(Supplier, document.supplier_id) if document.supplier_id else None
    )
    if supplier is not None and document.iban:
        # Like a trusted bank account in Odoo: the one to pay from now on.
        supplier.iban = document.iban
        supplier.iban_confirmed_at = get_datetime_utc()
        session.add(supplier)
    run_checks(session, document)
    session.add(document)
    session.commit()
    session.refresh(document)
    return to_public(document)


@router.post("/{id}/retry", response_model=DocumentPublic)
def retry_document(
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    extractor: ExtractorDep,
    id: uuid.UUID,
) -> Any:
    """
    Read the document again with the AI.
    """
    expire_stale(session)
    document = get_owned_document(session, current_user, id)
    if document.status in BUSY:
        raise HTTPException(status_code=409, detail="Document en cours de lecture")
    document.status = DocumentStatus.pending
    document.issues = []
    document.started_at = get_datetime_utc()
    session.add(document)
    session.commit()
    session.refresh(document)
    if settings.READ_IN_REQUEST:
        process_document(document.id, engine, extractor)
        session.expire_all()
        document = get_owned_document(session, current_user, id)
    else:
        background_tasks.add_task(process_document, document.id, engine, extractor)
    return to_public(document)


@router.delete("/")
def delete_all_documents(session: SessionDep, current_user: CurrentUser) -> Message:
    """
    Delete every document of the current user, even for an admin.
    """
    count = session.exec(
        select(func.count())
        .select_from(Document)
        .where(Document.owner_id == current_user.id)
    ).one()
    session.exec(delete(Document).where(col(Document.owner_id) == current_user.id))
    session.exec(delete(Payment).where(col(Payment.owner_id) == current_user.id))
    session.exec(delete(Settlement).where(col(Settlement.owner_id) == current_user.id))
    session.commit()
    return Message(message=f"Documents supprimés : {count}")


@router.delete("/{id}")
def delete_document(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a document.
    """
    document = get_owned_document(session, current_user, id)
    session.delete(document)
    session.flush()
    recheck_duplicates_of(session, document)
    session.commit()
    return Message(message="Document supprimé")
