import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.models import Document, DocumentKind, DocumentLine, DocumentStatus
from app.services.checks import check_document
from app.services.reconciliation import build_purchases, reference_key

FIXTURES = Path(__file__).parent.parent / "fixtures" / "purchases"
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
        amount_excl_tax=to_decimal(case["amount_excl_tax"]),
        currency="EUR",
        lines=lines,
    )
    if document.kind == DocumentKind.invoice:
        excl = document.amount_excl_tax or Decimal(0)
        document.vat_amount = (excl * Decimal("0.2")).quantize(Decimal("0.01"))
        document.amount_incl_tax = excl + document.vat_amount
    document.status = check_document(document, None, TODAY)[0]
    return document


def test_demo_purchases_get_the_expected_verdict() -> None:
    documents = [as_read_perfectly(case) for case in EXPECTED["documents"]]
    assert {d.status for d in documents} <= {DocumentStatus.ok, DocumentStatus.to_check}

    result = build_purchases(documents)
    verdicts = {p.key: p.status.value for p in result.data}
    expected = {
        reference_key(p["order_reference"]): p["status"] for p in EXPECTED["purchases"]
    }
    assert verdicts == expected

    unlinked = sorted(ref.number or "" for ref in result.unlinked)
    assert unlinked == sorted(n for p in EXPECTED["purchases"] for n in p["unlinked"])
