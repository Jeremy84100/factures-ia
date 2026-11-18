"""IBANs: the bank account an invoice asks to be paid on.

A changed bank account is the fraud small firms meet most ("fraude au
changement de RIB"): an e-mail, or a fake invoice, from someone posing as the
supplier with a new IBAN. When an invoice gives another IBAN than the last one
of the same supplier, it waits until someone has called the supplier.
"""

import re
from collections.abc import Iterable
from datetime import date

from app.models import Document

NOT_ALNUM = re.compile(r"[^0-9A-Z]")
SHAPE = re.compile(r"^[A-Z]{2}\d{2}[0-9A-Z]{11,30}$")
INVALID_IBAN = "IBAN faux ou mal lu : vérifiez-le sur le PDF"
IBAN_CHANGED = "Nouvel IBAN"


def clean_iban(value: str | None) -> str | None:
    if not value:
        return None
    return NOT_ALNUM.sub("", value.upper())[:34] or None


def valid_iban(iban: str) -> bool:
    """ISO 13616: the shape, then the mod 97 check."""
    if not SHAPE.match(iban):
        return False
    moved = iban[4:] + iban[:4]
    digits = "".join(str(int(char, 36)) for char in moved)
    return int(digits) % 97 == 1


def iban_change(document: Document, others: Iterable[Document]) -> str | None:
    """Says so when the supplier's latest other invoice gave another IBAN."""
    from app.services.reconciliation import same_supplier

    if not document.iban or not document.supplier:
        return None
    supplier = document.supplier
    # Only the invoices before this one: the older invoice is not the suspect.
    previous = [
        other
        for other in others
        if other.id != document.id
        and other.iban
        and other.supplier
        and same_supplier(supplier, other.supplier)
        and not (
            document.document_date
            and other.document_date
            and other.document_date > document.document_date
        )
    ]
    if not previous:
        return None
    last = max(previous, key=lambda d: d.document_date or date.min)
    if last.iban == document.iban:
        return None
    when = f" du {last.document_date:%d/%m/%Y}" if last.document_date else ""
    return (
        f"{IBAN_CHANGED} : finit par {document.iban[-4:]}, la facture"
        f" {last.number or last.filename}{when} donnait un IBAN finissant par"
        f" {(last.iban or '')[-4:]}. Appelez le fournisseur à un numéro que vous"
        " connaissez avant de payer"
    )
