import uuid
from datetime import date
from decimal import Decimal

from app.models import Document, DocumentKind, DocumentLine, DocumentStatus
from app.services.checks import (
    NO_LINES,
    NO_ORDER_REFERENCE,
    NOT_A_PURCHASE_DOCUMENT,
    PROMISED_BEFORE_ORDER,
    check_document,
)

TODAY = date(2026, 11, 17)


def line(
    reference: str = "CAB-3G25",
    quantity: str = "50",
    unit_price: str | None = "1.19",
    amount: str | None = "59.50",
) -> DocumentLine:
    return DocumentLine(
        reference=reference,
        description="Câble R2V 3G2,5",
        quantity=Decimal(quantity),
        unit_price=None if unit_price is None else Decimal(unit_price),
        amount_excl_tax=None if amount is None else Decimal(amount),
    )


def make(kind: DocumentKind, **fields: object) -> Document:
    values: dict[str, object] = {
        "kind": kind,
        "filename": "doc.pdf",
        "file": b"",
        "owner_id": uuid.uuid4(),
        "supplier": "Rexel",
        "number": "CMD-2041",
        "document_date": date(2026, 10, 2),
        "amount_excl_tax": Decimal("59.50"),
        "lines": [line()],
    }
    values.update(fields)
    return Document(**values)


def make_delivery(**fields: object) -> Document:
    values: dict[str, object] = {
        "number": "BL-88",
        "order_reference": "CMD-2041",
        "amount_excl_tax": None,
        "lines": [line(unit_price=None, amount=None)],
    }
    values.update(fields)
    return make(DocumentKind.delivery, **values)


def test_unknown_document_is_unreadable() -> None:
    assert check_document(make(DocumentKind.unknown), None, TODAY) == (
        DocumentStatus.unreadable,
        [NOT_A_PURCHASE_DOCUMENT],
    )


def test_valid_order_is_ok() -> None:
    assert check_document(make(DocumentKind.order), None, TODAY) == (
        DocumentStatus.ok,
        [],
    )


def test_order_without_number_is_unreadable() -> None:
    order = make(DocumentKind.order, number=None, supplier=None)
    assert check_document(order, None, TODAY) == (
        DocumentStatus.unreadable,
        ["Champ introuvable : fournisseur, numéro"],
    )


def test_order_does_not_need_a_total_incl_tax() -> None:
    order = make(DocumentKind.order, amount_incl_tax=None, amount_excl_tax=None)
    assert check_document(order, None, TODAY)[0] == DocumentStatus.ok


def test_order_without_lines_needs_check() -> None:
    order = make(DocumentKind.order, lines=[])
    assert check_document(order, None, TODAY) == (DocumentStatus.to_check, [NO_LINES])


def test_zero_quantity_needs_check() -> None:
    order = make(DocumentKind.order, lines=[line(quantity="0", amount="0")])
    order.amount_excl_tax = Decimal("0")
    assert check_document(order, None, TODAY) == (
        DocumentStatus.to_check,
        ["CAB-3G25 : quantité 0"],
    )


def test_line_amount_must_match_quantity_times_price() -> None:
    order = make(DocumentKind.order, lines=[line(amount="95.20")])
    order.amount_excl_tax = Decimal("95.20")
    assert check_document(order, None, TODAY) == (
        DocumentStatus.to_check,
        ["CAB-3G25 : 50 × 1.19 = 59.50 mais montant = 95.20"],
    )


def test_line_rounding_cent_is_tolerated() -> None:
    order = make(DocumentKind.order, lines=[line(quantity="3", unit_price="0.333")])
    order.lines[0].amount_excl_tax = Decimal("1.00")
    order.amount_excl_tax = Decimal("1.00")
    assert check_document(order, None, TODAY)[0] == DocumentStatus.ok


def test_lines_must_add_up_to_total() -> None:
    order = make(DocumentKind.order, amount_excl_tax=Decimal("70.00"))
    assert check_document(order, None, TODAY) == (
        DocumentStatus.to_check,
        ["Somme des lignes = 59.50 mais total HT = 70.00 (remise globale ?)"],
    )


def test_line_without_label_gets_its_position() -> None:
    unnamed = line(quantity="0", amount="0")
    unnamed.reference = None
    unnamed.description = None
    order = make(DocumentKind.order, lines=[line(), unnamed])
    issues = check_document(order, None, TODAY)[1]
    assert "Ligne 2 : quantité 0" in issues


def test_valid_delivery_is_ok() -> None:
    assert check_document(make_delivery(), None, TODAY) == (DocumentStatus.ok, [])


