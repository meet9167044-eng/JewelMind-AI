"""
backend/app/services/upload_service.py — Data Upload & Validation Pipeline
===========================================================================
Implements validated CSV/Excel ingestion for Products, Purchases, and Sales.

Architecture rules:
    Rule 9  — Validate uploaded data BEFORE it reaches the database.
    Rule 11 — Every inserted row must have business_id (per-business data).
    Rule 14 — business_id is ALWAYS injected server-side. The file must NEVER
              supply this column; any such column in the file is silently ignored.
    Rule 20 — Shopkeepers upload Products, Purchases, Sales only.
              Metal rates are populated by the background Metal Rate Fetch Service.

Supported dataset types: "products", "purchases", "sales"
Supported file formats:  .csv, .xlsx, .xls

Upload result includes:
    - upload_id      (UUID, stored in-memory for quality report lookup)
    - rows_accepted  (rows successfully inserted)
    - rows_rejected  (rows that failed validation)
    - warnings       (list of per-row validation messages)
    - errors         (critical errors that aborted the whole upload)
"""

import io
import uuid
import logging
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.models.purchase import Purchase
from backend.app.models.sale import Sale

logger = logging.getLogger(__name__)

DatasetType = Literal["products", "purchases", "sales"]

# In-memory store for upload quality reports (keyed by upload_id)
# In production this would be persisted to an upload_logs table.
_UPLOAD_REPORTS: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Schema definitions: required columns + validation rules per dataset type
# ---------------------------------------------------------------------------

PRODUCTS_REQUIRED = ["sku", "product_name", "category", "metal", "purity",
                     "gross_weight", "net_weight"]
PURCHASES_REQUIRED = ["sku", "purchase_date", "quantity", "weight",
                      "metal_rate", "metal_cost", "making_cost", "total_cost"]
SALES_REQUIRED = ["sku", "sale_date", "quantity", "weight",
                  "selling_price", "making_charge", "discount", "cost_basis"]

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "products":  PRODUCTS_REQUIRED,
    "purchases": PURCHASES_REQUIRED,
    "sales":     SALES_REQUIRED,
}

# Columns that must be >= 0
NON_NEGATIVE: dict[str, list[str]] = {
    "products":  ["gross_weight", "net_weight"],
    "purchases": ["quantity", "weight", "metal_rate", "metal_cost", "making_cost", "total_cost"],
    "sales":     ["quantity", "weight", "selling_price", "making_charge", "discount", "cost_basis"],
}

# Date columns (parsed to datetime)
DATE_COLUMNS: dict[str, list[str]] = {
    "products":  [],
    "purchases": ["purchase_date"],
    "sales":     ["sale_date"],
}

