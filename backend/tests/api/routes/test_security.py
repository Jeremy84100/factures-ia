import io
import zipfile
from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.core import rate_limit as rate_limit_mod
from app.core import security
from app.core.config import settings
from app.crud import create_user
from app.models import (
    MAX_LINES,
    Document,
    DocumentKind,
    DocumentStatus,
    LineFields,
    UserCreate,
)
from app.services import extraction
from app.services.einvoice import parse_cii
from app.services.export import build_export, safe_cell
from app.services.images import ImageError, image_to_pdf
from app.services.processing import to_lines
from app.utils import generate_password_reset_token, render_email_template
from tests.utils.utils import random_email, random_lower_string

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def enable_rate_limits(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    rate_limit_mod.reset_rate_limits()
    yield
    rate_limit_mod.reset_rate_limits()


def _demo_headers(client: TestClient) -> dict[str, str]:
    r = client.post(f"{settings.API_V1_STR}/login/demo")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demo_user_cannot_upload_retry_or_edit_profile(client: TestClient) -> None:
    headers = _demo_headers(client)

    upload = client.post(
        f"{settings.API_V1_STR}/documents/",
        headers=headers,
        files=[("files", ("facture.pdf", MINIMAL_PDF, "application/pdf"))],
    )
    assert upload.status_code == 403

    docs = client.get(f"{settings.API_V1_STR}/documents/", headers=headers).json()[
        "data"
    ]
    assert docs
    retry = client.post(
        f"{settings.API_V1_STR}/documents/{docs[0]['id']}/retry",
        headers=headers,
    )
    assert retry.status_code == 403

    edit = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
        json={"email": random_email()},
    )
    assert edit.status_code == 403


def test_cannot_signup_or_change_email_to_demo_domain(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    signup = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json={
            "email": "attacker@demo.example.com",
            "password": "StrongPassword123",
            "full_name": "Attacker",
        },
    )
    assert signup.status_code == 400

    update = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json={"email": "escaped@demo.example.com"},
    )
    assert update.status_code == 400


def test_rate_limit_blocks_excess_and_prunes_buckets(
    client: TestClient,
    enable_rate_limits: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = enable_rate_limits
    rate_limit_mod.check_rate_limit("unit", "ip-1", limit=2, window_seconds=60)
    rate_limit_mod.check_rate_limit("unit", "ip-1", limit=2, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        rate_limit_mod.check_rate_limit("unit", "ip-1", limit=2, window_seconds=60)
    assert exc.value.status_code == 429
    assert exc.value.headers is not None
    assert int(exc.value.headers["Retry-After"]) >= 1

    # Pruning keeps bucket count bounded under MAX_BUCKETS.
    monkeypatch.setattr(rate_limit_mod, "MAX_BUCKETS", 2)
    rate_limit_mod.check_rate_limit("unit", "ip-2", limit=5, window_seconds=60)
    rate_limit_mod.check_rate_limit("unit", "ip-3", limit=5, window_seconds=60)
    assert len(rate_limit_mod._buckets) <= 2

    # HTTP route reads the rightmost proxy-appended X-Forwarded-For IP, so
    # spoofing a different leftmost IP on every request cannot bypass the limit.
    for i in range(15):
        r = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "nobody@example.com", "password": "wrongpassword"},
            headers={"X-Forwarded-For": f"198.51.100.{i}, 203.0.113.42"},
        )
        assert r.status_code == 400
    blocked = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "nobody@example.com", "password": "wrongpassword"},
        headers={"X-Forwarded-For": "198.51.100.99, 203.0.113.42"},
    )
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers


def test_jwt_purpose_separation_and_malformed_sub(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    password = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(email=email, password=password, full_name="JWT Test"),
    )

    # A password reset token cannot be used as an API Bearer token (403, not 500).
    reset_token = generate_password_reset_token(
        email=email,
        password_fingerprint=security.password_fingerprint(user.hashed_password),
    )
    r = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {reset_token}"},
    )
    assert r.status_code == 403

    # A malformed non-UUID sub returns 403 instead of crashing with ValueError/500.
    bad_sub_token = jwt.encode(
        {"sub": "not-a-uuid", "purpose": "access"},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    r = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": f"Bearer {bad_sub_token}"},
    )
    assert r.status_code == 403

    # An access token cannot be used on /reset-password/.
    access_token = security.create_access_token(
        user.id, expires_delta=timedelta(minutes=5)
    )
    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json={"token": access_token, "new_password": "NewPassword123"},
    )
    assert r.status_code == 400


def test_password_reset_token_is_single_use(client: TestClient, db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(email=email, password=password, full_name="Reset Once"),
    )
    token = generate_password_reset_token(
        email=email,
        password_fingerprint=security.password_fingerprint(user.hashed_password),
    )

    first = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json={"token": token, "new_password": "FirstNewPassword1"},
    )
    assert first.status_code == 200

    replay = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json={"token": token, "new_password": "SecondNewPassword2"},
    )
    assert replay.status_code == 400


