from app.services.pdf_reader import MAX_PAGES, DoclingReader
from tests.utils.invoice import FIXTURES


def test_docling_reads_invoice_text() -> None:
    path = FIXTURES / "04-bureau-vallee-avignon.pdf"
    text = DoclingReader().read(path.read_bytes(), path.name)
    assert "BV2026-3381" in text
    assert "147,00 EUR" in text


def test_long_pdf_is_read_up_to_max_pages() -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for page in range(1, MAX_PAGES + 3):
        pdf.add_page()
        pdf.cell(0, 10, f"Contenu de la page {page}")
    text = DoclingReader().read(bytes(pdf.output()), "long.pdf")
    assert f"page {MAX_PAGES}" in text
    assert f"page {MAX_PAGES + 1}" not in text
