# API_SPEC.md

## Status

This document defines the API interface for the **JewelMind-AI** backend (multi-business SaaS version). It establishes the Pydantic schemas (JSON payloads) and HTTP responses for both the frontend (Next.js) and the AI Copilot.

*   **Host**: `http://localhost:8000`
*   **Base Prefix**: `/api`
*   **Framework**: FastAPI

---

## 1. Global Conventions

- All successful responses return HTTP status code `200 OK` unless specified otherwise.
- All request and response bodies use snake_case consistently.
- Operational errors (e.g. invalid file, missing columns) return `400 Bad Request` with an explanatory JSON payload:
  ```json
  { "detail": "Upload failed. Missing required column: purchase_date" }
  ```
- Unhandled server errors return `500 Internal Server Error`.
- **All endpoints marked [AUTH REQUIRED] require a valid JWT bearer token in the `Authorization` header.**
- **All analytics endpoints resolve `business_id` from the request. The server validates that the authenticated user owns the specified business. Frontend must not be trusted to supply `business_id` without server-side ownership verification.**

---

## 2. Foundational Endpoints

### GET `/health`
Health check route for deployment monitoring. No auth required.
*   **Response (200 OK)**:
    ```json
    { "status": "ok" }
    ```

---

## 3. Authentication Endpoints

### POST `/api/auth/register`
Registers a new user account.
*   **Request Body**:
    ```json
    {
      "email": "rajesh@example.com",
      "password": "securepassword",
      "full_name": "Rajesh Mehta"
    }
    ```
*   **Response (201 Created)**:
    ```json
    {
      "user_id": 1,
      "email": "rajesh@example.com",
      "full_name": "Rajesh Mehta",
      "message": "Account created successfully."
    }
    ```

### POST `/api/auth/login`
Authenticates a user and returns a JWT access token.
*   **Request Body**:
    ```json
    {
      "email": "rajesh@example.com",
      "password": "securepassword"
    }
    ```
*   **Response (200 OK)**:
    ```json
    {
      "access_token": "eyJhbGciOi...",
      "token_type": "bearer",
      "user_id": 1,
      "full_name": "Rajesh Mehta"
    }
    ```

---

## 4. Business Management Endpoints [AUTH REQUIRED]

### GET `/api/businesses`
Returns all businesses owned by the authenticated user.
*   **Response (200 OK)**:
    ```json
    {
      "businesses": [
        {
          "business_id": 1,
          "business_name": "Rajesh Jewellers",
          "owner_name": "Rajesh Mehta",
          "email": "rajesh@example.com",
          "created_at": "2026-01-01T10:00:00Z"
        }
      ]
    }
    ```

### POST `/api/businesses`
Creates a new business for the authenticated user.
*   **Request Body**:
    ```json
    {
      "business_name": "Rajesh Jewellers",
      "owner_name": "Rajesh Mehta",
      "email": "rajesh@example.com",
      "phone": "+91-98765-43210"
    }
    ```
*   **Response (201 Created)**:
    ```json
    {
      "business_id": 1,
      "business_name": "Rajesh Jewellers",
      "message": "Business created successfully."
    }
    ```

### GET `/api/businesses/{business_id}`
Returns details for a single business. Server verifies ownership.
*   **Response (200 OK)**: Full business object as above.
*   **Response (403 Forbidden)**: If the authenticated user does not own this business.

---

## 5. Data Ingestion (Upload) Endpoints [AUTH REQUIRED]

These endpoints process CSV/Excel files, validate contents, and persist records tagged to the specified business.

### POST `/api/businesses/{business_id}/upload/{dataset_type}`
*   **Path Parameters**:
    - `business_id` — Server verifies authenticated user owns this business.
    - `dataset_type` — Enum: `products`, `purchases`, `sales`, `metal-rates`
