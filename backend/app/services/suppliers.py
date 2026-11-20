"""Suppliers, and what the app has learned about them.

Each document is filed under a supplier, found again whatever way its name is
written ("ÉLECTRO PROVENCE DISTRIB. SAS", "Electro Provence Distribution").
The supplier's page keeps what the documents say (country, payment terms,
e-mail, IBAN), as an Odoo partner does, and what the user corrected once
and the app now does by itself, as the matching rules of paperless-ngx:

- a supplier name read another way is filed under the right supplier;
- a delivery method ("Livraison dépôt") gets the meaning the user gave it;
- dates are read the way the supplier writes them, day or month first, from
  its country or from a correction, by code rather than by the AI;
- payment terms and e-mail fill in the documents that do not give them.
"""

import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from rapidfuzz import fuzz
from sqlalchemy.orm import defer
from sqlmodel import Session, col, select

from app.models import (
    DateOrder,
    DeliveryMode,
    Document,
    DocumentKind,
    LearnedRule,
    RuleField,
    Supplier,
)
from app.services.iban import valid_iban
from app.services.payment_terms import due_from_terms
from app.services.reconciliation import SUPPLIER_MATCH, fold

NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})\s*$")
COUNTRY = re.compile(r"^[A-Z]{2}$")
# Month first: the United States. Canada writes both ways: left to the AI.
MONTH_FIRST = {"US"}
EITHER_WAY = {"CA"}
# Left out of the supplier's key, so that "Rexel France SAS" and
# "REXEL FRANCE" are one supplier.
LEGAL_FORMS = {
    "sa", "sas", "sasu", "sarl", "eurl", "sci", "snc", "scop", "selarl",
    "gmbh", "ag", "kg", "ug", "ohg", "ltd", "limited", "plc", "llc", "inc",
    "corp", "bv", "nv", "srl", "spa", "sl",
}  # fmt: skip

DELIVERY_LABELS = {
    DeliveryMode.pickup: "retrait par vous",
    DeliveryMode.standard: "livraison standard",
    DeliveryMode.express: "livraison express",
}
ORDER_LABELS = {
    DateOrder.day_first: "jour/mois (08/01 = 8 janvier)",
    DateOrder.month_first: "mois/jour (08/01 = 1er août)",
}


def supplier_key(name: str) -> str:
    # « S.A.S. » is SAS.
    words = fold(name.replace(".", "")).split()
    kept = [w for w in words if w not in LEGAL_FORMS]
    return " ".join(kept or words)[:255]


def to_country(value: str | None) -> str | None:
    code = (value or "").strip().upper()
    return code if COUNTRY.match(code) else None


def country_of(country: str | None, iban: str | None) -> str | None:
    """The country the AI read on the address, else the IBAN's."""
    if code := to_country(country):
        return code
    if iban and valid_iban(iban):
        return iban[:2]
    return None


def date_order_of(supplier: Supplier | None) -> DateOrder | None:
    if supplier is None:
        return None
    if supplier.date_order:
        return supplier.date_order
    if not supplier.country or supplier.country in EITHER_WAY:
        return None
    if supplier.country in MONTH_FIRST:
        return DateOrder.month_first
    return DateOrder.day_first


def read_date(raw: str | None, order: DateOrder | None) -> date | None:
    """08/01/2026 read day first or month first. None if not numeric."""
    match = NUMERIC_DATE.match(raw or "")
    if not match or order is None:
        return None
    first, second, year = int(match[1]), int(match[2]), int(match[3])
    if year < 100:
        year += 2000
    day, month = (first, second) if order == DateOrder.day_first else (second, first)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def order_from_correction(raw: str | None, corrected: date | None) -> DateOrder | None:
    """The way of writing dates that turns the printed date into the right one."""
    if corrected is None:
        return None
    readings = [order for order in DateOrder if read_date(raw, order) == corrected]
    # 05/05 reads the same both ways: it says nothing.
    return readings[0] if len(readings) == 1 else None


def match_supplier(suppliers: Sequence[Supplier], key: str) -> Supplier | None:
    for supplier in suppliers:
        if supplier.key == key:
            return supplier
    best = max(
        ((fuzz.token_set_ratio(key, supplier.key), supplier) for supplier in suppliers),
        key=lambda pair: pair[0],
        default=None,
    )
    return best[1] if best and best[0] >= SUPPLIER_MATCH else None


