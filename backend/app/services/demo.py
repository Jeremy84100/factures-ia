"""Demo accounts: one per visitor, filled with the demo documents already read.

Reading 31 PDFs with Docling and Gemini takes minutes, too long for a demo.
The documents are loaded as Gemini reads them (30/30 measured by
scripts/evaluate_purchases.py), then checked by the real rules, so every
verdict on screen comes from the same code as for real uploads.
"""

import json
import secrets
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from sqlmodel import Session, col, delete, func, select

from app.core.security import get_password_hash
from app.models import (
    DeliveryMode,
    Document,
    DocumentKind,
    DocumentLine,
    DocumentStatus,
    Supplier,
    User,
    get_datetime_utc,
)
from app.services.checks import check_document
from app.services.iban import iban_change
from app.services.reconciliation import SUPPLIER_MATCH
from app.services.suppliers import country_of, fill_from, supplier_key

DEMO_DIR = Path(__file__).parent.parent / "demo" / "purchases"
DEMO_DOMAIN = "demo.example.com"
DEMO_LIFETIME = timedelta(hours=24)
MAX_DEMO_USERS = 300
VAT_RATE = Decimal("0.20")
CENT = Decimal("0.01")


class DemoUnavailable(Exception):
    pass


@cache
def demo_cases() -> list[dict[str, Any]]:
    expected = json.loads((DEMO_DIR / "expected.json").read_text(encoding="utf-8"))
    documents: list[dict[str, Any]] = expected["documents"]
    return documents


@cache
def demo_pdf(filename: str) -> bytes:
    return (DEMO_DIR / filename).read_bytes()


@cache
def demo_password_hash() -> str:
    # Demo visitors sign in with the returned JWT, never with a password.
    return get_password_hash(secrets.token_urlsafe(32))


def to_decimal(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def demo_document(case: dict[str, Any], owner_id: uuid.UUID, today: date) -> Document:
    lines = []
    for position, line in enumerate(case["lines"]):
        price = to_decimal(line["unit_price"])
        quantity = Decimal(str(line["quantity"]))
        lines.append(
            DocumentLine(
                position=position,
                reference=line["reference"],
                description=line["description"],
                quantity=quantity,
                unit_price=price,
                amount_excl_tax=None
                if price is None
                else (quantity * price).quantize(CENT),
            )
        )
    promised = case.get("expected_delivery_date")
    due = case.get("due_date")
    now = get_datetime_utc()
    document = Document(
        kind=DocumentKind(case["kind"]),
        filename=case["filename"],
        file=demo_pdf(case["filename"]),
        owner_id=owner_id,
        supplier=case["supplier"],
        number=case["number"],
        document_date=date.fromisoformat(case["date"]),
        order_reference=case["order_reference"],
        delivery_method=case.get("delivery_method"),
        delivery_mode=DeliveryMode(case["delivery_mode"])
        if case.get("delivery_mode")
        else None,
        expected_delivery_date=date.fromisoformat(promised) if promised else None,
        payment_terms=case.get("payment_terms"),
        iban=case.get("iban"),
        supplier_email=case.get("supplier_email"),
        due_date=date.fromisoformat(due) if due else None,
        amount_excl_tax=to_decimal(case["amount_excl_tax"]),
        currency="EUR",
        lines=lines,
        started_at=now,
        processed_at=now,
    )
    if document.kind == DocumentKind.invoice:
        excl = document.amount_excl_tax or Decimal(0)
        document.vat_amount = (excl * VAT_RATE).quantize(CENT)
        document.amount_incl_tax = excl + document.vat_amount
    document.status, document.issues = check_document(document, None, today)
    return document


def check_ibans(documents: list[Document]) -> None:
    """The bank account check that a real upload does against the database."""
    for document in documents:
        issue = iban_change(document, documents)
        if issue:
            document.issues = [*document.issues, issue]
            document.status = DocumentStatus.to_check


def is_demo(user: User) -> bool:
    return user.email.endswith(f"@{DEMO_DOMAIN}")


def _link_demo_suppliers(
    owner_id: uuid.UUID, documents: list[Document]
) -> list[Supplier]:
    suppliers: list[Supplier] = []
    for document in sorted(documents, key=lambda d: d.document_date or date.min):
        if not document.supplier:
            continue
        key = supplier_key(document.supplier)
        supplier = next((s for s in suppliers if s.key == key), None)
        if supplier is None:
            best = max(
                ((fuzz.token_set_ratio(key, s.key), s) for s in suppliers),
                key=lambda pair: pair[0],
                default=None,
            )
            supplier = best[1] if best and best[0] >= SUPPLIER_MATCH else None
        if supplier is None:
            supplier = Supplier(owner_id=owner_id, name=document.supplier, key=key)
            suppliers.append(supplier)
        if not supplier.country:
            supplier.country = country_of(None, document.iban)
        document.supplier_id = supplier.id
        fill_from(supplier, document)
    return suppliers


def remove_expired_demo_users(session: Session, now: datetime) -> None:
    expired_ids = session.exec(
        select(User.id).where(
            col(User.email).endswith(f"@{DEMO_DOMAIN}"),
            col(User.created_at) < now - DEMO_LIFETIME,
        )
    ).all()
    if not expired_ids:
        return
    session.exec(delete(Document).where(col(Document.owner_id).in_(expired_ids)))
    session.exec(delete(User).where(col(User.id).in_(expired_ids)))
    session.commit()


def create_demo_user(session: Session, today: date | None = None) -> User:
    now = get_datetime_utc()
    remove_expired_demo_users(session, now)
    active = session.exec(
        select(func.count())
        .select_from(User)
        .where(col(User.email).endswith(f"@{DEMO_DOMAIN}"))
    ).one()
    if active >= MAX_DEMO_USERS:
        raise DemoUnavailable

    user = User(
        email=f"visiteur-{secrets.token_hex(6)}@{DEMO_DOMAIN}",
        full_name="Visiteur",
        hashed_password=demo_password_hash(),
    )
    documents = [
        demo_document(case, user.id, today or date.today()) for case in demo_cases()
    ]
    check_ibans(documents)
    suppliers = _link_demo_suppliers(user.id, documents)
    session.add(user)
    session.flush()
    session.add_all(suppliers)
    session.flush()
    session.add_all(documents)
    session.commit()
    session.refresh(user)
    return user
