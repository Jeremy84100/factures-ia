import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile
from fastapi import File as FileParam
from sqlalchemy.orm import defer, selectinload
from sqlmodel import col, delete, extract, func, select

from app.api.deps import CurrentUser, EngineDep, ExtractorDep, PdfReaderDep, SessionDep
from app.models import (
    Document,
    DocumentKind,
    DocumentPublic,
    DocumentsPublic,
    DocumentStatus,
    DocumentUpdate,
    LineFields,
    Message,
    SupplierTotal,
    SupplierTotals,
    User,
    get_datetime_utc,
)
from app.services.images import ImageError, image_to_pdf, is_image
from app.services.payment_terms import due_from_terms
from app.services.processing import (
    expire_stale,
    process_document,
    recheck_duplicates_of,
    run_checks,
    sign_credit_note,
    to_lines,
)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILES = 50
BUSY = (DocumentStatus.pending, DocumentStatus.processing)


def to_public(document: Document) -> DocumentPublic:
    public = DocumentPublic.model_validate(document, update={"lines": []})
    public.lines = [LineFields.model_validate(line) for line in document.lines]
    return public


def get_owned_document(session: SessionDep, user: User, id: uuid.UUID) -> Document:
    document = session.get(Document, id)
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

    count = session.exec(
        select(func.count()).select_from(Document).where(*conditions)
    ).one()
    documents = session.exec(
        select(Document)
        .where(*conditions)
        .options(defer(Document.file), selectinload(Document.lines))  # type: ignore[arg-type]
        .order_by(col(Document.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return DocumentsPublic(data=[to_public(d) for d in documents], count=count)


@router.post("/", response_model=DocumentsPublic)
async def upload_documents(
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    reader: PdfReaderDep,
    extractor: ExtractorDep,
    files: Annotated[list[UploadFile], FileParam()],
) -> Any:
    """
    Upload PDF documents of any kind. Each one is sorted, read and checked in
    the background.
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

    documents = [
        Document(filename=name, file=data, owner_id=current_user.id)
        for name, data in contents
    ]
    session.add_all(documents)
    session.commit()
    for document in documents:
        session.refresh(document)
        background_tasks.add_task(
            process_document, document.id, engine, reader, extractor
        )

    return DocumentsPublic(data=[to_public(d) for d in documents], count=len(documents))


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
    document = get_owned_document(session, current_user, id)
    return Response(
        content=document.file,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
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
    changes = document_in.model_dump(exclude_unset=True, exclude={"lines"})
    if changes.get("kind") is None:
        changes.pop("kind", None)
    document.sqlmodel_update(changes)
    if document_in.lines is not None:
        document.lines = to_lines(document_in.lines)
    if document.due_date is None:
        document.due_date = due_from_terms(
            document.payment_terms, document.document_date
        )
    sign_credit_note(document)
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
    reader: PdfReaderDep,
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
    background_tasks.add_task(process_document, document.id, engine, reader, extractor)
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