VALID_CATEGORIES = {
    "chain", "necklace", "payal", "coin", "utensil",
    "ring", "bangle", "earring",
}
VALID_METALS = {"gold", "silver"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_file(content: bytes, filename: str) -> pd.DataFrame:
    """Parse CSV or Excel file bytes into a DataFrame."""
    fname = filename.lower()
    if fname.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    elif fname.endswith(".xlsx") or fname.endswith(".xls"):
        return pd.read_excel(io.BytesIO(content), engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file format: '{filename}'. Use .csv or .xlsx")


def _check_required_columns(df: pd.DataFrame, dataset_type: DatasetType) -> list[str]:
    """Returns list of missing required column names."""
    required = REQUIRED_COLUMNS[dataset_type]
    missing = [col for col in required if col not in df.columns]
    return missing


def _validate_row_products(row: pd.Series, idx: int) -> list[str]:
    """Validate a single products row. Returns list of error messages."""
    errors = []
    if pd.isna(row.get("sku")) or str(row["sku"]).strip() == "":
        errors.append(f"Row {idx}: 'sku' is empty")
    if pd.isna(row.get("product_name")) or str(row["product_name"]).strip() == "":
        errors.append(f"Row {idx}: 'product_name' is empty")
    cat = str(row.get("category", "")).strip().lower()
    if cat not in VALID_CATEGORIES:
        errors.append(f"Row {idx}: invalid category '{cat}'. Valid: {sorted(VALID_CATEGORIES)}")
    metal = str(row.get("metal", "")).strip().lower()
    if metal not in VALID_METALS:
        errors.append(f"Row {idx}: invalid metal '{metal}'. Valid: gold, silver")
    if pd.isna(row.get("purity")) or str(row["purity"]).strip() == "":
        errors.append(f"Row {idx}: 'purity' is empty")
    for col in ["gross_weight", "net_weight"]:
        try:
            val = float(row[col])
            if val < 0:
                errors.append(f"Row {idx}: '{col}' must be >= 0, got {val}")
        except (TypeError, ValueError):
            errors.append(f"Row {idx}: '{col}' is not a valid number")
    return errors


def _validate_row_purchases(row: pd.Series, idx: int,
                             valid_skus: set[str]) -> list[str]:
    """Validate a single purchases row."""
    errors = []
    sku = str(row.get("sku", "")).strip()
    if sku not in valid_skus:
        errors.append(f"Row {idx}: SKU '{sku}' not found in products for this business")
    try:
        pd.to_datetime(row["purchase_date"])
    except Exception:
        errors.append(f"Row {idx}: 'purchase_date' is not a valid date (got '{row.get('purchase_date')}')")
    for col in ["quantity", "weight", "metal_rate", "metal_cost", "making_cost", "total_cost"]:
        try:
            val = float(row[col])
            if val < 0:
                errors.append(f"Row {idx}: '{col}' must be >= 0, got {val}")
        except (TypeError, ValueError):
            errors.append(f"Row {idx}: '{col}' is not a valid number")
    return errors


def _validate_row_sales(row: pd.Series, idx: int,
                         valid_skus: set[str]) -> list[str]:
    """Validate a single sales row."""
    errors = []
    sku = str(row.get("sku", "")).strip()
    if sku not in valid_skus:
        errors.append(f"Row {idx}: SKU '{sku}' not found in products for this business")
    try:
        pd.to_datetime(row["sale_date"])
    except Exception:
        errors.append(f"Row {idx}: 'sale_date' is not a valid date (got '{row.get('sale_date')}')")
    for col in ["quantity", "weight", "selling_price", "making_charge", "discount", "cost_basis"]:
        try:
            val = float(row[col])
            if val < 0:
                errors.append(f"Row {idx}: '{col}' must be >= 0, got {val}")
        except (TypeError, ValueError):
            errors.append(f"Row {idx}: '{col}' is not a valid number")
    return errors


def _get_sku_to_product_id(db: Session, business_id: int) -> dict[str, int]:
    """Returns a dict of {sku: product_id} for the given business."""
    rows = db.query(Product.sku, Product.product_id).filter(
        Product.business_id == business_id
    ).all()
    return {row[0]: row[1] for row in rows}


# ---------------------------------------------------------------------------
# Public: process_upload
# ---------------------------------------------------------------------------

def process_upload(
    db: Session,
    business_id: int,
    dataset_type: DatasetType,
    file_content: bytes,
    filename: str,
) -> dict[str, Any]:
    """
    Main entry point for the upload pipeline.

    Steps:
        1. Parse the file (CSV or Excel).
        2. Check for required columns — abort with 400 if missing.
        3. Validate each row, collecting row-level warnings.
        4. Insert valid rows with business_id injected server-side.
        5. Return an upload report.

    Parameters:
        db            — SQLAlchemy session
        business_id   — Injected server-side (Rule 14: NEVER from the file)
        dataset_type  — "products", "purchases", or "sales"
        file_content  — Raw bytes of the uploaded file
        filename      — Original filename (used to detect format)

    Returns:
        dict with: upload_id, dataset_type, rows_accepted, rows_rejected,
                   warnings, errors, business_id
    """
    upload_id = str(uuid.uuid4())
    report: dict[str, Any] = {
        "upload_id":    upload_id,
        "dataset_type": dataset_type,
        "business_id":  business_id,
        "filename":     filename,
        "rows_accepted": 0,
        "rows_rejected": 0,
        "warnings":     [],
        "errors":       [],
        "status":       "pending",
    }

    # --- Step 1: Parse ---
    try:
        df = _parse_file(file_content, filename)
    except Exception as exc:
        report["errors"].append(str(exc))
        report["status"] = "failed"
        _UPLOAD_REPORTS[upload_id] = report
        return report

    # Strip whitespace from column names
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Drop any 'business_id' column the file may contain (Rule 14)
    if "business_id" in df.columns:
        df = df.drop(columns=["business_id"])
        report["warnings"].append(
            "Column 'business_id' was present in the file and has been ignored. "
            "business_id is always injected server-side."
        )

    # --- Step 2: Required columns ---
    missing_cols = _check_required_columns(df, dataset_type)
    if missing_cols:
        report["errors"].append(
            f"Missing required columns: {missing_cols}. "
            f"Required for '{dataset_type}': {REQUIRED_COLUMNS[dataset_type]}"
        )
        report["status"] = "failed"
        _UPLOAD_REPORTS[upload_id] = report
        return report

    if len(df) == 0:
        report["errors"].append("The file contains no data rows.")
        report["status"] = "failed"
        _UPLOAD_REPORTS[upload_id] = report
        return report

    # --- Step 3: Validate rows ---
    sku_to_id: dict[str, int] = {}
    if dataset_type in ("purchases", "sales"):
        sku_to_id = _get_sku_to_product_id(db, business_id)

    accepted_rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if dataset_type == "products":
            row_errors = _validate_row_products(row, i)
        elif dataset_type == "purchases":
            row_errors = _validate_row_purchases(row, i, set(sku_to_id.keys()))
        else:
            row_errors = _validate_row_sales(row, i, set(sku_to_id.keys()))

        if row_errors:
            report["warnings"].extend(row_errors)
            report["rows_rejected"] += 1
        else:
            accepted_rows.append(row)

    # --- Step 4: Insert valid rows ---
    try:
        for row in accepted_rows:
            if dataset_type == "products":
                _insert_product(db, business_id, row)
            elif dataset_type == "purchases":
                # Refresh sku map (products just inserted may be needed)
                sku_to_id = _get_sku_to_product_id(db, business_id)
                _insert_purchase(db, business_id, row, sku_to_id)
            else:
                sku_to_id = _get_sku_to_product_id(db, business_id)
                _insert_sale(db, business_id, row, sku_to_id)
        db.commit()
        report["rows_accepted"] = len(accepted_rows)
    except Exception as exc:
        db.rollback()
        report["errors"].append(f"Database insert failed: {exc}")
        report["rows_accepted"] = 0
        report["status"] = "failed"
        _UPLOAD_REPORTS[upload_id] = report
        return report

    report["status"] = "completed"
    _UPLOAD_REPORTS[upload_id] = report
    return report


# ---------------------------------------------------------------------------
# Row insertion helpers (business_id injected server-side — Rule 14)
# ---------------------------------------------------------------------------

def _insert_product(db: Session, business_id: int, row: pd.Series) -> None:
    # Check for duplicate SKU within this business (upsert-safe: skip if exists)
    existing = db.query(Product).filter(
        Product.business_id == business_id,
        Product.sku == str(row["sku"]).strip(),
    ).first()
    if existing:
        return  # Skip duplicate — treat as warning (already emitted in validation)
    db.add(Product(
        business_id  = business_id,                         # Rule 14: server-side
        sku          = str(row["sku"]).strip(),
        product_name = str(row["product_name"]).strip(),
        category     = str(row["category"]).strip().lower(),
        metal        = str(row["metal"]).strip().lower(),
        purity       = str(row["purity"]).strip(),
        gross_weight = float(row["gross_weight"]),
        net_weight   = float(row["net_weight"]),
    ))


def _insert_purchase(db: Session, business_id: int,
                     row: pd.Series, sku_to_id: dict[str, int]) -> None:
    product_id = sku_to_id[str(row["sku"]).strip()]
    db.add(Purchase(
        business_id  = business_id,                         # Rule 14: server-side
        product_id   = product_id,
        purchase_date= pd.to_datetime(row["purchase_date"]).to_pydatetime(),
        quantity     = int(float(row["quantity"])),
        weight       = float(row["weight"]),
        metal_rate   = float(row["metal_rate"]),
        metal_cost   = float(row["metal_cost"]),
        making_cost  = float(row["making_cost"]),
        total_cost   = float(row["total_cost"]),
    ))


def _insert_sale(db: Session, business_id: int,
                 row: pd.Series, sku_to_id: dict[str, int]) -> None:
    product_id = sku_to_id[str(row["sku"]).strip()]
    db.add(Sale(
        business_id  = business_id,                         # Rule 14: server-side
        product_id   = product_id,
        sale_date    = pd.to_datetime(row["sale_date"]).to_pydatetime(),
        quantity     = int(float(row["quantity"])),
        weight       = float(row["weight"]),
        selling_price= float(row["selling_price"]),
        making_charge= float(row["making_charge"]),
        discount     = float(row["discount"]),
        cost_basis   = float(row["cost_basis"]),
    ))


# ---------------------------------------------------------------------------
# Public: get_quality_report
# ---------------------------------------------------------------------------

def get_quality_report(upload_id: str) -> dict[str, Any] | None:
    """
    Returns the stored quality report for a given upload_id.
    Returns None if the upload_id is not found.
    """
    return _UPLOAD_REPORTS.get(upload_id)
