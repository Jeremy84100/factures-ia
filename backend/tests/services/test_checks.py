import uuid
from datetime import date
from decimal import Decimal

from app.models import Invoice, InvoiceStatus
from app.services.checks import check_invoice

TODAY = date(2026, 11, 16)


def make_invoice(**fields: object) -> Invoice:
    values: dict[str, object] = {
        "filename": "a.pdf",
        "file": b"",
        "owner_id": uuid.uuid4(),
        "supplier": "EDF",
        "invoice_number": "1",
        "invoice_date": date(2026, 3, 4),
        "amount_excl_tax": Decimal("70.17"),
        "vat_amount": Decimal("14.03"),
        "amount_incl_tax": Decimal("84.20"),
    }
    values.update(fields)
    return Invoice(**values)


def test_valid_invoice_is_ok() -> None:
    assert check_invoice(make_invoice(), None, TODAY) == (InvoiceStatus.ok, [])


def test_rounding_cent_is_tolerated() -> None:
    invoice = make_invoice(amount_incl_tax=Decimal("84.21"))
    assert check_invoice(invoice, None, TODAY)[0] == InvoiceStatus.ok


def test_wrong_total_needs_check() -> None:
    status, issues = check_invoice(
        make_invoice(amount_incl_tax=Decimal("842.00")), None, TODAY
    )
    assert status == InvoiceStatus.to_check
    assert issues == ["HT + TVA = 84.20 mais TTC = 842.00"]


def test_missing_fields_is_unreadable() -> None:
    status, issues = check_invoice(
        make_invoice(supplier=None, amount_incl_tax=None), None, TODAY
    )
    assert status == InvoiceStatus.unreadable
    assert issues == ["Champ introuvable : fournisseur, montant TTC"]


def test_total_alone_is_enough() -> None:
    invoice = make_invoice(amount_excl_tax=None, vat_amount=None)
    assert check_invoice(invoice, None, TODAY)[0] == InvoiceStatus.ok


def test_future_date_needs_check() -> None:
    status, issues = check_invoice(
        make_invoice(invoice_date=date(2027, 1, 1)), None, TODAY
    )
    assert status == InvoiceStatus.to_check
    assert issues == ["Date dans le futur"]


def test_negative_amount_needs_check() -> None:
    invoice = make_invoice(
        amount_excl_tax=Decimal("-10"),
        vat_amount=Decimal("-2"),
        amount_incl_tax=Decimal("-12"),
    )
    assert check_invoice(invoice, None, TODAY)[1] == ["Montant négatif (avoir ?)"]


def test_duplicate_needs_check() -> None:
    other = make_invoice(filename="edf-mars.pdf")
    status, issues = check_invoice(make_invoice(), other, TODAY)
    assert status == InvoiceStatus.to_check
    assert issues == ["Doublon possible de « edf-mars.pdf »"]
