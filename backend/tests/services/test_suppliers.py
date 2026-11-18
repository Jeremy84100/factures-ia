from datetime import date

from sqlmodel import Session

from app.core.db import engine
from app.models import DateOrder, DeliveryMode, Document, DocumentKind, Supplier
from app.services.extraction import ExtractedDocument
from app.services.processing import is_credit_title, process_document
from app.services.suppliers import (
    Knowledge,
    apply_knowledge,
    country_of,
    date_order_of,
    order_from_correction,
    read_date,
    supplier_key,
)
from tests.utils.invoice import EDF, FakeExtractor, create_random_invoice

FR_IBAN = "FR7630006000011234567890189"


def test_one_supplier_whatever_way_its_name_is_written() -> None:
    assert supplier_key("ÉLECTRO PROVENCE DISTRIBUTION SAS") == supplier_key(
        "Electro-Provence Distribution"
    )
    assert supplier_key("Rexel France S.A.S.") == "rexel france"
    # A name made only of a legal form is kept.
    assert supplier_key("SAS") == "sas"


def test_dates_read_the_way_the_supplier_writes_them() -> None:
    assert read_date("08/01/2026", DateOrder.day_first) == date(2026, 1, 8)
    assert read_date("08/01/2026", DateOrder.month_first) == date(2026, 8, 1)
    assert read_date("8.1.26", DateOrder.day_first) == date(2026, 1, 8)
    assert read_date("31/02/2026", DateOrder.day_first) is None
    assert read_date("8 janvier 2026", DateOrder.day_first) is None
    assert read_date("08/01/2026", None) is None


def test_a_corrected_date_tells_how_the_supplier_writes_dates() -> None:
    assert order_from_correction("08/01/2026", date(2026, 1, 8)) == DateOrder.day_first
    assert (
        order_from_correction("08/01/2026", date(2026, 8, 1)) == DateOrder.month_first
    )
    # Same both ways, or another date altogether: nothing learned.
    assert order_from_correction("05/05/2026", date(2026, 5, 5)) is None
    assert order_from_correction("08/01/2026", date(2026, 3, 3)) is None


def test_date_order_from_the_country_unless_corrected() -> None:
    def supplier(country: str | None, order: DateOrder | None = None) -> Supplier:
        return Supplier(
            name="X", key="x", owner_id=EDF_OWNER, country=country, date_order=order
        )

    assert date_order_of(supplier("FR")) == DateOrder.day_first
    assert date_order_of(supplier("US")) == DateOrder.month_first
    assert date_order_of(supplier("CA")) is None
    assert date_order_of(supplier(None)) is None
    assert date_order_of(supplier("US", DateOrder.day_first)) == DateOrder.day_first


def test_country_from_the_address_else_from_the_iban() -> None:
    assert country_of("de", None) == "DE"
    assert country_of(None, FR_IBAN) == "FR"
    assert country_of("France", None) is None


def test_credit_note_titles() -> None:
    for title in (
        "AVOIR",
        "Facture d'avoir n° 12",
        "Gutschrift",
        "Credit Note",
        "Note de crédit",
    ):
        assert is_credit_title(title), title
    for title in ("FACTURE", "Rechnung", "Facture à valoir sur commande", None):
        assert not is_credit_title(title), title


def test_knowledge_fills_what_the_document_does_not_say() -> None:
    document = Document(
        filename="f.pdf",
        file=b"",
        owner_id=EDF_OWNER,
        kind=DocumentKind.invoice,
        date_raw="08/01/2026",
        document_date=date(2026, 8, 1),
        delivery_method="Livraison dépôt",
        delivery_mode=DeliveryMode.pickup,
    )
    knowledge = Knowledge(
        date_order=DateOrder.day_first,
        delivery_modes={"livraison depot": DeliveryMode.standard},
        payment_terms="30 jours fin de mois",
        email="compta@exemple.fr",
    )
    apply_knowledge(document, knowledge, due_printed=False)
    assert document.document_date == date(2026, 1, 8)
    assert document.delivery_mode == DeliveryMode.standard
    assert document.payment_terms == "30 jours fin de mois"
    assert document.due_date == date(2026, 2, 28)
    assert document.supplier_email == "compta@exemple.fr"


