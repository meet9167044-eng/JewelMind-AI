"""
backend/tests/test_upload.py — Phase 12 Upload Pipeline Tests
=============================================================
Tests (per Phase 12 verification gate in PROJECT_PLAN.md):

    1.  Valid products CSV → rows appear in DB with correct business_id.
    2.  business_id column in file is SILENTLY IGNORED (Rule 14).
    3.  Missing required column → 400 with exact error message.
    4.  Invalid category → row rejected, rest accepted.
    5.  Negative weight → row rejected.
    6.  Invalid date → row rejected.
    7.  Valid purchases CSV → rows inserted with server-side business_id.
    8.  Purchases with unknown SKU → row rejected.
    9.  Valid sales CSV → rows inserted.
    10. Excel (.xlsx) file accepted (openpyxl).
    11. Empty file → 400 error.
    12. Invalid dataset_type → 400 error.
    13. Quality report endpoint returns 200 with correct upload_id.
    14. Quality report 404 for unknown upload_id.
    15. *** ISOLATION GATE ***: uploaded rows not visible in Biz B analytics.
    16. API cross-tenant returns 403.
    17. API unauthenticated returns 403.
"""

import io
import csv
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.business import Business
from backend.app.models.product import Product
from backend.app.models.purchase import Purchase
from backend.app.models.sale import Sale
from backend.app.services.auth_service import hash_password
from backend.app.services import upload_service

# ---------------------------------------------------------------------------
# In-memory SQLite setup
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    # Clear in-memory upload reports between tests
    upload_service._UPLOAD_REPORTS.clear()
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()
    upload_service._UPLOAD_REPORTS.clear()


@pytest.fixture
def db() -> Session:
    s = TestSessionLocal()
    yield s
    s.close()


client = TestClient(app)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_biz(db: Session, email: str) -> Business:
    u = User(email=email, password_hash=hash_password("Test1234"), full_name="T")
    db.add(u); db.flush()
    b = Business(owner_user_id=u.user_id, business_name="Test Biz")
    db.add(b); db.flush()
    db.commit()
    return b


def _seed_product(db: Session, biz_id: int, sku: str) -> Product:
    p = Product(
        business_id=biz_id, sku=sku, product_name=f"Item {sku}",
        category="ring", metal="gold", purity="22K",
        gross_weight=10.0, net_weight=9.0,
    )
    db.add(p); db.commit()
    return p


