import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.models import (
    DeliveryMode,
    Document,
    DocumentKind,
    DocumentLine,
    DocumentStatus,
    PurchaseStatus,
)
from app.services.checks import check_document
from app.services.demo import check_ibans
from app.services.reconciliation import build_purchases, reference_key

FIXTURES = Path(__file__).parents[2] / "app" / "demo" / "purchases"
EXPECTED: dict[str, Any] = json.loads(
    (FIXTURES / "expected.json").read_text(encoding="utf-8")
)
TODAY = date(2026, 11, 17)
OWNER = uuid.uuid4()


def to_decimal(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def as_read_perfectly(case: dict[str, Any]) -> Document:
    lines = []
    for position, line in enumerate(case["lines"]):
        price = to_decimal(line["unit_price"])
        quantity = Decimal(str(line["quantity"]))
        amount = None if price is None else (quantity * price).quantize(Decimal("0.01"))
        lines.append(
            DocumentLine(
                position=position,
                reference=line["reference"],
                description=line.get("description") or line["reference"],
                quantity=quantity,
                unit_price=price,
                amount_excl_tax=amount,
            )
        )
    document = Document(
        kind=DocumentKind(case["kind"]),
        filename=case["filename"],
        file=b"",
        owner_id=OWNER,
        supplier=case["supplier"],
        number=case["number"],
        document_date=date.fromisoformat(case["date"]),
        order_reference=case["order_reference"],
        delivery_mode=DeliveryMode(case["delivery_mode"])
        if case["delivery_mode"]
        else None,
        expected_delivery_date=date.fromisoformat(case["expected_delivery_date"])
        if case["expected_delivery_date"]
        else None,
        amount_excl_tax=to_decimal(case["amount_excl_tax"]),
        payment_terms=case["payment_terms"],
        iban=case["iban"],
        supplier_email=case["supplier_email"],
        due_date=date.fromisoformat(case["due_date"]) if case["due_date"] else None,
        currency="EUR",
        lines=lines,
    )
    if document.kind == DocumentKind.invoice:
        excl = document.amount_excl_tax or Decimal(0)
        document.vat_amount = (excl * Decimal("0.2")).quantize(Decimal("0.01"))
        document.amount_incl_tax = excl + document.vat_amount
    document.status = check_document(document, None, TODAY)[0]
    return document


def all_read_perfectly() -> list[Document]:
    documents = [as_read_perfectly(case) for case in EXPECTED["documents"]]
    check_ibans(documents)
    return documents


def test_demo_purchases_get_the_expected_verdict() -> None:
    documents = all_read_perfectly()
    assert {d.status for d in documents} <= {DocumentStatus.ok, DocumentStatus.to_check}

    result = build_purchases(documents, TODAY)
    verdicts = {reference_key(p.order_reference): p.status.value for p in result.data}
    expected = {
        reference_key(p["order_reference"]): p["status"] for p in EXPECTED["purchases"]
    }
    assert verdicts == expected

    unlinked = sorted(ref.number or "" for ref in result.unlinked)
    assert unlinked == sorted(n for p in EXPECTED["purchases"] for n in p["unlinked"])


def test_demo_delivery_problems_are_explained() -> None:
    documents = all_read_perfectly()
    purchases = {p.key: p for p in build_purchases(documents, TODAY).data}

    late = purchases["CMD26109"]
    assert late.notes == [
        "BL-CL-4471 livré le 19/10/2026, 7 jours après la date promise (12/10/2026)"
    ]
    express = purchases["CMD26110"]
    assert express.issues == [
        "Mode de livraison du BL-IVP-2208 : « livraison standard » au lieu de"
        " « livraison express » commandé"
    ]
    assert [line.issues for line in express.lines] == [[], [], []]


def test_demo_payment_dates() -> None:
    documents = all_read_perfectly()
    purchases = {p.order_reference: p for p in build_purchases(documents, TODAY).data}

    # 45 days after the 04/10 invoice.
    assert purchases["CMD-26-101"].due_date == date(2026, 11, 18)
    assert not purchases["CMD-26-101"].due_date_assumed
    # Nothing written on the invoice: the legal 30 days.
    assert purchases["CMD-26-108"].due_date == date(2026, 11, 14)
    assert purchases["CMD-26-108"].due_date_assumed
    # A subscription: one invoice, nothing to compare, still to pay.
    alone = purchases["TPP-2611-0458"]
    assert alone.status == PurchaseStatus.to_pay
    assert alone.invoice_only
    assert alone.to_pay_incl_tax == Decimal("143.84")
    assert alone.due_date == date(2026, 11, 20)


def test_demo_unlinked_delivery_is_not_called_late() -> None:
    documents = all_read_perfectly()
    result = build_purchases(documents, TODAY)
    paint = next(p for p in result.data if p.order_reference == "CMD-26-107")
    assert not paint.late
    assert paint.notes == [
        "Le bon de livraison BL-PM-6620 de ce fournisseur n'est pas rangé :"
        " c'est peut-être cette livraison"
    ]
    (unlinked,) = result.unlinked
    assert [s.order_reference for s in unlinked.suggestions] == ["CMD-26-107"]


def test_demo_changed_iban_waits_for_a_call() -> None:
    purchases = {
        p.order_reference: p for p in build_purchases(all_read_perfectly(), TODAY).data
    }
    usual = purchases["LMV-2610-118"]
    assert usual.status == PurchaseStatus.to_pay
    assert usual.iban and usual.supplier_email
    changed = purchases["LMV-2611-131"]
    assert changed.status == PurchaseStatus.waiting
    assert changed.notes[0].startswith("Facture LMV-2611-131 à vérifier : Nouvel IBAN")
    assert "Appelez le fournisseur" in changed.notes[0]
