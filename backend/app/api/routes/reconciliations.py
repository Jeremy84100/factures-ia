from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import defer, selectinload
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Document,
    Payment,
    Purchase,
    Purchases,
    PurchaseStatus,
    Settlement,
    SupplierEmail,
    get_datetime_utc,
)
from app.services.demo import is_demo
from app.services.reconciliation import (
    PURCHASE_KINDS,
    USABLE,
    all_issues,
    build_purchase,
    build_purchases,
)
from app.services.supplier_email import write_email
from app.services.suppliers import ensure_suppliers

router = APIRouter(prefix="/reconciliations", tags=["reconciliations"])


def settlements_of(session: SessionDep, user: CurrentUser) -> dict[str, Settlement]:
    rows = session.exec(select(Settlement).where(Settlement.owner_id == user.id))
    return {row.purchase_key: row for row in rows}


def payments_of(session: SessionDep, user: CurrentUser) -> list[Payment]:
    return list(session.exec(select(Payment).where(Payment.owner_id == user.id)))


def _load_documents(session: SessionDep, user: CurrentUser) -> list[Document]:
    statement = (
        select(Document)
        .where(
            Document.owner_id == user.id,
            col(Document.kind).in_(PURCHASE_KINDS),
            col(Document.status).in_(USABLE),
        )
        .options(
            defer(Document.file),  # type: ignore[arg-type]
            selectinload(Document.lines),  # type: ignore[arg-type]
        )
        .order_by(col(Document.created_at))
    )
    documents = list(session.exec(statement).all())
    if any(d.supplier_id is None and d.supplier for d in documents):
        ensure_suppliers(session, user.id)
        documents = list(session.exec(statement).all())
    return documents


def _load_state(
    session: SessionDep, user: CurrentUser
) -> tuple[list[Document], dict[str, Settlement], list[Payment]]:
    return (
        _load_documents(session, user),
        settlements_of(session, user),
        payments_of(session, user),
    )


def _require_purchase(
    documents: list[Document],
    key: str,
    settlements: dict[str, Settlement],
    payments: list[Payment],
) -> Purchase:
    purchase = build_purchase(
        documents, key, settlements=settlements, payments=payments
    )
    if purchase is None:
        raise HTTPException(status_code=404, detail="Achat introuvable")
    return purchase


def load_purchases(session: SessionDep, user: CurrentUser) -> Purchases:
    documents, settlements, payments = _load_state(session, user)
    return build_purchases(documents, settlements=settlements, payments=payments)


def find_purchase(session: SessionDep, user: CurrentUser, key: str) -> Purchase:
    documents, settlements, payments = _load_state(session, user)
    return _require_purchase(documents, key, settlements, payments)


@router.get("/", response_model=Purchases)
def read_purchases(
    session: SessionDep,
    current_user: CurrentUser,
    status: PurchaseStatus | None = None,
) -> Any:
    """
    Purchases rebuilt from orders, delivery notes and invoices, with the
    documents still waiting to be linked to an order.
    """
    purchases = load_purchases(session, current_user)
    if status:
        purchases.data = [p for p in purchases.data if p.status == status]
        purchases.count = len(purchases.data)
    return purchases


@router.get("/{key}", response_model=Purchase)
def read_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    One purchase, compared line by line.
    """
    return find_purchase(session, current_user, key)


@router.get("/{key}/email", response_model=SupplierEmail)
def read_supplier_email(
    session: SessionDep, current_user: CurrentUser, key: str
) -> Any:
    """
    A letter to the supplier listing what does not match, ready to send.
    """
    purchase = find_purchase(session, current_user, key)
    if not all_issues(purchase) and not purchase.late:
        raise HTTPException(status_code=400, detail="Aucun écart à signaler")
    sender = None if is_demo(current_user) else current_user.full_name
    return write_email(purchase, sender)


@router.post("/{key}/settle", response_model=Purchase)
def settle_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Mark a dispute as settled with the supplier, for the issues it has now.
    """
    documents, settlements, payments = _load_state(session, current_user)
    purchase = _require_purchase(documents, key, settlements, payments)
    if purchase.status != PurchaseStatus.dispute:
        raise HTTPException(status_code=400, detail="Cet achat n'est pas en litige")
    settlement = settlements.get(key) or Settlement(
        owner_id=current_user.id, purchase_key=key
    )
    settlement.issues = all_issues(purchase)
    settlement.settled_at = get_datetime_utc()
    settlements[key] = settlement
    session.add(settlement)
    session.flush()
    updated = _require_purchase(documents, key, settlements, payments)
    session.commit()
    return updated


@router.delete("/{key}/settle", response_model=Purchase)
def reopen_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Put a settled dispute back among the disputes.
    """
    documents, settlements, payments = _load_state(session, current_user)
    settlement = settlements.pop(key, None)
    if settlement:
        session.delete(settlement)
        session.flush()
    updated = _require_purchase(documents, key, settlements, payments)
    session.commit()
    return updated


@router.post("/{key}/pay", response_model=Purchase)
def pay_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Mark the invoices of a purchase as paid. An invoice added later is still
    to pay.
    """
    documents, settlements, payments = _load_state(session, current_user)
    purchase = _require_purchase(documents, key, settlements, payments)
    if purchase.status != PurchaseStatus.to_pay:
        raise HTTPException(
            status_code=400, detail="Cet achat n'est pas encore bon à payer"
        )
    payment = next((p for p in payments if p.purchase_key == key), None)
    if payment is None:
        payment = Payment(owner_id=current_user.id, purchase_key=key)
        payments.append(payment)
    payment.invoice_ids = [str(invoice.id) for invoice in purchase.invoices]
    payment.paid_at = get_datetime_utc()
    session.add(payment)
    session.flush()
    updated = _require_purchase(documents, key, settlements, payments)
    session.commit()
    return updated


@router.delete("/{key}/pay", response_model=Purchase)
def unpay_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Undo « Payé »: the invoices are to pay again.
    """
    documents, settlements, payments = _load_state(session, current_user)
    purchase = _require_purchase(documents, key, settlements, payments)
    invoices = {str(invoice.id) for invoice in purchase.invoices}
    remaining: list[Payment] = []
    for payment in payments:
        if not invoices & set(payment.invoice_ids):
            remaining.append(payment)
            continue
        kept = [id for id in payment.invoice_ids if id not in invoices]
        if kept:
            payment.invoice_ids = kept
            session.add(payment)
            remaining.append(payment)
        else:
            session.delete(payment)
    session.flush()
    updated = _require_purchase(documents, key, settlements, remaining)
    session.commit()
    return updated