def find_supplier(session: Session, owner_id: uuid.UUID, name: str) -> Supplier | None:
    suppliers = session.exec(
        select(Supplier).where(Supplier.owner_id == owner_id)
    ).all()
    return match_supplier(suppliers, supplier_key(name))


def learned_name(session: Session, owner_id: uuid.UUID, name: str | None) -> str | None:
    """The supplier a name read another way was corrected to."""
    if not name:
        return None
    rule = session.exec(
        select(LearnedRule).where(
            LearnedRule.owner_id == owner_id,
            LearnedRule.field == RuleField.supplier,
            LearnedRule.seen == fold(name),
        )
    ).first()
    if rule is None:
        return None
    supplier = session.get(Supplier, rule.supplier_id)
    return supplier.name if supplier else rule.value


def link_supplier(
    session: Session, document: Document, country: str | None = None
) -> Supplier | None:
    """Files the document under its supplier, created the first time."""
    if not document.supplier:
        document.supplier_id = None
        return None
    supplier = find_supplier(session, document.owner_id, document.supplier)
    if supplier is None:
        supplier = Supplier(
            owner_id=document.owner_id,
            name=document.supplier,
            key=supplier_key(document.supplier),
        )
    if not supplier.country:
        supplier.country = country_of(country, document.iban)
    session.add(supplier)
    session.flush()
    document.supplier_id = supplier.id
    return supplier


@dataclass
class Knowledge:
    date_order: DateOrder | None = None
    delivery_modes: dict[str, DeliveryMode] = field(default_factory=dict)
    payment_terms: str | None = None
    email: str | None = None


def knowledge_of(session: Session, supplier: Supplier) -> Knowledge:
    rules = session.exec(
        select(LearnedRule).where(
            LearnedRule.supplier_id == supplier.id,
            LearnedRule.field == RuleField.delivery_mode,
        )
    ).all()
    return Knowledge(
        date_order=date_order_of(supplier),
        delivery_modes={
            rule.seen: DeliveryMode(rule.value)
            for rule in rules
            if rule.value in DeliveryMode.__members__.values()
        },
        payment_terms=supplier.payment_terms,
        email=supplier.email,
    )


def apply_knowledge(
    document: Document, knowledge: Knowledge, due_printed: bool
) -> None:
    """What the supplier's page says, on a document just read (pure)."""
    if not document.from_einvoice:
        read = read_date(document.date_raw, knowledge.date_order)
        if read is not None:
            document.document_date = read
    if document.delivery_method:
        mode = knowledge.delivery_modes.get(fold(document.delivery_method))
        if mode is not None:
            document.delivery_mode = mode
    if document.kind == DocumentKind.invoice and not document.payment_terms:
        document.payment_terms = knowledge.payment_terms
    if not due_printed:
        document.due_date = due_from_terms(
            document.payment_terms, document.document_date
        )
    if not document.supplier_email:
        document.supplier_email = knowledge.email


def remember(
    session: Session,
    document: Document,
    country: str | None = None,
    due_printed: bool = False,
) -> DateOrder | None:
    """Files a document just read and applies what is known of its supplier.

    Returns how its dates are written, when known.
    """
    if name := learned_name(session, document.owner_id, document.supplier):
        document.supplier = name
    supplier = link_supplier(session, document, country)
    if supplier is None:
        return None
    knowledge = knowledge_of(session, supplier)
    apply_knowledge(document, knowledge, due_printed)
    fill_from(supplier, document)
    session.add(supplier)
    return knowledge.date_order


def fill_from(supplier: Supplier, document: Document) -> None:
    """What the supplier's page does not know yet, from one of its documents.

    The IBAN is the first one met: a later, different one is the change the
    IBAN check warns about, until someone confirms it.
    """
    if not supplier.email and document.supplier_email:
        supplier.email = document.supplier_email
    if document.kind != DocumentKind.invoice:
        return
    if not supplier.payment_terms and document.payment_terms:
        supplier.payment_terms = document.payment_terms
    if not supplier.iban and document.iban and valid_iban(document.iban):
        supplier.iban = document.iban