def test_delivery_without_order_reference_must_be_linked() -> None:
    delivery = make_delivery(order_reference=None)
    assert check_document(delivery, None, TODAY) == (
        DocumentStatus.to_check,
        [NO_ORDER_REFERENCE],
    )


def test_delivery_without_lines_needs_check() -> None:
    delivery = make_delivery(lines=[])
    assert check_document(delivery, None, TODAY)[1] == [NO_LINES]


def test_delivery_without_date_is_unreadable() -> None:
    delivery = make_delivery(document_date=None)
    assert check_document(delivery, None, TODAY)[0] == DocumentStatus.unreadable


def test_future_delivery_needs_check() -> None:
    delivery = make_delivery(document_date=date(2027, 1, 5))
    assert check_document(delivery, None, TODAY)[1] == ["Date dans le futur"]


def test_duplicate_order_number_needs_check() -> None:
    first = make(DocumentKind.order, filename="commande.pdf")
    second = make(DocumentKind.order)
    assert check_document(second, first, TODAY) == (
        DocumentStatus.to_check,
        ["Doublon possible de « commande.pdf »"],
    )


def invoice(**fields: object) -> Document:
    values: dict[str, object] = {
        "number": "FA-501",
        "order_reference": "CMD-2041",
        "vat_amount": Decimal("11.90"),
        "amount_incl_tax": Decimal("71.40"),
    }
    values.update(fields)
    return make(DocumentKind.invoice, **values)


def test_invoice_with_lines_is_ok() -> None:
    assert check_document(invoice(), None, TODAY) == (DocumentStatus.ok, [])


def test_invoice_lines_must_add_up_to_total() -> None:
    wrong = invoice(lines=[line(), line(reference="ICTA-20", amount="95.00")])
    issues = check_document(wrong, None, TODAY)[1]
    assert "ICTA-20 : 50 × 1.19 = 59.50 mais montant = 95.00" in issues
    assert (
        "Somme des lignes = 154.50 mais total HT = 59.50 (remise globale ?)" in issues
    )


def test_line_discount_is_not_an_error() -> None:
    discounted = invoice(lines=[line(amount="53.55")], amount_excl_tax=Decimal("53.55"))
    discounted.vat_amount = Decimal("10.71")
    discounted.amount_incl_tax = Decimal("64.26")
    assert check_document(discounted, None, TODAY) == (DocumentStatus.ok, [])


def test_lines_may_add_up_to_total_incl_tax() -> None:
    retail = invoice(
        lines=[line(amount="71.40", unit_price="1.428")],
        amount_excl_tax=Decimal("59.50"),
    )
    assert check_document(retail, None, TODAY)[0] == DocumentStatus.ok


def test_zero_quantity_line_on_an_invoice_is_fine() -> None:
    note = line(reference="Justificatif papier", quantity="0", amount="0")
    assert check_document(invoice(lines=[line(), note]), None, TODAY)[1] == []


def test_credit_note_with_positive_quantities_and_negative_amounts() -> None:
    credit = invoice(
        is_credit_note=True,
        amount_excl_tax=Decimal("-59.50"),
        vat_amount=Decimal("-11.90"),
        amount_incl_tax=Decimal("-71.40"),
        lines=[line(amount="-59.50")],
    )
    assert check_document(credit, None, TODAY) == (DocumentStatus.ok, [])


def test_invoice_without_lines_is_still_checked_as_before() -> None:
    assert check_document(invoice(lines=[]), None, TODAY) == (DocumentStatus.ok, [])


def test_invoice_without_order_reference_is_fine() -> None:
    assert check_document(invoice(order_reference=None), None, TODAY)[0] == (
        DocumentStatus.ok
    )


def test_credit_note_lines_may_be_negative() -> None:
    credit = invoice(
        is_credit_note=True,
        amount_excl_tax=Decimal("-59.50"),
        vat_amount=Decimal("-11.90"),
        amount_incl_tax=Decimal("-71.40"),
        lines=[line(quantity="-50", amount="-59.50")],
    )
    assert check_document(credit, None, TODAY) == (DocumentStatus.ok, [])


def test_promised_delivery_after_the_order_is_fine() -> None:
    order = make(DocumentKind.order, expected_delivery_date=date(2026, 10, 9))
    assert check_document(order, None, TODAY) == (DocumentStatus.ok, [])


def test_promised_delivery_before_the_order_needs_check() -> None:
    order = make(DocumentKind.order, expected_delivery_date=date(2026, 9, 28))
    assert check_document(order, None, TODAY) == (
        DocumentStatus.to_check,
        [PROMISED_BEFORE_ORDER],
    )
