import re
from datetime import date
from decimal import Decimal

from app.models import Document, DocumentStatus
from app.services.extraction import ExtractedDocument

TOLERANCE = Decimal("0.02")
DUPLICATE_OF = "Doublon possible de"
SAME_NUMBER_AS = "Même numéro que"
NUMBER_ISSUES = (DUPLICATE_OF, SAME_NUMBER_AS)


def number_issue(invoice: Document, other: Document) -> str:
    if other.amount_incl_tax == invoice.amount_incl_tax:
        return f"{DUPLICATE_OF} « {other.filename} »"
    return f"{SAME_NUMBER_AS} « {other.filename} » mais un autre montant"


MONTH_FIRST_CURRENCIES = {"USD"}
NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\s*$")

REQUIRED_FIELDS = {
    "supplier": "fournisseur",
    "document_date": "date",
    "amount_incl_tax": "montant TTC",
}


def ambiguous_date(extracted: ExtractedDocument) -> str | None:
    raw = extracted.date_raw or ""
    match = NUMERIC_DATE.match(raw)
    if not match or (extracted.currency or "").upper() not in MONTH_FIRST_CURRENCIES:
        return None
    first, second = int(match[1]), int(match[2])
    if first > 12 or second > 12 or first == second:
        return None
    try:
        if date.fromisoformat(extracted.date or "").month == first:
            return None
    except ValueError:
        pass
    return f"Date « {raw.strip()} » à vérifier : jour et mois peuvent être inversés"


def review_extraction(extracted: ExtractedDocument) -> list[str]:
    date_issue = ambiguous_date(extracted)
    return [date_issue] if date_issue else []


def check_invoice(
    invoice: Document,
    duplicate_of: Document | None,
    today: date | None = None,
    extraction_issues: list[str] | None = None,
) -> tuple[DocumentStatus, list[str]]:
    missing = [
        label
        for field, label in REQUIRED_FIELDS.items()
        if getattr(invoice, field) is None
    ]
    if missing:
        return DocumentStatus.unreadable, [f"Champ introuvable : {', '.join(missing)}"]

    issues = list(extraction_issues or [])
    excl, vat, incl = (
        invoice.amount_excl_tax,
        invoice.vat_amount,
        invoice.amount_incl_tax,
    )

    if excl is not None and vat is not None and incl is not None:
        if abs(excl + vat - incl) > TOLERANCE:
            issues.append(f"HT + TVA = {excl + vat} mais TTC = {incl}")

    amounts = [amount for amount in (excl, vat, incl) if amount is not None]
    if not invoice.is_credit_note and any(amount < 0 for amount in amounts):
        issues.append("Montant négatif sur une facture (avoir ?)")

    if incl and not invoice.vat_exemption:
        if vat == 0:
            issues.append("TVA à 0 sans mention d'exonération")
        elif vat is None:
            issues.append("Montant de TVA introuvable")

    if invoice.document_date and invoice.document_date > (today or date.today()):
        issues.append("Date dans le futur")

    if duplicate_of is not None:
        issues.append(number_issue(invoice, duplicate_of))

    return (DocumentStatus.to_check if issues else DocumentStatus.ok), issues