def save_rule(
    session: Session,
    supplier: Supplier,
    rule_field: RuleField,
    written: str,
    value: str,
) -> None:
    seen = fold(written)
    query = select(LearnedRule).where(
        LearnedRule.owner_id == supplier.owner_id,
        LearnedRule.field == rule_field,
        LearnedRule.seen == seen,
    )
    if rule_field != RuleField.supplier:
        # A delivery method means something for one supplier only.
        query = query.where(LearnedRule.supplier_id == supplier.id)
    for old in session.exec(query).all():
        session.delete(old)
    session.flush()
    session.add(
        LearnedRule(
            owner_id=supplier.owner_id,
            supplier_id=supplier.id,
            field=rule_field,
            seen=seen,
            written=written[:255],
            value=value,
        )
    )


@dataclass
class Before:
    """A document as the AI read it, before the user corrected it."""

    supplier: str | None
    document_date: date | None
    delivery_mode: DeliveryMode | None
    payment_terms: str | None
    supplier_email: str | None

    @classmethod
    def of(cls, document: Document) -> Before:
        return cls(
            supplier=document.supplier,
            document_date=document.document_date,
            delivery_mode=document.delivery_mode,
            payment_terms=document.payment_terms,
            supplier_email=document.supplier_email,
        )


def learn(session: Session, document: Document, before: Before) -> list[str]:
    """Keeps what a correction teaches about the supplier, and says it."""
    learned: list[str] = []
    renamed = bool(
        before.supplier
        and document.supplier
        and fold(before.supplier) != fold(document.supplier)
    )
    supplier = link_supplier(session, document)
    if supplier is None:
        return learned
    if renamed and before.supplier:
        save_rule(session, supplier, RuleField.supplier, before.supplier, supplier.name)
        learned.append(f"« {before.supplier} » sera rangé chez {supplier.name}")

    if (
        document.delivery_mode
        and document.delivery_mode != before.delivery_mode
        and document.delivery_method
    ):
        save_rule(
            session,
            supplier,
            RuleField.delivery_mode,
            document.delivery_method,
            document.delivery_mode.value,
        )
        learned.append(
            f"Chez {supplier.name}, « {document.delivery_method} » veut dire"
            f" {DELIVERY_LABELS[document.delivery_mode]}"
        )

    if document.document_date != before.document_date:
        order = order_from_correction(document.date_raw, document.document_date)
        if order and order != date_order_of(supplier):
            supplier.date_order = order
            learned.append(f"{supplier.name} écrit les dates en {ORDER_LABELS[order]}")

    terms = document.payment_terms
    if (
        document.kind == DocumentKind.invoice
        and terms
        and terms != before.payment_terms
        and terms != supplier.payment_terms
    ):
        supplier.payment_terms = terms
        learned.append(f"Conditions de paiement de {supplier.name} : {terms}")

    email = document.supplier_email
    if email and email != before.supplier_email and email != supplier.email:
        supplier.email = email
        learned.append(f"E-mail de {supplier.name} : {email}")

    session.add(supplier)
    return learned


def rule_label(rule: LearnedRule, supplier: Supplier) -> str:
    if rule.field == RuleField.supplier:
        return f"Un nom lu « {rule.written} » est rangé chez {supplier.name}"
    mode = DeliveryMode(rule.value)
    return f"« {rule.written} » veut dire {DELIVERY_LABELS[mode]}"


def ensure_suppliers(session: Session, owner_id: uuid.UUID) -> None:
    """Files the documents read before suppliers existed."""
    unfiled = session.exec(
        select(Document)
        .where(
            Document.owner_id == owner_id,
            col(Document.supplier_id).is_(None),
            col(Document.supplier).is_not(None),
        )
        .options(defer(Document.file))  # type: ignore[arg-type]
    ).all()
    unfiled = sorted(unfiled, key=lambda d: d.document_date or date.min)
    for document in unfiled:
        if supplier := link_supplier(session, document):
            fill_from(supplier, document)
        session.add(document)
    if unfiled:
        session.commit()


def documents_of(session: Session, supplier: Supplier) -> Iterable[Document]:
    return session.exec(
        select(Document)
        .where(
            Document.owner_id == supplier.owner_id,
            Document.supplier_id == supplier.id,
        )
        .options(defer(Document.file))  # type: ignore[arg-type]
    ).all()
