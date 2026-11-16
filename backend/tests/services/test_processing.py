import uuid
from datetime import date
from decimal import Decimal

from sqlmodel import Session

from app.core.db import engine
from app.models import Invoice, InvoiceStatus
from app.services.processing import process_invoice, to_amount, to_date
from tests.utils.invoice import EDF, FakeExtractor, FakeReader, create_random_invoice


def reload(db: Session, invoice: Invoice) -> Invoice:
    db.expire_all()
    fresh = db.get(Invoice, invoice.id)
    assert fresh is not None
    return fresh


def test_to_amount_rounds_to_cents() -> None:
    assert to_amount(84.2) == Decimal("84.20")
    assert to_amount(None) is None


def test_to_date_ignores_bad_values() -> None:
    assert to_date("2026-03-04") == date(2026, 3, 4)
    assert to_date("04/03/2026") is None
    assert to_date(None) is None


def test_process_fills_fields(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(invoice.id, engine, FakeReader(), FakeExtractor())
    invoice = reload(db, invoice)
    assert invoice.status == InvoiceStatus.ok
    assert invoice.supplier == "EDF"
    assert invoice.invoice_date == date(2026, 3, 4)
    assert invoice.amount_incl_tax == Decimal("84.20")
    assert invoice.currency == "EUR"
    assert invoice.processed_at is not None


def test_unreadable_pdf(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(invoice.id, engine, FakeReader(error=True), FakeExtractor())
    invoice = reload(db, invoice)
    assert invoice.status == InvoiceStatus.unreadable
    assert invoice.issues == ["Le PDF n'a pas pu être lu"]


def test_empty_text(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(invoice.id, engine, FakeReader(text="  \n"), FakeExtractor())
    assert reload(db, invoice).issues == ["Aucun texte trouvé dans le PDF"]


def test_ai_error_is_kept(db: Session) -> None:
    invoice = create_random_invoice(db)
    process_invoice(
        invoice.id, engine, FakeReader(), FakeExtractor(error="quota dépassé")
    )
    invoice = reload(db, invoice)
    assert invoice.status == InvoiceStatus.failed
    assert invoice.issues == ["quota dépassé"]


def test_duplicate_for_same_owner(db: Session) -> None:
    first = create_random_invoice(db)
    process_invoice(first.id, engine, FakeReader(), FakeExtractor())
    second = Invoice(filename="copie.pdf", file=b"%PDF", owner_id=first.owner_id)
    db.add(second)
    db.commit()
    same_supplier = EDF.model_copy(update={"supplier": "edf"})
    process_invoice(second.id, engine, FakeReader(), FakeExtractor(same_supplier))
    second = reload(db, second)
    assert second.status == InvoiceStatus.to_check
    assert second.issues == ["Doublon possible de « facture.pdf »"]


def test_missing_invoice_is_ignored() -> None:
    process_invoice(uuid.uuid4(), engine, FakeReader(), FakeExtractor())
