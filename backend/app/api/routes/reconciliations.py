from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import defer, selectinload
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Document, Purchase, Purchases, PurchaseStatus
from app.services.reconciliation import PURCHASE_KINDS, build_purchases

router = APIRouter(prefix="/reconciliations", tags=["reconciliations"])


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
    return build_purchases(documents)


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
    for purchase in load_purchases(session, current_user).data:
        if purchase.key == key:
            return purchase
    raise HTTPException(status_code=404, detail="Achat introuvable")
