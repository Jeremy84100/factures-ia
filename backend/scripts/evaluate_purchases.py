import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models import Document, DocumentStatus
from app.services.checks import check_document, review_extraction
from app.services.demo import check_ibans
from app.services.extraction import ExtractionError, GeminiExtractor
from app.services.pdf_reader import DoclingReader
from app.services.processing import apply_extraction
from app.services.reconciliation import build_purchases, reference_key

FIXTURES = Path(__file__).parent.parent / "app" / "demo" / "purchases"
DELIVERY_KINDS = ("order", "delivery")


def same_number(a: object, b: object) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return Decimal(str(a)) == Decimal(str(b))


def lines_ok(document: Document, expected: list[dict[str, Any]]) -> bool:
    if len(document.lines) != len(expected):
        return False
    return all(
        same_number(line.quantity, want["quantity"])
        and same_number(line.unit_price, want["unit_price"])
        for line, want in zip(document.lines, expected, strict=True)
    )


def main() -> None:
    if not settings.GEMINI_API_KEY:
        sys.exit("Ajoute GEMINI_API_KEY dans .env avant de lancer l'évaluation.")

    reader = DoclingReader()
    extractor = GeminiExtractor(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    owner = uuid.uuid4()

    documents: list[Document] = []
    scores = {
        "type": 0,
        "numéro": 0,
        "n° commande": 0,
        "lignes": 0,
        "livraison": 0,
        "échéance": 0,
        "iban": 0,
        "e-mail": 0,
    }
    for case in expected["documents"]:
        path = FIXTURES / case["filename"]
        data = path.read_bytes()
        document = Document(filename=path.name, file=b"", owner_id=owner)
        try:
            extracted = extractor.extract(reader.read(data, path.name), data)
        except ExtractionError as e:
            print(f"ÉCHEC {path.name} : {e}")
            continue
        apply_extraction(document, extracted)
        document.status, document.issues = check_document(
            document, None, extraction_issues=review_extraction(extracted)
        )
        documents.append(document)

        checks = {
            "type": document.kind.value == case["kind"],
            "numéro": reference_key(document.number) == reference_key(case["number"]),
            "n° commande": reference_key(document.order_reference)
            == reference_key(case["order_reference"]),
            "lignes": lines_ok(document, case["lines"]),
        }
        # Delivery mode and promised date are only compared on orders and
        # delivery notes: an invoice may mention them, they are never used.
        if case["kind"] in DELIVERY_KINDS:
            checks["livraison"] = (document.delivery_mode or None) == case[
                "delivery_mode"
            ] and str(document.expected_delivery_date or "") == (
                case["expected_delivery_date"] or ""
            )
        # The due date as the app stores it: printed, or worked out from the
        # payment terms the AI copied.
        if case["kind"] == "invoice":
            checks["échéance"] = str(document.due_date or "") == (
                case["due_date"] or ""
            )
            checks["iban"] = document.iban == case["iban"]
            checks["e-mail"] = document.supplier_email == case["supplier_email"]
        for name, ok in checks.items():
            scores[name] += ok
        wrong = [name for name, ok in checks.items() if not ok]
        status = "" if document.status == DocumentStatus.ok else f" ({document.status})"
        print(f"{'OK  ' if not wrong else 'FAUX'} {path.name}{status} {wrong or ''}")

    total = len(expected["documents"])
    totals = dict.fromkeys(scores, total)
    totals["livraison"] = sum(
        case["kind"] in DELIVERY_KINDS for case in expected["documents"]
    )
    invoices = sum(case["kind"] == "invoice" for case in expected["documents"])
    totals["échéance"] = totals["iban"] = totals["e-mail"] = invoices
    # The bank account check a real upload does against earlier invoices.
    check_ibans(documents)
    print(f"\nModèle : {settings.GEMINI_MODEL} — {total} documents")
    for name, hits in scores.items():
        print(f"  {name:<12} {hits}/{totals[name]}")

    result = build_purchases(documents)
    verdicts = {reference_key(p.order_reference): p for p in result.data}
    unlinked = {ref.number for ref in result.unlinked}
    good = 0
    print(f"\n{len(expected['purchases'])} achats")
    for purchase in expected["purchases"]:
        got = verdicts.get(reference_key(purchase["order_reference"]))
        verdict = got.status.value if got else "absent"
        links_ok = all(number in unlinked for number in purchase["unlinked"])
        ok = verdict == purchase["status"] and links_ok
        good += ok
        print(
            f"{'OK  ' if ok else 'FAUX'} {purchase['case']:<45}"
            f" attendu {purchase['status']:<9} obtenu {verdict}"
        )
        if got and not ok:
            for issue in got.issues + [i for line in got.lines for i in line.issues]:
                print(f"       {issue}")
    print(f"  verdicts justes : {good}/{len(expected['purchases'])}")


if __name__ == "__main__":
    main()
