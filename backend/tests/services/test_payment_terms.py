from datetime import date

import pytest

from app.services.payment_terms import due_from_terms, legal_due_date

INVOICE_DAY = date(2026, 10, 6)


@pytest.mark.parametrize(
    ("terms", "due"),
    [
        ("30 jours", date(2026, 11, 5)),
        ("Paiement à 45 jours", date(2026, 11, 20)),
        ("45 jours fin de mois", date(2026, 11, 30)),
        ("60 j. FDM", date(2026, 12, 31)),
        ("Net 30 days", date(2026, 11, 5)),
        ("À réception de facture", INVOICE_DAY),
        ("Comptant", INVOICE_DAY),
        ("Prélèvement à échéance", None),
        ("", None),
        (None, None),
    ],
)
def test_due_from_terms(terms: str | None, due: date | None) -> None:
    assert due_from_terms(terms, INVOICE_DAY) == due


def test_no_invoice_date_no_due_date() -> None:
    assert due_from_terms("30 jours", None) is None


def test_legal_delay_is_30_days() -> None:
    assert legal_due_date(INVOICE_DAY) == date(2026, 11, 5)
