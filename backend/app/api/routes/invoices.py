import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile
from fastapi import File as FileParam
from sqlmodel import col, extract, func, select

from app.api.deps import CurrentUser, EngineDep, ExtractorDep, PdfReaderDep, SessionDep
from app.models import (
    Invoice,
    InvoicePublic,
    InvoicesPublic,
    InvoiceStatus,
    InvoiceUpdate,
    Message,
    SupplierTotal,
    SupplierTotals,
    User,
    get_datetime_utc,
)
from app.services.processing import (
    expire_stale,
    process_invoice,
    recheck_duplicates_of,
    run_checks,
    sign_credit_note,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILES = 50


def get_owned_invoice(session: SessionDep, user: User, id: uuid.UUID) -> Invoice:
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    if not user.is_superuser and invoice.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return invoice


@router.get("/", response_model=InvoicesPublic)
def read_invoices(
    session: SessionDep,
    current_user: CurrentUser,
    status: InvoiceStatus | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve invoices.
    """
    expire_stale(session)
    conditions = []
    if not current_user.is_superuser:
        conditions.append(Invoice.owner_id == current_user.id)
    if status:
        conditions.append(Invoice.status == status)

    count = session.exec(
        select(func.count()).select_from(Invoice).where(*conditions)
    ).one()
    invoices = session.exec(
        select(Invoice)
        .where(*conditions)
        .order_by(col(Invoice.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return InvoicesPublic(
        data=[InvoicePublic.model_validate(invoice) for invoice in invoices],
        count=count,
    )


@router.post("/", response_model=InvoicesPublic)
async def upload_invoices(
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    reader: PdfReaderDep,
    extractor: ExtractorDep,
    files: Annotated[list[UploadFile], FileParam()],
) -> Any:
    """
    Upload PDF invoices. Each one is read and checked in the background.
    """
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"{MAX_FILES} fichiers maximum par envoi"
        )

    contents: list[tuple[str, bytes]] = []
    for upload in files:
        data = await upload.read(MAX_FILE_SIZE + 1)
        name = upload.filename or "facture.pdf"
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"{name} dépasse 10 Mo")
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail=f"{name} n'est pas un PDF")
        contents.append((name, data))

    invoices = [
        Invoice(filename=name, file=data, owner_id=current_user.id)
        for name, data in contents
    ]
    session.add_all(invoices)
    session.commit()
    for invoice in invoices:
        session.refresh(invoice)
        background_tasks.add_task(
            process_invoice, invoice.id, engine, reader, extractor
        )

    return InvoicesPublic(
        data=[InvoicePublic.model_validate(invoice) for invoice in invoices],
        count=len(invoices),
    )


@router.get("/totals", response_model=SupplierTotals)
def read_supplier_totals(
    session: SessionDep, current_user: CurrentUser, year: int | None = None
) -> Any:
    """
    Total incl. tax per supplier, counting only validated invoices.
    """
    total = func.sum(Invoice.amount_incl_tax)
    statement = (
        select(Invoice.supplier, func.count(), total)
        .where(Invoice.status == InvoiceStatus.ok)
        .group_by(col(Invoice.supplier))
        .order_by(total.desc())
    )
    if not current_user.is_superuser:
        statement = statement.where(Invoice.owner_id == current_user.id)
    if year:
        statement = statement.where(extract("year", Invoice.invoice_date) == year)

    rows = session.exec(statement).all()
    return SupplierTotals(
        data=[
            SupplierTotal(supplier=supplier, count=count, total_incl_tax=amount)
            for supplier, count, amount in rows
            if supplier is not None and amount is not None
        ]
    )


@router.get("/{id}", response_model=InvoicePublic)
def read_invoice(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get invoice by ID.
    """
    return get_owned_invoice(session, current_user, id)


@router.get("/{id}/file", response_class=Response)
def read_invoice_file(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Response:
    """
    Download the original PDF.
    """
    invoice = get_owned_invoice(session, current_user, id)
    return Response(
        content=invoice.file,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.filename}"'},
    )


@router.put("/{id}", response_model=InvoicePublic)
def update_invoice(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    invoice_in: InvoiceUpdate,
) -> Any:
    """
    Correct invoice fields by hand. Checks run again afterwards.
    """
    invoice = get_owned_invoice(session, current_user, id)
    if invoice.status in (InvoiceStatus.pending, InvoiceStatus.processing):
        raise HTTPException(status_code=409, detail="Facture en cours de lecture")
    invoice.sqlmodel_update(invoice_in.model_dump(exclude_unset=True))
    sign_credit_note(invoice)
    run_checks(session, invoice)
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


@router.post("/{id}/retry", response_model=InvoicePublic)
def retry_invoice(
    session: SessionDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    reader: PdfReaderDep,
    extractor: ExtractorDep,
    id: uuid.UUID,
) -> Any:
    """
    Read the invoice again with the AI.
    """
    expire_stale(session)
    invoice = get_owned_invoice(session, current_user, id)
    if invoice.status in (InvoiceStatus.pending, InvoiceStatus.processing):
        raise HTTPException(status_code=409, detail="Facture en cours de lecture")
    invoice.status = InvoiceStatus.pending
    invoice.issues = []
    invoice.started_at = get_datetime_utc()
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    background_tasks.add_task(process_invoice, invoice.id, engine, reader, extractor)
    return invoice


@router.delete("/{id}")
def delete_invoice(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an invoice.
    """
    invoice = get_owned_invoice(session, current_user, id)
    session.delete(invoice)
    session.flush()
    recheck_duplicates_of(session, invoice)
    session.commit()
    return Message(message="Facture supprimée")
