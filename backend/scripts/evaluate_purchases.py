import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models import Document, DocumentStatus
from app.services.checks import check_document, review_extraction
from app.services.extraction import ExtractionError, GeminiExtractor
from app.services.pdf_reader import DoclingReader
from app.services.processing import apply_extraction
from app.services.reconciliation import build_purchases, reference_key

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "purchases"


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
    scores = {"type": 0, "numéro": 0, "n° commande": 0, "lignes": 0}
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
        for name, ok in checks.items():
            scores[name] += ok
        wrong = [name for name, ok in checks.items() if not ok]
        status = "" if document.status == DocumentStatus.ok else f" ({document.status})"
        print(f"{'OK  ' if not wrong else 'FAUX'} {path.name}{status} {wrong or ''}")

    total = len(expected["documents"])
    print(f"\nModèle : {settings.GEMINI_MODEL} — {total} documents")
    for name, hits in scores.items():
        print(f"  {name:<12} {hits}/{total}")

    result = build_purchases(documents)
    verdicts = {p.key: p for p in result.data}
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
