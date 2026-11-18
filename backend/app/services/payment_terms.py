"""When an invoice must be paid, from what is written on it.

The AI copies the due date when one is printed, and the payment terms as
written (« 30 jours », « 45 jours fin de mois », « à réception »). The date is
worked out here, in code, rather than by the AI.
"""

import calendar
import re
import unicodedata
from datetime import date, timedelta

# Code de commerce, art. L441-10: 30 days when nothing was agreed.
LEGAL_DAYS = 30

DAYS = re.compile(r"(\d{1,3})\s*(?:j|jours?|days?|tagen?)\b")
END_OF_MONTH = re.compile(r"fin de mois|f\.?\s?d\.?\s?m\b|end of month")
AT_ONCE = re.compile(r"reception|comptant|immediat|a vue|upon receipt|on receipt")


def plain(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return folded.lower()


def end_of_month(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def due_from_terms(terms: str | None, invoice_date: date | None) -> date | None:
    if not terms or invoice_date is None:
        return None
    text = plain(terms)
    if match := DAYS.search(text):
        due = invoice_date + timedelta(days=int(match.group(1)))
        return end_of_month(due) if END_OF_MONTH.search(text) else due
    if AT_ONCE.search(text):
        return invoice_date
    return None


def legal_due_date(invoice_date: date) -> date:
    return invoice_date + timedelta(days=LEGAL_DAYS)
