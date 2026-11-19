"""The invoices for the accountant: one spreadsheet and the PDFs, in a zip.

The spreadsheet opens in French Excel as is: « ; » between columns, a comma
before the cents, and a BOM so the accents show.
"""

import csv
import io
import re
import unicodedata
import zipfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from app.models import Document

COLUMNS = [
    "Date",
    "Fournisseur",
    "Numéro",
    "Type",
    "N° de commande",
    "Total HT",
    "TVA",
    "Total TTC",
    "Échéance",
    "Payée le",
    "Fichier",
    "Devise",
]
UNSAFE = re.compile(r"[^\w.-]+")


def amount(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.2f}".replace(".", ",")


def file_name(document: Document, taken: set[str]) -> str:
    day = document.document_date.isoformat() if document.document_date else "sans-date"
    # Plain letters: old archive tools mangle accents in file names.
    label = f"{day}_{document.supplier or ''}_{document.number or ''}"
    plain = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    stem = UNSAFE.sub("-", plain)
    name, count = f"{stem.strip('-_')}.pdf", 2
    while name in taken:
        name, count = f"{stem.strip('-_')}-{count}.pdf", count + 1
    taken.add(name)
    return name


def build_export(
    invoices: Sequence[Document], paid_on: Mapping[str, datetime]
) -> bytes:
    table = io.StringIO()
    writer = csv.writer(table, delimiter=";", lineterminator="\r\n")
    writer.writerow(COLUMNS)
    archive = io.BytesIO()
    taken: set[str] = set()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for invoice in invoices:
            name = file_name(invoice, taken)
            zip_file.writestr(f"factures/{name}", invoice.file)
            paid = paid_on.get(str(invoice.id))
            writer.writerow(
                [
                    invoice.document_date.strftime("%d/%m/%Y")
                    if invoice.document_date
                    else "",
                    invoice.supplier or "",
                    invoice.number or "",
                    "Avoir" if invoice.is_credit_note else "Facture",
                    invoice.order_reference or "",
                    amount(invoice.amount_excl_tax),
                    amount(invoice.vat_amount),
                    amount(invoice.amount_incl_tax),
                    invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else "",
                    paid.strftime("%d/%m/%Y") if paid else "",
                    name,
                    invoice.currency or "",
                ]
            )
        zip_file.writestr("factures.csv", "﻿" + table.getvalue())
    return archive.getvalue()
