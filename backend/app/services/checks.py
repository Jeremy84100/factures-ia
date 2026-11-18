import re
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.models import Document, DocumentKind, DocumentStatus, LineFields
from app.services.extraction import ExtractedDocument

TOLERANCE = Decimal("0.02")
CENT = Decimal("0.01")
DUPLICATE_OF = "Doublon possible de"
SAME_NUMBER_AS = "Même numéro que"
NUMBER_ISSUES = (DUPLICATE_OF, SAME_NUMBER_AS)
NOT_A_PURCHASE_DOCUMENT = "Ni facture, ni bon de commande, ni bon de livraison"
NO_LINES = "Aucune ligne d'article trouvée"
NO_ORDER_REFERENCE = "Numéro de commande introuvable : à relier à une commande"
PROMISED_BEFORE_ORDER = "Date de livraison promise avant la date du document"
DUE_BEFORE_INVOICE = "Échéance avant la date de la facture"


def number_issue(document: Document, other: Document) -> str:
    if other.amount_incl_tax == document.amount_incl_tax:
        return f"{DUPLICATE_OF} « {other.filename} »"
    return f"{SAME_NUMBER_AS} « {other.filename} » mais un autre montant"


MONTH_FIRST_CURRENCIES = {"USD"}
NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\s*$")

HEADER = {"supplier": "fournisseur", "number": "numéro", "document_date": "date"}
REQUIRED_FIELDS = {
    DocumentKind.invoice: {
        "supplier": "fournisseur",
        "document_date": "date",
        "amount_incl_tax": "montant TTC",
    },
    DocumentKind.order: HEADER,
    DocumentKind.delivery: HEADER,
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


def show(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text if text != "-0" else "0"


def line_label(line: LineFields, index: int) -> str:
    return line.reference or line.description or f"Ligne {index + 1}"


def check_lines(lines: Sequence[LineFields], check_quantities: bool) -> list[str]:
    issues = []
    for index, line in enumerate(lines):
        label = line_label(line, index)
        quantity, price, amount = line.quantity, line.unit_price, line.amount_excl_tax
        if check_quantities and quantity is not None and quantity <= 0:
            issues.append(f"{label} : quantité {show(quantity)}")
        if quantity is not None and price is not None and amount is not None:
            expected = abs(quantity * price).quantize(CENT)
            if abs(amount) > expected + TOLERANCE:
                issues.append(
                    f"{label} : {show(quantity)} × {show(price)} = {expected}"
                    f" mais montant = {amount}"
                )
    return issues


def check_lines_total(
    lines: Sequence[LineFields],
    total_excl_tax: Decimal | None,
    total_incl_tax: Decimal | None = None,
) -> str | None:
    amounts = [line.amount_excl_tax for line in lines]
    if not amounts or total_excl_tax is None or None in amounts:
        return None
    lines_total = sum((a for a in amounts if a is not None), Decimal(0))
    totals = [t for t in (total_excl_tax, total_incl_tax) if t is not None]
    if all(abs(abs(lines_total) - abs(total)) > TOLERANCE for total in totals):
        return (
            f"Somme des lignes = {lines_total} mais total HT = {total_excl_tax}"
            " (remise globale ?)"
        )
    return None


def check_invoice_amounts(document: Document) -> list[str]:
    issues = []
    excl, vat, incl = (
        document.amount_excl_tax,
        document.vat_amount,
        document.amount_incl_tax,
    )

    if excl is not None and vat is not None and incl is not None:
        if abs(excl + vat - incl) > TOLERANCE:
            issues.append(f"HT + TVA = {excl + vat} mais TTC = {incl}")

    amounts = [amount for amount in (excl, vat, incl) if amount is not None]
    if not document.is_credit_note and any(amount < 0 for amount in amounts):
        issues.append("Montant négatif sur une facture (avoir ?)")

    if incl and not document.vat_exemption:
        if vat == 0:
            issues.append("TVA à 0 sans mention d'exonération")
        elif vat is None:
            issues.append("Montant de TVA introuvable")
    return issues


def check_document(
    document: Document,
    duplicate_of: Document | None,
    today: date | None = None,
    extraction_issues: list[str] | None = None,
) -> tuple[DocumentStatus, list[str]]:
    if document.kind == DocumentKind.unknown:
        return DocumentStatus.unreadable, [NOT_A_PURCHASE_DOCUMENT]

    missing = [
        label
        for field, label in REQUIRED_FIELDS[document.kind].items()
        if getattr(document, field) is None
    ]
    if missing:
        return DocumentStatus.unreadable, [f"Champ introuvable : {', '.join(missing)}"]

    issues = list(extraction_issues or [])
    lines = document.lines

    if document.kind == DocumentKind.invoice:
        issues += check_invoice_amounts(document)
    elif not lines:
        issues.append(NO_LINES)

    issues += check_lines(lines, check_quantities=document.kind != DocumentKind.invoice)
    if document.kind != DocumentKind.delivery:
        total_issue = check_lines_total(
            lines, document.amount_excl_tax, document.amount_incl_tax
        )
        if total_issue:
            issues.append(total_issue)

    if document.kind == DocumentKind.delivery and not document.order_reference:
        issues.append(NO_ORDER_REFERENCE)

    if document.document_date and document.document_date > (today or date.today()):
        issues.append("Date dans le futur")

    promised = document.expected_delivery_date
    if promised and document.document_date and promised < document.document_date:
        issues.append(PROMISED_BEFORE_ORDER)

    due = document.due_date
    if due and document.document_date and due < document.document_date:
        issues.append(DUE_BEFORE_INVOICE)

    if duplicate_of is not None:
        issues.append(number_issue(document, duplicate_of))

    return (DocumentStatus.to_check if issues else DocumentStatus.ok), issues
