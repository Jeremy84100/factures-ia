import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Document,
    DocumentKind,
    DocumentRef,
    DocumentStatus,
    LearnedRule,
    Message,
    RuleField,
    Supplier,
    SupplierDetail,
    SupplierRule,
    Suppliers,
    SupplierSummary,
    SupplierUpdate,
    get_datetime_utc,
)
from app.services.iban import clean_iban, valid_iban
from app.services.processing import EMAIL, run_checks
from app.services.reconciliation import fold
from app.services.suppliers import (
    date_order_of,
    documents_of,
    ensure_suppliers,
    read_date,
    rule_label,
    save_rule,
    supplier_key,
    to_country,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

COUNTED = (DocumentStatus.ok, DocumentStatus.to_check)
RECENT = 8


def get_owned_supplier(
    session: SessionDep, user: CurrentUser, id: uuid.UUID
) -> Supplier:
    supplier = session.get(Supplier, id)
    if supplier is None or supplier.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    return supplier


def summaries(session: SessionDep, owner_id: uuid.UUID) -> list[SupplierSummary]:
    invoiced = func.sum(Document.amount_incl_tax).filter(
        col(Document.kind) == DocumentKind.invoice,
        col(Document.status).in_(COUNTED),
    )
    stats = {
        supplier_id: (count, total, last)
        for supplier_id, count, total, last in session.exec(
            select(
                Document.supplier_id,
                func.count(),
                invoiced,
                func.max(Document.document_date),
            )
            .where(
                Document.owner_id == owner_id,
                col(Document.supplier_id).is_not(None),
            )
            .group_by(col(Document.supplier_id))
        ).all()
    }
    suppliers = session.exec(
        select(Supplier).where(Supplier.owner_id == owner_id)
    ).all()
    result = []
    for supplier in suppliers:
        count, total, last = stats.get(supplier.id, (0, None, None))
        if not count:
            continue
        result.append(
            SupplierSummary.model_validate(
                supplier,
                update={
                    "documents": count,
                    "invoiced_incl_tax": total or Decimal(0),
                    "last_document_date": last,
                },
            )
        )
    return sorted(result, key=lambda s: fold(s.name))


def detail(session: SessionDep, supplier: Supplier) -> SupplierDetail:
    summary = next(
        (s for s in summaries(session, supplier.owner_id) if s.id == supplier.id),
        SupplierSummary.model_validate(supplier),
    )
    rules = session.exec(
        select(LearnedRule)
        .where(LearnedRule.supplier_id == supplier.id)
        .order_by(col(LearnedRule.created_at))
    ).all()
    recent = session.exec(
        select(Document)
        .where(
            Document.owner_id == supplier.owner_id,
            Document.supplier_id == supplier.id,
        )
        .order_by(
            col(Document.document_date).desc().nulls_last(),
            col(Document.created_at).desc(),
        )
        .limit(RECENT)
    ).all()
    return SupplierDetail.model_validate(
        summary,
        update={
            "rules": [
                SupplierRule(id=r.id, field=r.field, label=rule_label(r, supplier))
                for r in rules
            ],
            "recent": [DocumentRef.model_validate(d) for d in recent],
        },
    )


@router.get("/", response_model=Suppliers)
def read_suppliers(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    The suppliers of the user's documents, by name.
    """
    ensure_suppliers(session, current_user.id)
    data = summaries(session, current_user.id)
    return Suppliers(data=data, count=len(data))


@router.get("/{id}", response_model=SupplierDetail)
def read_supplier(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    A supplier, what the app has learned about it and its latest documents.
    """
    return detail(session, get_owned_supplier(session, current_user, id))


@router.put("/{id}", response_model=SupplierDetail)
def update_supplier(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    supplier_in: SupplierUpdate,
) -> Any:
    """
    Correct a supplier. Its documents follow: new name, dates read again.
    """
    supplier = get_owned_supplier(session, current_user, id)
    changes = supplier_in.model_dump(exclude_unset=True)
    documents = list(documents_of(session, supplier))

    if "country" in changes:
        raw = changes["country"]
        changes["country"] = to_country(raw)
        if raw and changes["country"] is None:
            raise HTTPException(
                status_code=400, detail="Pays : un code à 2 lettres (FR, DE, US…)"
            )
    if changes.get("email"):
        changes["email"] = changes["email"].strip()
        if not EMAIL.match(changes["email"]):
            raise HTTPException(status_code=400, detail="Adresse e-mail invalide")
    if "iban" in changes:
        iban = clean_iban(changes["iban"])
        if iban and not valid_iban(iban):
            raise HTTPException(
                status_code=400,
                detail="IBAN invalide : vérifiez-le chiffre par chiffre",
            )
        if iban != supplier.iban:
            supplier.iban_confirmed_at = get_datetime_utc() if iban else None
        changes["iban"] = iban
    for text in ("payment_terms", "email"):
        if text in changes:
            changes[text] = (changes[text] or "").strip() or None

    name = (changes.pop("name", None) or "").strip()
    if name and name != supplier.name:
        key = supplier_key(name)
        other = session.exec(
            select(Supplier).where(
                Supplier.owner_id == supplier.owner_id,
                Supplier.key == key,
                Supplier.id != supplier.id,
            )
        ).first()
        if other is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Un autre fournisseur s'appelle déjà {other.name}",
            )
        # The names its documents gave are remembered as this supplier.
        for written in {d.supplier for d in documents if d.supplier} | {supplier.name}:
            if fold(written) != fold(name):
                save_rule(session, supplier, RuleField.supplier, fold(written), name)
        supplier.name, supplier.key = name, key
        for document in documents:
            document.supplier = name

    order_before = date_order_of(supplier)
    supplier.sqlmodel_update(changes)
    order = date_order_of(supplier)
    for document in documents:
        if order != order_before and not document.from_einvoice:
            read = read_date(document.date_raw, order)
            if read is not None:
                document.document_date = read
        if document.status in COUNTED:
            run_checks(session, document)
        session.add(document)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return detail(session, supplier)


@router.delete("/{id}/rules/{rule_id}", response_model=Message)
def forget_rule(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID, rule_id: uuid.UUID
) -> Message:
    """
    Forget something the app learned from a correction.
    """
    supplier = get_owned_supplier(session, current_user, id)
    rule = session.get(LearnedRule, rule_id)
    if rule is None or rule.supplier_id != supplier.id:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    session.delete(rule)
    session.commit()
    return Message(message="Règle oubliée")
