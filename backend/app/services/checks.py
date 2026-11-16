from datetime import date
from decimal import Decimal

from app.models import Invoice, InvoiceStatus

TOLERANCE = Decimal("0.02")

REQUIRED_FIELDS = {
    "supplier": "fournisseur",
    "invoice_date": "date",
    "amount_incl_tax": "montant TTC",
}


def check_invoice(
    invoice: Invoice, duplicate_of: Invoice | None, today: date | None = None
) -> tuple[InvoiceStatus, list[str]]:
    missing = [
        label
        for field, label in REQUIRED_FIELDS.items()
        if getattr(invoice, field) is None
    ]
    if missing:
        return InvoiceStatus.unreadable, [f"Champ introuvable : {', '.join(missing)}"]

    issues: list[str] = []
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