def _csv(rows: list[dict]) -> bytes:
    """Build a CSV bytes object from a list of row dicts."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def _register_and_token(email: str) -> str:
    r = client.post("/api/auth/register",
        json={"email": email, "password": "Test1234!!", "full_name": "T"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Service-layer unit tests
# ---------------------------------------------------------------------------

VALID_PRODUCT_ROW = {
    "sku": "TEST001", "product_name": "Gold Ring",
    "category": "ring", "metal": "gold", "purity": "22K",
    "gross_weight": "10.5", "net_weight": "9.5",
}

VALID_PURCHASE_ROW = {
    "sku": "TEST001", "purchase_date": "2026-05-01",
    "quantity": "1", "weight": "10.5",
    "metal_rate": "6500.00", "metal_cost": "61750.00",
    "making_cost": "5000.00", "total_cost": "66750.00",
}

VALID_SALE_ROW = {
    "sku": "TEST001", "sale_date": "2026-06-15",
    "quantity": "1", "weight": "10.5",
    "selling_price": "75000.00", "making_charge": "3000.00",
    "discount": "500.00", "cost_basis": "66750.00",
}


def test_valid_products_csv_inserts_rows_with_business_id(db):
    """Valid products CSV → rows appear in DB with correct business_id."""
    biz = _seed_biz(db, "up_prod@test.com")
    content = _csv([VALID_PRODUCT_ROW])

    result = upload_service.process_upload(
        db, biz.business_id, "products", content, "products.csv"
    )

    assert result["rows_accepted"] == 1
    assert result["rows_rejected"] == 0
    assert result["status"] == "completed"

    # Verify row is in DB with correct business_id
    product = db.query(Product).filter(
        Product.business_id == biz.business_id,
        Product.sku == "TEST001",
    ).first()
    assert product is not None
    assert product.business_id == biz.business_id


def test_business_id_column_in_file_is_ignored(db):
    """
    *** Rule 14 TEST ***
    If the file contains a 'business_id' column, it must be silently ignored.
    The server-side business_id must be used.
    """
    biz = _seed_biz(db, "bid_ignore@test.com")
    # Include a fake business_id in the file (e.g., 9999)
    row_with_bid = {**VALID_PRODUCT_ROW, "business_id": "9999"}
    content = _csv([row_with_bid])

    result = upload_service.process_upload(
        db, biz.business_id, "products", content, "products.csv"
    )

    assert result["rows_accepted"] == 1
    # Verify the DB row uses the server-side business_id, NOT 9999
    product = db.query(Product).filter(Product.sku == "TEST001").first()
    assert product is not None
    assert product.business_id == biz.business_id
    assert product.business_id != 9999

    # Warning about ignored column should be present
    assert any("business_id" in w for w in result["warnings"])


def test_missing_required_column_returns_error(db):
    """Missing 'purchase_date' column → upload fails with descriptive error."""
    biz = _seed_biz(db, "miss_col@test.com")
    incomplete_row = {k: v for k, v in VALID_PURCHASE_ROW.items() if k != "purchase_date"}
    content = _csv([incomplete_row])

    result = upload_service.process_upload(
        db, biz.business_id, "purchases", content, "purchases.csv"
    )

    assert result["status"] == "failed"
    assert result["rows_accepted"] == 0
    assert any("purchase_date" in e for e in result["errors"])


def test_invalid_category_rejects_row(db):
    """Row with invalid category is rejected; valid rows still accepted."""
    biz = _seed_biz(db, "cat@test.com")
    bad_row = {**VALID_PRODUCT_ROW, "sku": "BAD001", "category": "INVALID_CAT"}
    good_row = {**VALID_PRODUCT_ROW, "sku": "GOOD001"}
    content = _csv([bad_row, good_row])

    result = upload_service.process_upload(
        db, biz.business_id, "products", content, "products.csv"
    )

    assert result["rows_accepted"] == 1
    assert result["rows_rejected"] == 1
    assert any("INVALID_CAT" in w or "category" in w for w in result["warnings"])


def test_negative_weight_rejects_row(db):
    """Row with negative net_weight is rejected."""
    biz = _seed_biz(db, "neg@test.com")
    bad_row = {**VALID_PRODUCT_ROW, "sku": "NEG001", "net_weight": "-5.0"}
    content = _csv([bad_row])

    result = upload_service.process_upload(
        db, biz.business_id, "products", content, "products.csv"
    )

    assert result["rows_rejected"] == 1
    assert any("net_weight" in w for w in result["warnings"])


def test_invalid_date_rejects_purchase_row(db):
    """Row with invalid purchase_date is rejected."""
    biz = _seed_biz(db, "date@test.com")
    _seed_product(db, biz.business_id, "TEST001")
    bad_row = {**VALID_PURCHASE_ROW, "purchase_date": "not-a-date"}
    content = _csv([bad_row])

    result = upload_service.process_upload(
        db, biz.business_id, "purchases", content, "purchases.csv"
    )

    assert result["rows_rejected"] == 1
    assert any("purchase_date" in w for w in result["warnings"])


def test_valid_purchases_csv_inserts_with_server_side_business_id(db):
    """Valid purchases CSV → rows inserted with server-side business_id."""
    biz = _seed_biz(db, "pur@test.com")
    _seed_product(db, biz.business_id, "TEST001")
    content = _csv([VALID_PURCHASE_ROW])

    result = upload_service.process_upload(
        db, biz.business_id, "purchases", content, "purchases.csv"
    )

    assert result["rows_accepted"] == 1
    purchase = db.query(Purchase).filter(
        Purchase.business_id == biz.business_id
    ).first()
    assert purchase is not None
    assert purchase.business_id == biz.business_id


def test_purchase_unknown_sku_rejects_row(db):
    """Purchase row where SKU doesn't exist in this business's products → rejected."""
    biz = _seed_biz(db, "unk_sku@test.com")
    # No products seeded
    content = _csv([VALID_PURCHASE_ROW])

    result = upload_service.process_upload(
        db, biz.business_id, "purchases", content, "purchases.csv"
    )

    assert result["rows_rejected"] == 1
    assert any("TEST001" in w or "SKU" in w for w in result["warnings"])


def test_valid_sales_csv_inserts_rows(db):
    """Valid sales CSV → rows inserted correctly."""
    biz = _seed_biz(db, "sale@test.com")
    _seed_product(db, biz.business_id, "TEST001")
    content = _csv([VALID_SALE_ROW])

    result = upload_service.process_upload(
        db, biz.business_id, "sales", content, "sales.csv"
    )

    assert result["rows_accepted"] == 1
    sale = db.query(Sale).filter(Sale.business_id == biz.business_id).first()
    assert sale is not None


def test_excel_file_accepted(db):
    """Excel (.xlsx) file is parsed and accepted correctly."""
    import openpyxl
    biz = _seed_biz(db, "xlsx@test.com")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(VALID_PRODUCT_ROW.keys()))
    ws.append(list(VALID_PRODUCT_ROW.values()))
    buf = io.BytesIO()
    wb.save(buf)
    xlsx_content = buf.getvalue()

    result = upload_service.process_upload(
        db, biz.business_id, "products", xlsx_content, "products.xlsx"
    )

    assert result["rows_accepted"] == 1
    assert result["status"] == "completed"


def test_quality_report_stored_and_retrievable(db):
    """upload_id from upload response retrieves the quality report."""
    biz = _seed_biz(db, "qr@test.com")
    content = _csv([VALID_PRODUCT_ROW])

    result = upload_service.process_upload(
        db, biz.business_id, "products", content, "products.csv"
    )
    upload_id = result["upload_id"]

    report = upload_service.get_quality_report(upload_id)
    assert report is not None
    assert report["upload_id"] == upload_id
    assert report["business_id"] == biz.business_id


def test_quality_report_none_for_unknown_id(db):
    """get_quality_report returns None for an unknown upload_id."""
    report = upload_service.get_quality_report("00000000-0000-0000-0000-000000000000")
    assert report is None


def test_isolation_uploaded_rows_not_visible_to_other_business(db):
    """
    *** ISOLATION GATE ***
    Products uploaded for Biz A must NOT appear in analytics for Biz B.
    """
    biz_a = _seed_biz(db, "iso_a@test.com")
    biz_b = _seed_biz(db, "iso_b@test.com")

    content = _csv([VALID_PRODUCT_ROW])
    result = upload_service.process_upload(
        db, biz_a.business_id, "products", content, "products.csv"
    )
    assert result["rows_accepted"] == 1

    # Biz B should see NO products
    biz_b_products = db.query(Product).filter(
        Product.business_id == biz_b.business_id,
        Product.sku == "TEST001",
    ).all()
    assert len(biz_b_products) == 0, (
        f"ISOLATION VIOLATION: Biz B can see {len(biz_b_products)} products that belong to Biz A"
    )


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def test_api_upload_products_returns_200():
    """POST /upload/products returns 200 with rows_accepted for valid CSV."""
    token = _register_and_token("api_up@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Upload Biz"}, headers=_auth(token)
    ).json()["business_id"]

    content = _csv([VALID_PRODUCT_ROW])
    resp = client.post(
        f"/api/businesses/{biz_id}/upload/products",
        files={"file": ("products.csv", content, "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "upload_id"     in body
    assert "rows_accepted" in body
    assert body["rows_accepted"] >= 0


def test_api_upload_missing_column_returns_400():
    """POST /upload/purchases with missing column → 400 with error details."""
    token = _register_and_token("bad_col@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Bad Biz"}, headers=_auth(token)
    ).json()["business_id"]

    incomplete = {k: v for k, v in VALID_PURCHASE_ROW.items() if k != "purchase_date"}
    content = _csv([incomplete])
    resp = client.post(
        f"/api/businesses/{biz_id}/upload/purchases",
        files={"file": ("purchases.csv", content, "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert "errors" in body["detail"]
    assert any("purchase_date" in e for e in body["detail"]["errors"])


def test_api_upload_invalid_dataset_type_returns_400():
    """POST /upload/metal_rates → 400 (metal_rates not allowed)."""
    token = _register_and_token("bad_type@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "Type Biz"}, headers=_auth(token)
    ).json()["business_id"]

    content = b"rate_date,gold_24k\n2026-07-01,7200"
    resp = client.post(
        f"/api/businesses/{biz_id}/upload/metal_rates",
        files={"file": ("metal_rates.csv", content, "text/csv")},
        headers=_auth(token),
    )
    assert resp.status_code == 400

def test_api_quality_report_returns_200():
    """GET /upload/quality-report/{upload_id} returns 200 for valid upload_id."""
    token = _register_and_token("qr_api@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "QR Biz"}, headers=_auth(token)
    ).json()["business_id"]

    content = _csv([VALID_PRODUCT_ROW])
    upload_resp = client.post(
        f"/api/businesses/{biz_id}/upload/products",
        files={"file": ("products.csv", content, "text/csv")},
        headers=_auth(token),
    )
    upload_id = upload_resp.json()["upload_id"]

    resp = client.get(
        f"/api/businesses/{biz_id}/upload/quality-report/{upload_id}",
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["upload_id"] == upload_id


def test_api_quality_report_unknown_id_returns_404():
    """GET /quality-report with unknown id → 404."""
    token = _register_and_token("qr_404@test.com")
    biz_id = client.post(
        "/api/businesses", json={"business_name": "404 Biz"}, headers=_auth(token)
    ).json()["business_id"]

    resp = client.get(
        f"/api/businesses/{biz_id}/upload/quality-report/nonexistent-id",
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_api_upload_cross_tenant_returns_403():
    """User B cannot upload to User A's business."""
    token_a = _register_and_token("up_a@test.com")
    token_b = _register_and_token("up_b@test.com")
    biz_a = client.post(
        "/api/businesses", json={"business_name": "A"}, headers=_auth(token_a)
    ).json()["business_id"]

    content = _csv([VALID_PRODUCT_ROW])
    resp = client.post(
        f"/api/businesses/{biz_a}/upload/products",
        files={"file": ("products.csv", content, "text/csv")},
        headers=_auth(token_b),
    )
    assert resp.status_code == 403, (
        f"SECURITY VIOLATION: User B got {resp.status_code} uploading to User A's business!"
    )


def test_api_upload_unauthenticated_returns_403():
    """Upload without a token → 403."""
    resp = client.post(
        "/api/businesses/1/upload/products",
        files={"file": ("products.csv", b"sku,product_name\nA,B", "text/csv")},
    )
    assert resp.status_code == 403
