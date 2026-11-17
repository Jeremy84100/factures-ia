from pathlib import Path

from sqlmodel import Session

from app.models import Document, DocumentKind, DocumentStatus
from app.services.extraction import ExtractedInvoice, ExtractionError
from tests.utils.user import create_random_user

FIXTURES = Path(__file__).parent.parent / "fixtures" / "invoices"

PDF_BYTES = (FIXTURES / "01-edf.pdf").read_bytes()

EDF = ExtractedInvoice(
    supplier="EDF",
    invoice_number="FA-2026-0412",
    invoice_date="2026-03-04",
    amount_excl_tax=70.17,
    vat_amount=14.03,
    amount_incl_tax=84.20,
    currency="eur",
)


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
        self, result: ExtractedInvoice = EDF, error: str | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    def extract(self, text: str, pdf: bytes) -> ExtractedInvoice:
        self.calls.append((text, pdf))
        if self.error:
            raise ExtractionError(self.error)
        return self.result


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
