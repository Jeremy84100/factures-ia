from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Document, DocumentKind, DocumentStatus, User
from app.services.einvoice import parse_cii, read_einvoice
from app.services.extraction import ExtractedDocument, ExtractedLine
from app.services.processing import process_document
from tests.utils.invoice import PDF_BYTES, FakeExtractor, FakeReader

SAMPLES = Path(__file__).parents[1] / "fixtures" / "einvoices"
INVOICE = (SAMPLES / "Facture_FR_BASICWL.pdf").read_bytes()
CREDIT = (SAMPLES / "Avoir_FR_type381_BASIC.pdf").read_bytes()


def test_header_read_from_the_xml() -> None:
    read = read_einvoice(INVOICE)
    assert read is not None
    assert read.supplier == "Au bon moulin"
    assert read.number == "FA-2017-0010"
    assert read.date == "2017-11-13"
    assert read.order_reference == "PO445"
    assert (read.amount_excl_tax, read.vat_amount, read.amount_incl_tax) == (
        624.90,
        46.25,
        671.15,
    )
    assert read.currency == "EUR"
    assert read.due_date == "2017-12-13"
    assert not read.is_credit_note
    # BASIC WL: no lines in the XML.
    assert read.lines == []


def test_credit_note_and_its_lines() -> None:
    read = read_einvoice(CREDIT)
    assert read is not None
    assert read.is_credit_note
    assert [(line.description, line.quantity, line.unit) for line in read.lines] == [
        ("Nougat de l'Abbaye 250g", 5.0, "u"),
        ("Huile d'olive à l'ancienne", 10.0, "L"),
    ]
    assert all(line.quantity and line.amount_excl_tax for line in read.lines)


def test_a_plain_pdf_is_no_einvoice() -> None:
    assert read_einvoice(PDF_BYTES) is None
    assert read_einvoice(b"not a pdf") is None


def test_broken_or_foreign_xml_is_ignored() -> None:
    assert parse_cii(b"<oops") is None
    assert parse_cii(b"<Invoice xmlns='urn:oasis:names'/>") is None


def store(db: Session, pdf: bytes) -> Document:
    document = Document(filename="efacture.pdf", file=pdf, owner_id=owner(db))
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def owner(db: Session) -> object:

    user = db.exec(select(User)).first()
    assert user is not None
    return user.id


def test_einvoice_with_lines_skips_the_ai(db: Session) -> None:
    document = store(db, CREDIT)
    extractor = FakeExtractor()
    process_document(document.id, engine, FakeReader(), extractor)
    db.expire_all()
    read = db.get(Document, document.id)
    assert read is not None
    assert extractor.calls == []
    assert read.from_einvoice
    assert read.kind == DocumentKind.invoice
    assert read.is_credit_note
    assert read.amount_incl_tax is not None and read.amount_incl_tax < 0
    assert read.lines


def test_einvoice_without_lines_takes_them_from_the_ai(db: Session) -> None:
    document = store(db, INVOICE)
    from_ai = ExtractedDocument(
        document_type="facture",
        supplier="Au Bon Moulin (lu par l'IA)",
        number="FAUX",
        amount_incl_tax=1.0,
        lines=[ExtractedLine(description="Farine", quantity=10, amount_excl_tax=20)],
    )
    extractor = FakeExtractor(from_ai)
    process_document(document.id, engine, FakeReader(), extractor)
    db.expire_all()
    read = db.get(Document, document.id)
    assert read is not None
    assert len(extractor.calls) == 1
    # The header stays the XML's, exact; the lines come from the AI.
    assert read.supplier == "Au bon moulin"
    assert read.number == "FA-2017-0010"
    assert read.amount_incl_tax == Decimal("671.15")
    assert read.due_date == date(2017, 12, 13)
    assert [line.description for line in read.lines] == ["Farine"]
    assert read.status in (DocumentStatus.ok, DocumentStatus.to_check)
