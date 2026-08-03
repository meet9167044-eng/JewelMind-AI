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
_UPLOAD_REPORTS: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

PRODUCTS_REQUIRED = ["sku", "product_name", "category", "metal", "purity",
                     "gross_weight", "net_weight"]
PURCHASES_REQUIRED = ["purchase_date", "quantity", "weight",
                      "metal_rate", "metal_cost", "making_cost", "total_cost"]
SALES_REQUIRED = ["sale_date", "quantity", "weight",
                  "selling_price", "making_charge", "discount", "cost_basis"]

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "products":  PRODUCTS_REQUIRED,
    "purchases": PURCHASES_REQUIRED,
    "sales":     SALES_REQUIRED,
}

VALID_CATEGORIES = {
    "chain", "necklace", "payal", "coin", "utensil",
    "ring", "bangle", "earring",
}
VALID_METALS = {"gold", "silver"}


# ---------------------------------------------------------------------------
# Smart Product Resolver for a Business
# ---------------------------------------------------------------------------

class BusinessProductResolver:
    """
    Resolves product references in sales/purchases CSVs to exact DB product_id.
    Supports:
      1. Exact SKU matching (e.g. 'DI101')
      2. Direct DB product_id matching (e.g. 501)
      3. Ordinal / index position matching (e.g. 1st product of this business -> 186th product)
    """
    def __init__(self, db: Session, business_id: int):
        self.db = db
        self.business_id = business_id
        self.products: list[Product] = []
        self.sku_to_id: dict[str, int] = {}
        self.db_id_to_id: dict[int, int] = {}
        self.ordinal_to_id: dict[int, int] = {}
        self.refresh()

    def refresh(self):
        self.products = (
            self.db.query(Product)
            .filter(Product.business_id == self.business_id)
            .order_by(Product.product_id.asc())
            .all()
        )
        self.sku_to_id = {
            p.sku.strip().lower(): p.product_id
            for p in self.products
            if p.sku
        }
        self.db_id_to_id = {
            p.product_id: p.product_id
            for p in self.products
        }
        self.ordinal_to_id = {
            i + 1: p.product_id
            for i, p in enumerate(self.products)
        }

    def resolve(self, row: pd.Series) -> int | None:
        """Resolve a row's product using sku or product_id column."""
        # 1. Try SKU if present
        if "sku" in row and not pd.isna(row["sku"]):
            sku_val = str(row["sku"]).strip().lower()
            if sku_val in self.sku_to_id:
                return self.sku_to_id[sku_val]

        # 2. Try product_id if present
        if "product_id" in row and not pd.isna(row["product_id"]):
            try:
                pid_int = int(float(row["product_id"]))
                # Check direct DB product_id
                if pid_int in self.db_id_to_id:
                    return self.db_id_to_id[pid_int]
                # Check 1-based ordinal index (common in exported datasets)
                if pid_int in self.ordinal_to_id:
                    return self.ordinal_to_id[pid_int]
            except (ValueError, TypeError):
                pass

        # 3. Fallback: check if 'sku' column value was a numeric string matching ordinal or DB ID
        if "sku" in row and not pd.isna(row["sku"]):
            try:
                pid_int = int(float(str(row["sku"]).strip()))
                if pid_int in self.db_id_to_id:
                    return self.db_id_to_id[pid_int]
                if pid_int in self.ordinal_to_id:
                    return self.ordinal_to_id[pid_int]
            except (ValueError, TypeError):
                pass

        return None


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
    # For purchases/sales, either 'sku' OR 'product_id' must be present
    if dataset_type in ("purchases", "sales"):
        if "sku" not in df.columns and "product_id" not in df.columns:
            return ["sku or product_id"] + [col for col in required if col not in df.columns]
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


def _validate_row_purchases(row: pd.Series, idx: int, resolver: BusinessProductResolver) -> list[str]:
    """Validate a single purchases row."""
    errors = []
    pid = resolver.resolve(row)
    if pid is None:
        ref = row.get("sku") if not pd.isna(row.get("sku")) else row.get("product_id")
        errors.append(f"Row {idx}: SKU '{ref}' not found in products for this business")
    try:
        pd.to_datetime(row["purchase_date"])
    except Exception:
        errors.append(f"Row {idx}: 'purchase_date' is not a valid date")
    for col in ["quantity", "weight", "metal_rate", "metal_cost", "making_cost", "total_cost"]:
        try:
            val = float(row[col])
            if val < 0:
                errors.append(f"Row {idx}: '{col}' must be >= 0, got {val}")
        except (TypeError, ValueError):
            errors.append(f"Row {idx}: '{col}' is not a valid number")
    return errors


