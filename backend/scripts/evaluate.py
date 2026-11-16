import json
import sys
from pathlib import Path

from app.core.config import settings
from app.services.extraction import ExtractionError, GeminiExtractor
from app.services.pdf_reader import DoclingReader
from app.services.processing import to_amount, to_date

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "invoices"
FIELDS = [
    "supplier",
    "invoice_number",
    "invoice_date",
    "amount_excl_tax",
    "vat_amount",
    "amount_incl_tax",
]


def normalize(field: str, value: object) -> object:
    if value is None:
        return None
    if field.startswith("amount") or field == "vat_amount":
        return to_amount(float(str(value)))
    if field == "invoice_date":
        return to_date(str(value))
    return str(value).strip().lower()


def main() -> None:
    if not settings.GEMINI_API_KEY:
        sys.exit("Ajoute GEMINI_API_KEY dans .env avant de lancer l'évaluation.")

    reader = DoclingReader()
    extractor = GeminiExtractor(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    hits = dict.fromkeys(FIELDS, 0)
    for case in expected:
        path = FIXTURES / case["filename"]
        try:
            data = path.read_bytes()
            result = extractor.extract(reader.read(data, path.name), data)
        except ExtractionError as e:
            print(f"ÉCHEC {case['filename']} : {e}")
            continue
        got = result.model_dump()
        wrong = [
            field
            for field in FIELDS
            if normalize(field, got[field]) != normalize(field, case[field])
        ]
        for field in FIELDS:
            hits[field] += field not in wrong
        print(f"{'OK  ' if not wrong else 'FAUX'} {case['filename']} {wrong or ''}")

    total = len(expected)
    print(f"\nModèle : {settings.GEMINI_MODEL} — {total} factures")
    for field in FIELDS:
        print(f"  {field:<16} {hits[field] / total:6.1%}")
    print(f"  {'global':<16} {sum(hits.values()) / (total * len(FIELDS)):6.1%}")


if __name__ == "__main__":
    main()
