import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import EmailStr
from sqlalchemy import JSON, LargeBinary, String
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


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class DocumentKind(StrEnum):
    unknown = "unknown"
    invoice = "invoice"
    order = "order"
    delivery = "delivery"


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
    lines: list[LineFields] = []
    created_at: datetime | None = None
    processed_at: datetime | None = None


class DocumentsPublic(SQLModel):
    data: list[DocumentPublic]
    count: int


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
