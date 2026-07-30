"""
backend/app/routers/upload.py — Data Upload Endpoints
======================================================
Routes:
    POST /api/businesses/{business_id}/upload/{dataset_type}
         Upload a CSV/Excel file of products, purchases, or sales.
         dataset_type must be one of: products, purchases, sales

    GET  /api/businesses/{business_id}/upload/quality-report/{upload_id}
         Retrieve the data quality report for a previous upload.

All routes protected by get_owned_business (authenticated owner only).
business_id is ALWAYS resolved from the route + auth token — never from the
uploaded file itself (PROJECT_RULES.md Rule 14).
"""

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.dependencies.business import get_owned_business
from backend.app.models.business import Business
from backend.app.services import upload_service
from backend.app.services.upload_service import DatasetType

router = APIRouter(
    prefix="/api/businesses/{business_id}/upload",
    tags=["Data Upload"],
)

ALLOWED_DATASET_TYPES = {"products", "purchases", "sales"}
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",   # some clients send this for .xlsx
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/{dataset_type}",
    status_code=200,
    summary="Upload CSV/Excel data for products, purchases, or sales",
)
async def upload_dataset(
    dataset_type: str = Path(..., description="One of: products, purchases, sales"),
    file: UploadFile = File(..., description="CSV or Excel file (.csv, .xlsx)"),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Validates and ingests a CSV or Excel file for the specified dataset.

    **Critical Rule (Rule 14)**: `business_id` is ALWAYS injected server-side.
    The uploaded file must NOT contain a `business_id` column — if it does,
    that column is silently ignored.

    **Validation Checks**:
    - Required columns per DATABASE_SCHEMA.md
    - Non-negative weights, prices, and rates
    - Valid date formats (ISO 8601)
    - Valid category and metal enum values (for products)
    - SKU must exist in this business's products (for purchases/sales)

    **Response**:
    - `upload_id` — use this to fetch the quality report
    - `rows_accepted` — rows successfully inserted
    - `rows_rejected` — rows that failed validation
    - `warnings` — per-row validation messages
    - `errors` — critical errors (missing columns, unparseable file)
    """
    if dataset_type not in ALLOWED_DATASET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid dataset_type '{dataset_type}'. "
                f"Must be one of: {sorted(ALLOWED_DATASET_TYPES)}"
            ),
        )

    # Read file content
    content = await file.read()

    # Size guard
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is 10 MB.",
        )

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "upload.csv"

    result = upload_service.process_upload(
        db=db,
        business_id=business.business_id,
        dataset_type=dataset_type,  # type: ignore[arg-type]
        file_content=content,
        filename=filename,
    )

    # If there were critical errors (missing columns, parse failure), return 400
    if result["errors"] and result["rows_accepted"] == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "message":  "Upload failed due to validation errors.",
                "upload_id": result["upload_id"],
                "errors":   result["errors"],
                "warnings": result["warnings"],
            },
        )

    return result


@router.get(
    "/quality-report/{upload_id}",
    summary="Retrieve the data quality report for a previous upload",
)
def get_quality_report(
    upload_id: str = Path(..., description="upload_id returned by the upload endpoint"),
    business: Business = Depends(get_owned_business),
    db: Session = Depends(get_db),
):
    """
    Returns the stored quality report for a given `upload_id`.

    The report includes:
    - rows_accepted / rows_rejected counts
    - Per-row validation warnings
    - Any critical errors that caused the upload to fail
    """
    report = upload_service.get_quality_report(upload_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"No upload report found for upload_id '{upload_id}'.",
        )
    # Enforce ownership: the report's business_id must match the route
    if report.get("business_id") != business.business_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return report