*   **Request Body**: Multipart form data with `file` key containing the CSV/Excel file.
*   **Response (200 OK)**:
    ```json
    {
      "upload_id": "uuid-v4-string",
      "business_id": 1,
      "dataset_type": "sales",
      "rows_processed": 10482,
      "status": "success",
      "warnings": [
        {
          "row": 42,
          "column": "category",
          "message": "Missing product category. Defaulted to 'general'."
        }
      ]
    }
    ```
*   **Response (400 Bad Request)**:
    ```json
    { "detail": "Data Validation Error: Row 18 contains negative selling_price (-120.00)" }
    ```
*   **Response (403 Forbidden)**: Authenticated user does not own this business.

### GET `/api/businesses/{business_id}/upload/data-quality-report/{upload_id}`
Returns the quality report for a previous upload.
*   **Response (200 OK)**:
    ```json
    {
      "upload_id": "uuid-v4-string",
      "business_id": 1,
      "rows_loaded": 10482,
      "rows_valid": 10461,
      "warnings": [
        { "type": "missing_field", "count": 18, "description": "Missing product_category" },
        { "type": "invalid_date", "count": 3, "description": "3 rows with unparseable dates" },
        { "type": "duplicate_row", "count": 7, "description": "7 duplicate rows skipped" }
      ]
    }
    ```

---

## 6. Analytics Endpoints [AUTH REQUIRED]

All analytics endpoints are scoped to a `business_id`. The server validates ownership before executing any query.

### GET `/api/businesses/{business_id}/analytics/dashboard-summary`
Aggregates summary statistics for the dashboard.
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "revenue": 4280000.00,
      "revenue_change_pct": 8.2,
      "gross_profit": 620000.00,
      "profit_change_pct": -12.7,
      "inventory_value": 18400000.00,
      "ageing_stock_value": 1840000.00
    }
    ```

### POST `/api/businesses/{business_id}/analytics/profit-diagnosis`
Triggers variance analysis between two time periods.
*   **Request Body**:
    ```json
    {
      "current_period": {
        "start_date": "2026-06-01T00:00:00Z",
        "end_date": "2026-06-30T23:59:59Z"
      },
      "comparison_period": {
        "start_date": "2026-05-01T00:00:00Z",
        "end_date": "2026-05-31T23:59:59Z"
      }
    }
    ```
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "net_profit_change": -118000.00,
      "base_period_profit": 738000.00,
      "target_period_profit": 620000.00,
      "drivers": [
        { "driver": "sales_volume", "impact": -52000.00, "description": "Decrease in total gold chain sales volume" },
        { "driver": "discount", "impact": -31000.00, "description": "Increase in average customer discount rate" },
        { "driver": "making_charge", "impact": -21000.00, "description": "Drop in realized making charges per gram" },
        { "driver": "product_mix", "impact": -14000.00, "description": "Shift toward lower-margin silver coin categories" },
        { "driver": "metal_margin", "impact": 0.00, "description": "Raw metal rate fluctuation net variance" }
      ]
    }
    ```

### GET `/api/businesses/{business_id}/analytics/inventory-age`
Returns inventory breakdown by ageing buckets.
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "buckets": [
        { "range": "0-30",    "value": 4200000.00, "percentage": 30.4 },
        { "range": "31-90",   "value": 3800000.00, "percentage": 27.5 },
        { "range": "91-180",  "value": 3100000.00, "percentage": 22.5 },
        { "range": "181-365", "value": 1800000.00, "percentage": 13.0 },
        { "range": "365+",    "value": 700000.00,  "percentage": 6.6 }
      ],
      "total_inventory_value": 13600000.00
    }
    ```

### GET `/api/businesses/{business_id}/analytics/inventory-performance`
Lists items classified by inventory performance.
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "dead_stock": [
        { "sku": "DN102", "name": "Diamond Necklace DN102", "age_days": 324, "value": 240000.00 }
      ],
      "slow_movers": [
        { "sku": "SP204", "name": "Silver Payal SP204", "stock_qty": 72, "days_coverage": 216 }
      ],
      "stockout_risks": [
        { "sku": "GC102", "name": "Gold Chain GC102", "stock_qty": 8, "days_coverage": 10 }
      ]
    }
    ```

