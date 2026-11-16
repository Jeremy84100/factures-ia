import re
from datetime import date
from decimal import Decimal

from app.models import Invoice, InvoiceStatus
from app.services.extraction import ExtractedInvoice

TOLERANCE = Decimal("0.02")
MONTH_FIRST_CURRENCIES = {"USD"}
NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\s*$")

REQUIRED_FIELDS = {
    "supplier": "fournisseur",
    "invoice_date": "date",
    "amount_incl_tax": "montant TTC",
}


def ambiguous_date(extracted: ExtractedInvoice) -> str | None:
    raw = extracted.invoice_date_raw or ""
    match = NUMERIC_DATE.match(raw)
    if not match or (extracted.currency or "").upper() not in MONTH_FIRST_CURRENCIES:
        return None
    first, second = int(match[1]), int(match[2])
    if first > 12 or second > 12 or first == second:
        return None
    try:
        if date.fromisoformat(extracted.invoice_date or "").month == first:
            return None
    except ValueError:
        pass
    return f"Date « {raw.strip()} » à vérifier : jour et mois peuvent être inversés"


def review_extraction(extracted: ExtractedInvoice) -> list[str]:
    date_issue = ambiguous_date(extracted)
    return [date_issue] if date_issue else []


def check_invoice(
    invoice: Invoice,
    duplicate_of: Invoice | None,
    today: date | None = None,
    extraction_issues: list[str] | None = None,
) -> tuple[InvoiceStatus, list[str]]:
    missing = [
        label
        for field, label in REQUIRED_FIELDS.items()
        if getattr(invoice, field) is None
    ]
    if missing:
        return InvoiceStatus.unreadable, [f"Champ introuvable : {', '.join(missing)}"]

    issues = list(extraction_issues or [])
    excl, vat, incl = (
        invoice.amount_excl_tax,
        invoice.vat_amount,
        invoice.amount_incl_tax,
    )

    if excl is not None and vat is not None and incl is not None:
        if abs(excl + vat - incl) > TOLERANCE:
            issues.append(f"HT + TVA = {excl + vat} mais TTC = {incl}")

    if any(amount is not None and amount < 0 for amount in (excl, vat, incl)):
        issues.append("Montant négatif (avoir ?)")

    if invoice.invoice_date and invoice.invoice_date > (today or date.today()):
        issues.append("Date dans le futur")

    if duplicate_of is not None:
        issues.append(f"Doublon possible de « {duplicate_of.filename} »")

    return (InvoiceStatus.to_check if issues else InvoiceStatus.ok), issues
