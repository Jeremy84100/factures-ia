from collections.abc import Sequence
from decimal import Decimal

from app.models import DocumentRef, Purchase, SupplierEmail
from app.services.reconciliation import AMOUNT_TOLERANCE, all_issues, day, euros


def numbers(documents: Sequence[DocumentRef]) -> str:
    names = [d.number or d.filename for d in documents]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} et {names[-1]}"


def described(documents: Sequence[DocumentRef], one: str, many: str) -> str:
    text = f"{one if len(documents) == 1 else many} n° {numbers(documents)}"
    if len(documents) == 1 and documents[0].document_date:
        text += f" du {day(documents[0].document_date)}"
    return text


# A plain, polite letter listing what does not match, ready to send. Written
# from the comparison itself, without the AI: every figure is one it checked.
def write_email(purchase: Purchase, sender: str | None = None) -> SupplierEmail:
    order = purchase.order_reference
    if purchase.invoices:
        checked = described(purchase.invoices, "votre facture", "vos factures")
        subject = f"Commande {order} : écarts sur {checked.split(' du ')[0]}"
        request = (
            "Pourriez-vous nous adresser un avoir ou une facture corrigée ?"
            " Nous réglerons dès réception."
        )
    else:
        checked = described(
            purchase.deliveries, "votre bon de livraison", "vos bons de livraison"
        )
        subject = f"Commande {order} : écarts sur la livraison"
        request = "Pourriez-vous nous indiquer comment régulariser ces écarts ?"

    lines = [
        "Bonjour,",
        "",
        f"En vérifiant {checked}, pour notre commande n° {order},"
        " nous avons relevé les écarts suivants :",
        "",
        *(f"- {issue}" for issue in all_issues(purchase)),
        "",
    ]
    extra = purchase.gap_excl_tax or Decimal(0)
    if purchase.invoices and extra > AMOUNT_TOLERANCE:
        lines += [f"Le montant facturé en trop s'élève à {euros(extra)} HT.", ""]
    lines += [request, "", "Cordialement,"]
    if sender:
        lines.append(sender)
    return SupplierEmail(subject=subject, body="\n".join(lines))
