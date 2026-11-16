from app.services.pdf_reader import DoclingReader
from tests.utils.invoice import FIXTURES


def test_docling_reads_invoice_text() -> None:
    path = FIXTURES / "04-bureau-vallee-avignon.pdf"
    text = DoclingReader().read(path.read_bytes(), path.name)
    assert "BV2026-3381" in text
    assert "147,00 EUR" in text
