import uuid
from datetime import date

from app.models import Document, DocumentKind, DocumentStatus
from app.services.checks import check_document
from app.services.iban import INVALID_IBAN, clean_iban, iban_change, valid_iban

USUAL = "FR7630006000011234567890189"
OTHER = "FR7699999000120000000000241"


def invoice(iban: str, day: date, number: str = "F-1") -> Document:
    return Document(
        kind=DocumentKind.invoice,
        filename=f"{number}.pdf",
        file=b"",
        owner_id=uuid.uuid4(),
        status=DocumentStatus.ok,
        supplier="Location Matériel Vaucluse",
        number=number,
        document_date=day,
        amount_excl_tax=100,
        vat_amount=20,
        amount_incl_tax=120,
        iban=iban,
    )


def test_clean_and_check() -> None:
    assert clean_iban("fr76 3000 6000 0112 3456 7890 189") == USUAL
    assert clean_iban("") is None
    assert valid_iban(USUAL)
    assert not valid_iban(USUAL[:-1] + "8")
    assert not valid_iban("FR76")


def test_same_iban_is_fine() -> None:
    old = invoice(USUAL, date(2026, 10, 5), "F-1")
    new = invoice(USUAL, date(2026, 11, 5), "F-2")
    assert iban_change(new, [old]) is None


def test_new_iban_is_flagged_on_the_newer_invoice_only() -> None:
    old = invoice(USUAL, date(2026, 10, 5), "F-1")
    new = invoice(OTHER, date(2026, 11, 5), "F-2")
    issue = iban_change(new, [old, new])
    assert issue is not None
    assert issue.startswith(
        "Nouvel IBAN : finit par 0241, la facture F-1 du 05/10/2026"
    )
    assert iban_change(old, [old, new]) is None


def test_another_supplier_is_not_compared() -> None:
    old = invoice(USUAL, date(2026, 10, 5))
    old.supplier = "Électro Provence Distribution"
    assert iban_change(invoice(OTHER, date(2026, 11, 5)), [old]) is None


def test_a_wrong_iban_is_to_check() -> None:
    document = invoice(USUAL[:-1] + "8", date(2026, 10, 5))
    status, issues = check_document(document, None, date(2026, 11, 1))
    assert status == DocumentStatus.to_check
    assert INVALID_IBAN in issues
