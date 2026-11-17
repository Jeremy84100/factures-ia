from pathlib import Path

from sqlmodel import Session

from app.models import Document, DocumentKind, DocumentStatus
from app.services.extraction import ExtractedDocument, ExtractedLine, ExtractionError
from tests.utils.user import create_random_user

FIXTURES = Path(__file__).parent.parent / "fixtures" / "invoices"

PDF_BYTES = (FIXTURES / "01-edf.pdf").read_bytes()

EDF = ExtractedDocument(
    supplier="EDF",
    document_type="facture",
    number="FA-2026-0412",
    date="2026-03-04",
    amount_excl_tax=70.17,
    vat_amount=14.03,
    amount_incl_tax=84.20,
    currency="eur",
)


CABLE = ExtractedLine(
    reference="CAB-3G25",
    description="Câble R2V 3G2,5 couronne 100 m",
    quantity=50,
    unit="m",
    unit_price=1.19,
    amount_excl_tax=59.50,
)
GAINE = ExtractedLine(
    reference="ICTA-20",
    description="Gaine ICTA 20 mm",
    quantity=100,
    unit="m",
    unit_price=0.42,
    amount_excl_tax=42.00,
)

ORDER = ExtractedDocument(
    document_type="bon_de_commande",
    supplier="Rexel",
    number="CMD-2041",
    date="2026-10-02",
    amount_excl_tax=101.50,
    currency="EUR",
    lines=[CABLE, GAINE],
)


def purchase_documents(
    order_number: str,
) -> tuple[ExtractedDocument, ExtractedDocument, ExtractedDocument]:
    order = ORDER.model_copy(update={"number": order_number})
    delivery = ExtractedDocument(
        document_type="bon_de_livraison",
        supplier="Rexel",
        number=f"BL-{order_number}",
        date="2026-10-05",
        order_reference=order_number,
        lines=[
            line.model_copy(update={"unit_price": None, "amount_excl_tax": None})
            for line in (CABLE, GAINE)
        ],
    )
    invoice = ExtractedDocument(
        document_type="facture",
        supplier="Rexel",
        number=f"FA-{order_number}",
        date="2026-10-06",
        order_reference=order_number,
        amount_excl_tax=101.50,
        vat_amount=20.30,
        amount_incl_tax=121.80,
        currency="EUR",
        lines=[CABLE, GAINE],
    )
    return order, delivery, invoice


class FakeReader:
    def __init__(self, text: str = "facture", error: bool = False) -> None:
        self.text = text
        self.error = error

    def read(self, data: bytes, filename: str) -> str:  # noqa: ARG002
        if self.error:
            raise ValueError("PDF cassé")
        return self.text


class FakeExtractor:
    def __init__(
        self, result: ExtractedDocument = EDF, error: str | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    def extract(self, text: str, pdf: bytes) -> ExtractedDocument:
        self.calls.append((text, pdf))
        if self.error:
            raise ExtractionError(self.error)
        return self.result


def create_random_document(
    db: Session, kind: DocumentKind = DocumentKind.unknown
) -> Document:
    user = create_random_user(db)
    document = Document(
        kind=kind, filename="document.pdf", file=PDF_BYTES, owner_id=user.id
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_random_invoice(
    db: Session, status: DocumentStatus = DocumentStatus.pending
) -> Document:
    user = create_random_user(db)
    invoice = Document(
        kind=DocumentKind.invoice,
        filename="facture.pdf",
        file=PDF_BYTES,
        owner_id=user.id,
        status=status,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