def _validate_row_sales(row: pd.Series, idx: int, resolver: BusinessProductResolver) -> list[str]:
    """Validate a single sales row."""
    errors = []
    pid = resolver.resolve(row)
    if pid is None:
        ref = row.get("sku") if not pd.isna(row.get("sku")) else row.get("product_id")
        errors.append(f"Row {idx}: SKU '{ref}' not found in products for this business")
    try:
        pd.to_datetime(row["sale_date"])
    except Exception:
        errors.append(f"Row {idx}: 'sale_date' is not a valid date")
    for col in ["quantity", "weight", "selling_price", "making_charge", "discount", "cost_basis"]:
        try:
            val = float(row[col])
            if val < 0:
                errors.append(f"Row {idx}: '{col}' must be >= 0, got {val}")
        except (TypeError, ValueError):
            errors.append(f"Row {idx}: '{col}' is not a valid number")
    return errors


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

    # Clean column names
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Drop business_id column if present (Rule 14)
    if "business_id" in df.columns:
        df = df.drop(columns=["business_id"])
        report["warnings"].append("Column 'business_id' was ignored; business_id is injected server-side.")

    # Drop primary key IDs from file if present
    for drop_col in ("purchase_id", "sale_id"):
        if drop_col in df.columns:
            df = df.drop(columns=[drop_col])

    # For products dataset, drop raw product_id from file (MySQL generates DB product_id)
    if dataset_type == "products" and "product_id" in df.columns:
        df = df.drop(columns=["product_id"])

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
    resolver = BusinessProductResolver(db, business_id)

    accepted_rows = []
    first_warnings = []

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if dataset_type == "products":
            row_errors = _validate_row_products(row, i)
        elif dataset_type == "purchases":
            row_errors = _validate_row_purchases(row, i, resolver)
        else:
            row_errors = _validate_row_sales(row, i, resolver)

        if row_errors:
            # Cap reported warnings at 50 to keep response fast and clean
            if len(first_warnings) < 50:
                first_warnings.extend(row_errors)
            report["rows_rejected"] += 1
        else:
            accepted_rows.append(row)

    if first_warnings:
        if report["rows_rejected"] > 50:
            first_warnings.append(f"... and {report['rows_rejected'] - 50} more row validation errors.")
        report["warnings"].extend(first_warnings)

    # --- Step 4: Bulk Insert Valid Rows ---
    if accepted_rows:
        try:
            if dataset_type == "products":
                # Filter out existing SKUs for this business to avoid duplicates
                existing_skus = {p.sku.strip().lower() for p in resolver.products if p.sku}
                prod_objects = []
                for row in accepted_rows:
                    sku_clean = str(row["sku"]).strip()
                    if sku_clean.lower() in existing_skus:
                        continue  # skip duplicate SKU
                    existing_skus.add(sku_clean.lower())
                    prod_objects.append(Product(
                        business_id  = business_id,
                        sku          = sku_clean,
                        product_name = str(row["product_name"]).strip(),
                        category     = str(row["category"]).strip().lower(),
                        metal        = str(row["metal"]).strip().lower(),
                        purity       = str(row["purity"]).strip(),
                        gross_weight = float(row["gross_weight"]),
                        net_weight   = float(row["net_weight"]),
                    ))
                if prod_objects:
                    db.add_all(prod_objects)
                    db.commit()
                    resolver.refresh()  # refresh resolver with newly inserted products

            elif dataset_type == "purchases":
                purchase_objects = [
                    Purchase(
                        business_id   = business_id,
                        product_id    = resolver.resolve(row),
                        purchase_date = pd.to_datetime(row["purchase_date"]).to_pydatetime(),
                        quantity      = int(float(row["quantity"])),
                        weight        = float(row["weight"]),
                        metal_rate    = float(row["metal_rate"]),
                        metal_cost    = float(row["metal_cost"]),
                        making_cost   = float(row["making_cost"]),
                        total_cost    = float(row["total_cost"]),
                    )
                    for row in accepted_rows
                    if resolver.resolve(row) is not None
                ]
                if purchase_objects:
                    db.add_all(purchase_objects)
                    db.commit()

            else:  # sales
                sale_objects = [
                    Sale(
                        business_id   = business_id,
                        product_id    = resolver.resolve(row),
                        sale_date     = pd.to_datetime(row["sale_date"]).to_pydatetime(),
                        quantity      = int(float(row["quantity"])),
                        weight        = float(row["weight"]),
                        selling_price = float(row["selling_price"]),
                        making_charge = float(row["making_charge"]),
                        discount      = float(row["discount"]),
                        cost_basis    = float(row["cost_basis"]),
                    )
                    for row in accepted_rows
                    if resolver.resolve(row) is not None
                ]
                if sale_objects:
                    db.add_all(sale_objects)
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
# Public: get_quality_report
# ---------------------------------------------------------------------------

def get_quality_report(upload_id: str) -> dict[str, Any] | None:
    return _UPLOAD_REPORTS.get(upload_id)
