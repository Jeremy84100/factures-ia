from datetime import date, timedelta

import pytest
from sqlmodel import Session, col, select

from app.models import Document, DocumentStatus, User
from app.services import demo
from app.services.demo import (
    DEMO_DOMAIN,
    DEMO_LIFETIME,
    DemoUnavailable,
    create_demo_user,
    is_demo,
)
from app.services.reconciliation import build_purchases, reference_key

TODAY = date(2026, 11, 17)


def documents_of(db: Session, user: User) -> list[Document]:
    return list(db.exec(select(Document).where(Document.owner_id == user.id)).all())


def test_demo_user_gets_the_30_documents_already_read(db: Session) -> None:
    user = create_demo_user(db, TODAY)
    assert is_demo(user)
    documents = documents_of(db, user)
    assert len(documents) == 30
    assert {d.status for d in documents} == {DocumentStatus.ok, DocumentStatus.to_check}
    assert all(d.file.startswith(b"%PDF") for d in documents)


def test_demo_purchases_have_the_expected_verdicts(db: Session) -> None:
    user = create_demo_user(db, TODAY)
    result = build_purchases(documents_of(db, user), TODAY)
    verdicts = {p.key: p.status.value for p in result.data}
    expected = demo.json.loads((demo.DEMO_DIR / "expected.json").read_text("utf-8"))
    assert verdicts == {
        reference_key(p["order_reference"]): p["status"] for p in expected["purchases"]
    }
    late = {p.order_reference for p in result.data if p.late}
    assert late == {"CMD-26-107", "CMD-26-109", "CMD-26-110"}


def test_each_visitor_gets_their_own_account(db: Session) -> None:
    first, second = create_demo_user(db, TODAY), create_demo_user(db, TODAY)
    assert first.id != second.id
    assert first.email.endswith(f"@{DEMO_DOMAIN}")


def test_old_demo_accounts_are_removed(db: Session) -> None:
    old = create_demo_user(db, TODAY)
    old_id = old.id
    old.created_at = (
        (old.created_at or demo.get_datetime_utc())
        - DEMO_LIFETIME
        - timedelta(minutes=1)
    )
    db.add(old)
    db.commit()
    create_demo_user(db, TODAY)
    db.expire_all()
    assert db.get(User, old_id) is None
    assert db.exec(select(Document).where(Document.owner_id == old_id)).all() == []


def test_real_accounts_are_never_removed(db: Session) -> None:
    real = db.exec(
        select(User).where(col(User.email).not_like(f"%@{DEMO_DOMAIN}"))
    ).first()
    assert real is not None
    create_demo_user(db, TODAY)
    assert db.get(User, real.id) is not None


def test_too_many_demo_accounts(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo, "MAX_DEMO_USERS", 0)
    with pytest.raises(DemoUnavailable):
        create_demo_user(db, TODAY)