def test_an_e_invoice_date_is_never_read_again() -> None:
    document = Document(
        filename="f.pdf",
        file=b"",
        owner_id=EDF_OWNER,
        from_einvoice=True,
        date_raw="08/01/2026",
        document_date=date(2026, 8, 1),
    )
    apply_knowledge(
        document, Knowledge(date_order=DateOrder.day_first), due_printed=True
    )
    assert document.document_date == date(2026, 8, 1)


EDF_OWNER = __import__("uuid").uuid4()


def read(db: Session, extracted: ExtractedDocument) -> Document:
    invoice = create_random_invoice(db)
    owner = invoice.owner_id
    process_document(invoice.id, engine, FakeExtractor(extracted))
    db.expire_all()
    document = db.get(Document, invoice.id)
    assert document is not None and document.owner_id == owner
    return document


def test_documents_of_one_supplier_are_filed_together(db: Session) -> None:
    first = read(db, EDF.model_copy(update={"supplier": "Rexel France SAS"}))
    second = Document(filename="b.pdf", file=b"%PDF", owner_id=first.owner_id)
    db.add(second)
    db.commit()
    extractor = FakeExtractor(
        EDF.model_copy(update={"supplier": "REXEL FRANCE", "number": "B"})
    )
    process_document(second.id, engine, extractor)
    db.expire_all()
    second = db.get(Document, second.id)
    assert second is not None
    assert first.supplier_id is not None
    assert second.supplier_id == first.supplier_id


def test_a_french_supplier_date_is_read_day_first_by_code(db: Session) -> None:
    misread = EDF.model_copy(
        update={
            "supplier": "Rexel Avignon",
            "supplier_country": "FR",
            "date_raw": "08/01/2026",
            "date": "2026-08-01",
            "currency": "USD",
        }
    )
    document = read(db, misread)
    assert document.document_date == date(2026, 1, 8)
    assert not any("inversés" in issue for issue in document.issues)
    supplier = db.get(Supplier, document.supplier_id)
    assert supplier is not None and supplier.country == "FR"


def test_an_american_supplier_date_is_read_month_first(db: Session) -> None:
    misread = EDF.model_copy(
        update={
            "supplier": "Acme Corp",
            "supplier_country": "US",
            "date_raw": "08/01/2026",
            "date": "2026-01-08",
            "currency": "USD",
        }
    )
    assert read(db, misread).document_date == date(2026, 8, 1)


def test_a_credit_note_title_overrules_the_ai(db: Session) -> None:
    gutschrift = EDF.model_copy(
        update={
            "supplier": "Lieferant GmbH",
            "title": "Gutschrift",
            "is_credit_note": False,
        }
    )
    document = read(db, gutschrift)
    assert document.is_credit_note
    assert document.amount_incl_tax is not None and document.amount_incl_tax < 0


def test_a_self_billed_invoice_is_not_a_credit_note(db: Session) -> None:
    self_billed = EDF.model_copy(
        update={
            "supplier": "Lieferant Zwei GmbH",
            "title": "Gutschrift (Selbst ausgestellte Rechnung)",
            "is_credit_note": True,
        }
    )
    document = read(db, self_billed)
    assert not document.is_credit_note
    assert document.amount_incl_tax is not None and document.amount_incl_tax > 0


def test_a_masked_customer_iban_is_ignored(db: Session) -> None:
    debit = EDF.model_copy(
        update={"supplier": "Hébergeur", "iban": "DE54 5004 **** **** **** 00"}
    )
    document = read(db, debit)
    assert document.iban is None
    assert document.issues == []
