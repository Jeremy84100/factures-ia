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
from app.services.reconciliation import PURCHASE_KINDS, all_issues, build_purchases
from app.services.supplier_email import write_email

router = APIRouter(prefix="/reconciliations", tags=["reconciliations"])


def settlements_of(session: SessionDep, user: CurrentUser) -> dict[str, Settlement]:
    rows = session.exec(select(Settlement).where(Settlement.owner_id == user.id))
    return {row.purchase_key: row for row in rows}


def payments_of(session: SessionDep, user: CurrentUser) -> dict[str, Payment]:
    rows = session.exec(select(Payment).where(Payment.owner_id == user.id))
    return {row.purchase_key: row for row in rows}


def load_purchases(session: SessionDep, user: CurrentUser) -> Purchases:
    documents = session.exec(
        select(Document)
        .where(
            Document.owner_id == user.id,
            col(Document.kind).in_(PURCHASE_KINDS),
        )
        .options(defer(Document.file), selectinload(Document.lines))  # type: ignore[arg-type]
        .order_by(col(Document.created_at))
    ).all()
    return build_purchases(
        documents,
        settlements=settlements_of(session, user),
        payments=payments_of(session, user),
    )


def find_purchase(session: SessionDep, user: CurrentUser, key: str) -> Purchase:
    for purchase in load_purchases(session, user).data:
        if purchase.key == key:
            return purchase
    raise HTTPException(status_code=404, detail="Achat introuvable")


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
    purchase = find_purchase(session, current_user, key)
    if purchase.status != PurchaseStatus.dispute:
        raise HTTPException(status_code=400, detail="Cet achat n'est pas en litige")
    settlement = settlements_of(session, current_user).get(key) or Settlement(
        owner_id=current_user.id, purchase_key=key
    )
    settlement.issues = all_issues(purchase)
    settlement.settled_at = get_datetime_utc()
    session.add(settlement)
    session.commit()
    return find_purchase(session, current_user, key)


@router.delete("/{key}/settle", response_model=Purchase)
def reopen_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Put a settled dispute back among the disputes.
    """
    settlement = settlements_of(session, current_user).get(key)
    if settlement:
        session.delete(settlement)
        session.commit()
    return find_purchase(session, current_user, key)


@router.post("/{key}/pay", response_model=Purchase)
def pay_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Mark the invoices of a purchase as paid. An invoice added later is still
    to pay.
    """
    purchase = find_purchase(session, current_user, key)
    if purchase.status != PurchaseStatus.to_pay:
        raise HTTPException(
            status_code=400, detail="Cet achat n'est pas encore bon à payer"
        )
    payment = payments_of(session, current_user).get(key) or Payment(
        owner_id=current_user.id, purchase_key=key
    )
    payment.invoice_ids = [str(invoice.id) for invoice in purchase.invoices]
    payment.paid_at = get_datetime_utc()
    session.add(payment)
    session.commit()
    return find_purchase(session, current_user, key)


@router.delete("/{key}/pay", response_model=Purchase)
def unpay_purchase(session: SessionDep, current_user: CurrentUser, key: str) -> Any:
    """
    Undo « Payé »: the invoices are to pay again.
    """
    payment = payments_of(session, current_user).get(key)
    if payment:
        session.delete(payment)
        session.commit()
    return find_purchase(session, current_user, key)