def test_csv_export_neutralizes_formulas_and_keeps_negative_amounts() -> None:
    assert safe_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert safe_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert safe_cell("-1+1") == "'-1+1"
    assert safe_cell("@SUM(1,1)") == "'@SUM(1,1)"
    assert safe_cell("\t=1") == "'\t=1"
    assert safe_cell("Rexel") == "Rexel"
    assert safe_cell(None) == ""

    doc = Document(
        filename="avoir.pdf",
        file=MINIMAL_PDF,
        kind=DocumentKind.invoice,
        status=DocumentStatus.ok,
        is_credit_note=True,
        document_date=date(2026, 10, 6),
        supplier='=HYPERLINK("http://evil.test","Cliquez")',
        number="+AV-1",
        order_reference="@CMD-1",
        amount_excl_tax=Decimal("-100.00"),
        vat_amount=Decimal("-20.00"),
        amount_incl_tax=Decimal("-120.00"),
        currency="EUR",
    )
    archive_bytes = build_export([doc], {})
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        csv_text = archive.read("factures.csv").decode("utf-8-sig")
    data_row = csv_text.splitlines()[1]
    assert "'=HYPERLINK" in data_row
    assert ";'+AV-1;" in data_row
    assert ";'@CMD-1;" in data_row
    # Negative amounts stay numeric for Excel formulas and sums.
    assert ";-100,00;-20,00;-120,00;" in data_row


def test_email_template_escapes_html_injection() -> None:
    html = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": "<script>alert(1)</script>",
            "username": "<img src=x onerror=alert(1)>",
            "password": "secret",
            "email": "user@example.com",
            "link": "https://example.com",
        },
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x onerror=alert(1)>" not in html


def test_image_decompression_bomb_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Image.MAX_IMAGE_PIXELS == 25_000_000
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), color="white").save(buf, format="PNG")
    raw = buf.getvalue()

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ImageError):
        image_to_pdf(raw)


def test_security_headers_and_pdf_csp(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=(self)" in r.headers["permissions-policy"]
    assert "microphone=()" in r.headers["permissions-policy"]
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]

    monkeypatch.setattr(settings, "FASTAPI_ENV", None)
    prod = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert prod.headers["strict-transport-security"].startswith("max-age=31536000")

    headers = _demo_headers(client)
    docs = client.get(f"{settings.API_V1_STR}/documents/", headers=headers).json()[
        "data"
    ]
    pdf = client.get(
        f"{settings.API_V1_STR}/documents/{docs[0]['id']}/file", headers=headers
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )
    assert pdf.headers["x-content-type-options"] == "nosniff"


def test_extraction_separates_system_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "document externe non fiable" in extraction.PROMPT
    assert "ignore" in extraction.PROMPT.lower()

    captured: dict[str, Any] = {}

    class _FakeModels:
        def generate_content(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return type("Resp", (), {"parsed": extraction.ExtractedDocument()})()

    fake_client = type("FakeClient", (), {"models": _FakeModels()})()
    monkeypatch.setattr(extraction, "_gemini_client", lambda _key: fake_client)

    result = extraction.GeminiExtractor(
        api_key="test-key", model="gemini-test"
    ).extract(MINIMAL_PDF)
    assert isinstance(result, extraction.ExtractedDocument)
    assert captured["config"].system_instruction == extraction.PROMPT
    assert isinstance(captured["contents"], list)
    assert extraction.PROMPT not in str(captured["contents"])


def test_pagination_and_export_month_validation(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    docs_url = f"{settings.API_V1_STR}/documents/"
    users_url = f"{settings.API_V1_STR}/users/"
    export_url = f"{settings.API_V1_STR}/documents/export"

    assert (
        client.get(
            docs_url, headers=normal_user_token_headers, params={"skip": -1}
        ).status_code
        == 422
    )
    assert (
        client.get(
            docs_url, headers=normal_user_token_headers, params={"limit": 0}
        ).status_code
        == 422
    )
    assert (
        client.get(
            docs_url, headers=normal_user_token_headers, params={"limit": 501}
        ).status_code
        == 422
    )
    assert (
        client.get(
            users_url, headers=superuser_token_headers, params={"skip": -1}
        ).status_code
        == 422
    )
    assert (
        client.get(
            users_url, headers=superuser_token_headers, params={"limit": 501}
        ).status_code
        == 422
    )

    assert (
        client.get(
            export_url, headers=normal_user_token_headers, params={"month": "9999-12"}
        ).status_code
        == 400
    )
    assert (
        client.get(
            export_url,
            headers=normal_user_token_headers,
            params={"month": "2026-11\r\n"},
        ).status_code
        == 400
    )


def test_document_lines_capped_and_xml_dtd_rejected(client: TestClient) -> None:
    headers = _demo_headers(client)
    docs = client.get(f"{settings.API_V1_STR}/documents/", headers=headers).json()[
        "data"
    ]
    too_many = [{"description": f"Ligne {i}"} for i in range(MAX_LINES + 1)]
    r = client.put(
        f"{settings.API_V1_STR}/documents/{docs[0]['id']}",
        headers=headers,
        json={"lines": too_many},
    )
    assert r.status_code == 422

    capped = to_lines(
        [LineFields(description=f"Ligne {i}") for i in range(MAX_LINES + 50)]
    )
    assert len(capped) == MAX_LINES

    dtd_xml = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE foo [<!ENTITY x "boom">]>'
        b'<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"/>'
    )
    assert parse_cii(dtd_xml) is None


def test_email_is_case_insensitive_on_signup_and_login(client: TestClient) -> None:
    raw_email = f"Jean.{random_lower_string()}@Example.COM"
    password = "StrongPassword123"

    signup = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json={"email": raw_email, "password": password, "full_name": "Jean"},
    )
    assert signup.status_code == 200
    assert signup.json()["email"] == raw_email.lower()

    duplicate = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json={"email": raw_email.lower(), "password": password, "full_name": "Jean 2"},
    )
    assert duplicate.status_code == 400

    login = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": raw_email.upper(), "password": password},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]
