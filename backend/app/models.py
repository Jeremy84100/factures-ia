import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import EmailStr
from sqlalchemy import JSON, LargeBinary, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    documents: list[Document] = Relationship(
        back_populates="owner", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class Features(SQLModel):
    password_recovery: bool


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class DocumentKind(StrEnum):
    unknown = "unknown"
    invoice = "invoice"
    order = "order"
    delivery = "delivery"


class DeliveryMode(StrEnum):
    pickup = "pickup"
    standard = "standard"
    express = "express"


class DocumentStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ok = "ok"
    to_check = "to_check"
    unreadable = "unreadable"
    failed = "failed"


class LineFields(SQLModel):
    reference: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    quantity: Decimal | None = Field(default=None, max_digits=12, decimal_places=3)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    amount_excl_tax: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )


class DocumentFields(SQLModel):
    supplier: str | None = Field(default=None, max_length=255)
    number: str | None = Field(default=None, max_length=100)
    document_date: date | None = None
    order_reference: str | None = Field(default=None, max_length=100, index=True)
    amount_excl_tax: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    vat_amount: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    amount_incl_tax: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    currency: str | None = Field(default=None, max_length=3)
    is_credit_note: bool = False
    vat_exemption: str | None = Field(default=None, max_length=255)
    delivery_method: str | None = Field(default=None, max_length=100)
    delivery_mode: DeliveryMode | None = Field(default=None, sa_type=String(20))
    expected_delivery_date: date | None = None
    due_date: date | None = None
    payment_terms: str | None = Field(default=None, max_length=100)
    iban: str | None = Field(default=None, max_length=34)
    supplier_email: str | None = Field(default=None, max_length=255)


class DocumentUpdate(DocumentFields):
    kind: DocumentKind | None = None
    lines: list[LineFields] | None = None


class Document(DocumentFields, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    kind: DocumentKind = Field(
        default=DocumentKind.unknown, sa_type=String(20), index=True
    )
    filename: str = Field(max_length=255)
    file: bytes = Field(sa_type=LargeBinary)
    status: DocumentStatus = Field(
        default=DocumentStatus.pending, sa_type=String(20), index=True
    )
    issues: list[str] = Field(default_factory=list, sa_type=JSON)
    # Read from the e-invoice data inside the PDF (Factur-X), not by the AI.
    from_einvoice: bool = False
    # The user called the supplier: a new IBAN on this invoice is genuine.
    iban_checked: bool = False
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    started_at: datetime | None = None
    processed_at: datetime | None = None
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="documents")
    lines: list[DocumentLine] = Relationship(
        back_populates="document",
        cascade_delete=True,
        sa_relationship_kwargs={"order_by": "DocumentLine.position"},
    )


class DocumentLine(LineFields, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    position: int = 0
    document_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="document.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
    )
    document: Document | None = Relationship(back_populates="lines")


class DocumentPublic(DocumentFields):
    id: uuid.UUID
    owner_id: uuid.UUID
    kind: DocumentKind
    filename: str
    status: DocumentStatus
    issues: list[str]
    from_einvoice: bool = False
    iban_checked: bool = False
    lines: list[LineFields] = []
    created_at: datetime | None = None
    processed_at: datetime | None = None


class DocumentsPublic(SQLModel):
    data: list[DocumentPublic]
    count: int


# A dispute the user has settled with the supplier. It only holds for the
# issues the purchase had then: a new document that changes them reopens it.
class Settlement(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("owner_id", "purchase_key"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    purchase_key: str = Field(max_length=100)
    issues: list[str] = Field(default_factory=list, sa_type=JSON)
    settled_at: datetime = Field(default_factory=get_datetime_utc)


# A purchase the user has paid: the invoices it had then. An invoice that
# comes later is still to pay.
class Payment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("owner_id", "purchase_key"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True
    )
    purchase_key: str = Field(max_length=100)
    invoice_ids: list[str] = Field(default_factory=list, sa_type=JSON)
    paid_at: datetime = Field(default_factory=get_datetime_utc)


class PurchaseStatus(StrEnum):
    to_pay = "to_pay"
    dispute = "dispute"
    waiting = "waiting"
    paid = "paid"


class DocumentRef(SQLModel):
    id: uuid.UUID
    kind: DocumentKind
    filename: str
    number: str | None = None
    document_date: date | None = None
    status: DocumentStatus


class LinkSuggestion(SQLModel):
    key: str
    order_reference: str
    # When the order was placed, so the user can tell it is the right one.
    order_date: date | None = None


# A document no purchase could take, with the purchases it may belong to.
class UnlinkedDocument(DocumentRef):
    supplier: str | None = None
    suggestions: list[LinkSuggestion] = []


class LineMatch(SQLModel):
    label: str
    reference: str | None = None
    ordered: Decimal | None = None
    delivered: Decimal = Decimal(0)
    invoiced: Decimal = Decimal(0)
    order_price: Decimal | None = None
    invoice_price: Decimal | None = None
    fee: bool = False
    issues: list[str] = []
    notes: list[str] = []


class Purchase(SQLModel):
    key: str
    order_reference: str
    supplier: str | None = None
    status: PurchaseStatus
    orders: list[DocumentRef] = []
    deliveries: list[DocumentRef] = []
    invoices: list[DocumentRef] = []
    lines: list[LineMatch] = []
    issues: list[str] = []
    notes: list[str] = []
    late: bool = False
    expected_delivery_date: date | None = None
    invoice_only: bool = False
    invoiced_excl_tax: Decimal | None = None
    invoiced_incl_tax: Decimal | None = None
    # Incl. tax, invoices not paid yet.
    to_pay_incl_tax: Decimal | None = None
    gap_excl_tax: Decimal | None = None
    gap_incl_tax: Decimal | None = None
    due_date: date | None = None
    # No due date written on the invoice: the legal 30 days are assumed.
    due_date_assumed: bool = False
    # Where to pay and whom to write to, from the latest invoice.
    iban: str | None = None
    supplier_email: str | None = None
    # An invoice asks to be paid on a new IBAN: call before paying.
    iban_warning: str | None = None
    iban_document_id: uuid.UUID | None = None
    settled_at: datetime | None = None
    paid_at: datetime | None = None


class Purchases(SQLModel):
    data: list[Purchase]
    unlinked: list[UnlinkedDocument]
    count: int


class SupplierEmail(SQLModel):
    to: str | None = None
    subject: str
    body: str


class SupplierTotal(SQLModel):
    supplier: str
    count: int
    total_incl_tax: Decimal


class SupplierTotals(SQLModel):
    data: list[SupplierTotal]


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
