import io
import zipfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.api.routes.test_reconciliations import URL, deposit
from tests.utils.invoice import purchase_documents

EXPORT = f"{settings.API_V1_STR}/documents/export"


@pytest.fixture(autouse=True)
def fake_ai() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


def read_zip(content: bytes) -> tuple[list[str], list[str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        table = archive.read("factures.csv").decode("utf-8-sig")
    return names, table.splitlines()


def test_export_for_the_accountant(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("EXP-1"))
    client.post(f"{URL}EXP1/pay", headers=normal_user_token_headers)

    r = client.get(EXPORT, headers=normal_user_token_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    names, rows = read_zip(r.content)
    assert rows[0].startswith("Date;Fournisseur;Numéro;Type")
    line = next(row for row in rows if ";FA-EXP-1;" in row)
    assert line.startswith(
        "06/10/2026;Rexel;FA-EXP-1;Facture;EXP-1;101,50;20,30;121,80;"
    )
    # Paid today: the date is there.
    assert line.split(";")[9]
    assert "factures/2026-10-06_Rexel_FA-EXP-1.pdf" in names


def test_export_one_month(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("EXP-2"))
    r = client.get(
        EXPORT, headers=normal_user_token_headers, params={"month": "2026-10"}
    )
    assert r.status_code == 200
    r = client.get(
        EXPORT, headers=normal_user_token_headers, params={"month": "2031-01"}
    )
    assert r.status_code == 404
    r = client.get(EXPORT, headers=normal_user_token_headers, params={"month": "nope"})
    assert r.status_code == 400


def test_export_holds_only_my_invoices(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    deposit(client, normal_user_token_headers, *purchase_documents("EXP-3"))
    r = client.get(EXPORT, headers=superuser_token_headers)
    if r.status_code == 200:
        _, rows = read_zip(r.content)
        assert not any("FA-EXP-3" in row for row in rows)
    else:
        assert r.status_code == 404