### GET `/api/businesses/{business_id}/analytics/metal-exposure`
Returns metal exposure metrics for this business.
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "metals": [
        {
          "metal": "gold",
          "inventory_weight_g": 2480.50,
          "weighted_acquisition_rate": 6920.00,
          "today_board_rate": 7250.00,
          "valuation_exposure": 818565.00
        },
        {
          "metal": "silver",
          "inventory_weight_g": 12400.00,
          "weighted_acquisition_rate": 92.40,
          "today_board_rate": 84.00,
          "valuation_exposure": -104160.00
        }
      ]
    }
    ```

---

## 7. Scenario Simulator Endpoint [AUTH REQUIRED]

### POST `/api/businesses/{business_id}/scenario/simulate-rate-shift`
*   **Request Body**:
    ```json
    {
      "metal": "silver",
      "change_percent": -10.0
    }
    ```
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "metal": "silver",
      "change_percent": -10.0,
      "current_valuation": 2760000.00,
      "simulated_valuation": 2484000.00,
      "valuation_movement": -276000.00,
      "most_exposed_categories": [
        { "category": "utensils", "exposure_delta": -184000.00 },
        { "category": "payal",    "exposure_delta": -92000.00 }
      ]
    }
    ```

---

## 8. Proactive Insights / Action Center [AUTH REQUIRED]

### GET `/api/businesses/{business_id}/insights`
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "insights": [
        {
          "id": "insight_001",
          "priority": "HIGH",
          "title": "Aged Inventory Alert",
          "description": "Rs4.2L inventory is older than 180 days.",
          "category": "inventory",
          "evidence_link": "/api/businesses/1/analytics/inventory-age"
        },
        {
          "id": "insight_002",
          "priority": "MEDIUM",
          "title": "Stockout Risk Detected",
          "description": "11 fast-moving products may face stockout risk in under 15 days.",
          "category": "inventory",
          "evidence_link": "/api/businesses/1/analytics/inventory-performance"
        },
        {
          "id": "insight_003",
          "priority": "LOW",
          "title": "Discount Escalation",
          "description": "Average discount rate increased from 3.2% to 4.8% over the past month.",
          "category": "profit",
          "evidence_link": "/api/businesses/1/analytics/profit-diagnosis"
        }
      ]
    }
    ```

---

## 9. AI Copilot Endpoints [AUTH REQUIRED]

### POST `/api/businesses/{business_id}/copilot/ask`
Sends the user's natural language question to the LLM agent. The Copilot operates within the context of the specified business only.
*   **Request Body**:
    ```json
    {
      "question": "Why did my profit drop in June?",
      "conversation_history": []
    }
    ```
*   **Response (200 OK)**:
    ```json
    {
      "business_id": 1,
      "response_text": "Your gross profit in June fell by Rs1.18 lakh compared to May. This was primarily driven by a drop in gold chain sales volume (-Rs52K) and increased discounting (-Rs31K).",
      "evidence": {
        "tool_called": "analyze_profit_change",
        "payload": {
          "net_profit_change": -118000.00,
          "drivers": [
            { "driver": "sales_volume", "impact": -52000.00 },
            { "driver": "discount",     "impact": -31000.00 }
          ]
        }
      }
    }
    ```

---

## 10. Explicitly Deferred

- Any endpoint related to billing, GST, payroll, CRM, or other out-of-scope functionality (see PROJECT_DEFINITION.md).
- ML-backed endpoints (anomaly detection, forecasting) — deferred to Phase 16+, to be documented here once actually planned in detail.
- Role-based access within a business (e.g., staff vs. owner) — deferred to post-MVP.

---

## Change Log

| Date | Change |
|---|---|
| (initial) | Drafted planned endpoint list aligned to 12-week roadmap; nothing implemented yet |
| 2026-07-25 | Added Pydantic JSON schemas for all endpoints |
| 2026-07-25 | Restructured all business-data endpoints under `/api/businesses/{business_id}/` prefix; added auth, business management, and ownership validation |
