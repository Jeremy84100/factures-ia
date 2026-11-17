import uuid
from datetime import date
from decimal import Decimal

from app.models import Document, DocumentKind, DocumentStatus
from app.services.checks import check_invoice, review_extraction
from app.services.extraction import ExtractedInvoice

TODAY = date(2026, 11, 16)


def make_invoice(**fields: object) -> Document:
    values: dict[str, object] = {
        "kind": DocumentKind.invoice,
        "filename": "a.pdf",
        "file": b"",
        "owner_id": uuid.uuid4(),
        "supplier": "EDF",
        "number": "1",
        "document_date": date(2026, 3, 4),
        "amount_excl_tax": Decimal("70.17"),
        "vat_amount": Decimal("14.03"),
        "amount_incl_tax": Decimal("84.20"),
    }
    values.update(fields)
    return Document(**values)


def test_valid_invoice_is_ok() -> None:
    assert check_invoice(make_invoice(), None, TODAY) == (DocumentStatus.ok, [])


def test_rounding_cent_is_tolerated() -> None:
    invoice = make_invoice(amount_incl_tax=Decimal("84.21"))
    assert check_invoice(invoice, None, TODAY)[0] == DocumentStatus.ok


def test_wrong_total_needs_check() -> None:
    status, issues = check_invoice(
        make_invoice(amount_incl_tax=Decimal("842.00")), None, TODAY
    )
    assert status == DocumentStatus.to_check
    assert issues == ["HT + TVA = 84.20 mais TTC = 842.00"]


def test_missing_fields_is_unreadable() -> None:
    status, issues = check_invoice(
        make_invoice(supplier=None, amount_incl_tax=None), None, TODAY
    )
    assert status == DocumentStatus.unreadable
    assert issues == ["Champ introuvable : fournisseur, montant TTC"]


def test_total_alone_is_readable_but_needs_vat() -> None:
    invoice = make_invoice(amount_excl_tax=None, vat_amount=None)
    assert check_invoice(invoice, None, TODAY) == (
        DocumentStatus.to_check,
        ["Montant de TVA introuvable"],
    )


def test_future_date_needs_check() -> None:
    status, issues = check_invoice(
        make_invoice(document_date=date(2027, 1, 1)), None, TODAY
    )
    assert status == DocumentStatus.to_check
    assert issues == ["Date dans le futur"]


NEGATIVE = {
    "amount_excl_tax": Decimal("-10"),
    "vat_amount": Decimal("-2"),
    "amount_incl_tax": Decimal("-12"),
}


def test_negative_invoice_needs_check() -> None:
    assert check_invoice(make_invoice(**NEGATIVE), None, TODAY)[1] == [
        "Montant négatif sur une facture (avoir ?)"
    ]


def test_negative_credit_note_is_ok() -> None:
    invoice = make_invoice(**NEGATIVE, is_credit_note=True)
    assert check_invoice(invoice, None, TODAY) == (DocumentStatus.ok, [])


ZERO_VAT = {
    "amount_excl_tax": Decimal("530.75"),
    "vat_amount": Decimal("0"),
    "amount_incl_tax": Decimal("530.75"),
}


def test_zero_vat_without_mention_needs_check() -> None:
    assert check_invoice(make_invoice(**ZERO_VAT), None, TODAY)[1] == [
        "TVA à 0 sans mention d'exonération"
    ]


def test_zero_vat_with_mention_is_ok() -> None:
    invoice = make_invoice(**ZERO_VAT, vat_exemption="Article 262 I du CGI")
    assert check_invoice(invoice, None, TODAY) == (DocumentStatus.ok, [])


def test_missing_vat_needs_check() -> None:
    invoice = make_invoice(**{**ZERO_VAT, "vat_amount": None})
    assert check_invoice(invoice, None, TODAY)[1] == ["Montant de TVA introuvable"]


def test_missing_vat_with_mention_is_ok() -> None:
    invoice = make_invoice(vat_amount=None, vat_exemption="TVA incluse")
    assert check_invoice(invoice, None, TODAY) == (DocumentStatus.ok, [])


def test_same_number_other_amount_is_reported_separately() -> None:
    other = make_invoice(filename="autre.pdf", amount_incl_tax=Decimal("99.00"))
    assert check_invoice(make_invoice(), other, TODAY)[1] == [
        "Même numéro que « autre.pdf » mais un autre montant"
    ]


def test_duplicate_needs_check() -> None:
    other = make_invoice(filename="edf-mars.pdf")
    status, issues = check_invoice(make_invoice(), other, TODAY)
    assert status == DocumentStatus.to_check
    assert issues == ["Doublon possible de « edf-mars.pdf »"]


def us_invoice(raw: str, iso: str) -> ExtractedInvoice:
    return ExtractedInvoice(invoice_date_raw=raw, invoice_date=iso, currency="USD")


def test_us_date_read_day_first_is_reported() -> None:
    assert review_extraction(us_invoice("06/02/2015", "2015-02-06")) == [
        "Date « 06/02/2015 » à vérifier : jour et mois peuvent être inversés"
    ]


def test_us_date_read_month_first_is_trusted() -> None:
    assert review_extraction(us_invoice("06/02/2015", "2015-06-02")) == []


def test_unambiguous_or_european_dates_are_trusted() -> None:
    assert review_extraction(us_invoice("09/18/2015", "2015-09-18")) == []
    euro = ExtractedInvoice(
        invoice_date_raw="06/02/2015", invoice_date="2015-02-06", currency="EUR"
    )
    assert review_extraction(euro) == []


def test_extraction_issues_send_to_review() -> None:
    status, issues = check_invoice(
        make_invoice(),
        None,
        TODAY,
        extraction_issues=["Date « 06/02/2015 » à vérifier"],
    )
    assert status == DocumentStatus.to_check
    assert issues == ["Date « 06/02/2015 » à vérifier"]
