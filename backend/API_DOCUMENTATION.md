# 404 Found Backend API Documentation

## Overview
The backend API provides endpoints for transaction management, merchant fee calculations, and desired margin calculations. Built with Flask, SQLAlchemy, and comprehensive validation.

## Base URL
```
http://localhost:5000/api/v1
```

## Environment Configuration
Create a `.env` file in the backend directory (see `.env.example`):
```
FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///app.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5000
```

## Error Response Format
All error responses follow this format:
```json
{
  "success": false,
  "error": "Error message",
  "error_type": "ERROR_TYPE",
  "details": {}
}
```

## Success Response Format
All success responses follow this format:
```json
{
  "success": true,
  "message": "Operation message",
  "data": {}
}
```

---

## Transaction Endpoints

### Upload Transactions
**POST** `/transactions/upload`

Upload transaction data from CSV or Excel file.

**Request:**
- Content-Type: `multipart/form-data`
- Parameters:
  - `file` (required): CSV or Excel file (.csv, .xlsx, .xls)
  - `merchant_id` (optional): Associated merchant ID

**Response:**
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "data": {
    "batch_id": "batch_abc123_20240115120000",
    "filename": "transactions.csv",
    "total_records": 150,
    "stored_records": 148,
    "error_count": 2,
    "errors": [
      {
        "row": 5,
        "column": "transaction_date",
        "error": "Invalid date format",
        "error_type": "INVALID_DATE"
      }
    ],
    "preview": [...]
  }
}
```

**File Format Requirements:**
- Required columns: transaction_id, transaction_date, merchant_id, amount, transaction_type, card_type
- Date format: DD/MM/YYYY
- Amount: Positive decimal (e.g., 150.50)
- transaction_type: 'Sale', 'Refund', or 'Void'
- card_type: 'Visa', 'Mastercard', 'Amex', or 'Discover'

---

### List Transactions
**GET** `/transactions`

Retrieve paginated list of transactions.

**Query Parameters:**
- `page` (optional, default: 1): Page number
- `per_page` (optional, default: 20, max: 100): Records per page
- `merchant_id` (optional): Filter by merchant ID

**Response:**
```json
{
  "success": true,
  "message": "Transactions retrieved successfully",
  "data": [
    {
      "id": 1,
      "transaction_id": "TXN001",
      "transaction_date": "2024-01-15",
      "merchant_id": "MER001",
      "amount": 150.50,
      "transaction_type": "Sale",
      "card_type": "Visa",
      "created_at": "2024-01-15T12:00:00"
    }
  ],
  "pagination": {
    "total": 1000,
    "page": 1,
    "per_page": 20,
    "pages": 50
  }
}
```

---

### Get Single Transaction
**GET** `/transactions/<id>`

Retrieve a specific transaction by ID.

**Response:**
```json
{
  "success": true,
  "message": "Transaction retrieved successfully",
  "data": {
    "id": 1,
    "transaction_id": "TXN001",
    ...
  }
}
```

---

## Calculation Endpoints

### Calculate Merchant Fee (Current Rates)
**POST** `/calculations/merchant-fee`

Calculate fees based on current merchant rates.

**Request Body:**
```json
{
  "transactions": [
    {
      "transaction_id": "TXN001",
      "transaction_date": "15/01/2024",
      "amount": 150.50,
      "transaction_type": "Sale",
      "card_type": "Visa"
    }
  ],
  "mcc": "5812",
  "current_rate": 0.029,
  "fixed_fee": 0.30
}
```

**Response:**
```json
{
  "success": true,
  "message": "Merchant fee calculation completed",
  "data": {
    "transaction_count": 150,
    "total_volume": 25000.00,
    "total_fees": 751.50,
    "effective_rate": 0.03006,
    "average_ticket": 166.67,
    "mcc": "5812",
    "applied_rate": 0.029,
    "fixed_fee": 0.30
  }
}
```

---

### Calculate Desired Margin
**POST** `/calculations/desired-margin`

Calculate required rate to achieve desired profit margin.

**Request Body:**
```json
{
  "transactions": [...],
  "mcc": "5812",
  "desired_margin": 0.015
}
```

**Response:**
```json
{
  "success": true,
  "message": "Desired margin calculation completed",
  "data": {
    "transaction_count": 150,
    "total_volume": 25000.00,
    "average_ticket": 166.67,
    "desired_margin": 0.015,
    "recommended_rate": 0.015,
    "estimated_total_fees": 420.00,
    "estimated_effective_rate": 0.0168,
    "mcc": "5812"
  }
}
```

---

## Merchant Endpoints

### List Merchants
**GET** `/merchants`

Retrieve paginated list of merchants.

**Query Parameters:**
- `page` (optional, default: 1)
- `per_page` (optional, default: 20, max: 100)

**Response:**
```json
{
  "success": true,
  "message": "Merchants retrieved successfully",
  "data": [
    {
      "id": 1,
      "merchant_id": "MER001",
      "merchant_name": "Test Restaurant",
      "mcc": "5812",
      "industry": "Food Service",
      "annual_volume": 500000.00,
      "average_ticket": 150.50,
      "current_rate": 0.029,
      "fixed_fee": 0.30
    }
  ],
  "pagination": {...}
}
```

---

### Get Single Merchant
**GET** `/merchants/<merchant_id>`

Retrieve specific merchant profile.

**Response:**
```json
{
  "success": true,
  "message": "Merchant retrieved successfully",
  "data": {
    "id": 1,
    "merchant_id": "MER001",
    ...
  }
}
```

---

### Create/Update Merchant
**POST** `/merchants`

Create new or update existing merchant profile.

**Request Body:**
```json
{
  "merchant_id": "MER001",
  "merchant_name": "Test Restaurant",
  "mcc": "5812",
  "industry": "Food Service",
  "annual_volume": 500000.00,
  "average_ticket": 150.50,
  "current_rate": 0.029
}
```

**Required Fields:**
- merchant_id
- merchant_name
- mcc (valid 4-digit code)

**Response:**
```json
{
  "success": true,
  "message": "Merchant saved successfully",
  "data": {...}
}
```

---

## MCC (Merchant Category Code) Endpoints

### List All MCCs
**GET** `/mcc-codes`

Get list of all available MCC codes.

**Response:**
```json
{
  "success": true,
  "message": "MCC codes retrieved successfully",
  "data": [
    {
      "code": "5812",
      "description": "Eating Places and Restaurants"
    },
    {
      "code": "5411",
      "description": "Grocery Stores and Supermarkets"
    }
  ]
}
```

---

### Search MCCs
**GET** `/mcc-codes/search`

Search MCC codes by code or description.

**Query Parameters:**
- `q` (required): Search query (minimum 2 characters)

**Response:**
```json
{
  "success": true,
  "message": "Found 3 MCC codes",
  "data": [
    {
      "code": "5812",
      "description": "Eating Places and Restaurants"
    }
  ]
}
```

---

### Get Single MCC
**GET** `/mcc-codes/<mcc_code>`

Retrieve specific MCC details.

**Response:**
```json
{
  "success": true,
  "message": "MCC retrieved successfully",
  "data": {
    "code": "5812",
    "description": "Eating Places and Restaurants"
  }
}
```

---

## Health Endpoints

### Service Health
**GET** `/health`

Check if service is running.

**Response:**
```json
{
  "status": "healthy",
  "service": "ml-backend"
}
```

---

### API Welcome
**GET** `/`

API information endpoint.

**Response:**
```json
{
  "message": "Welcome to 404 Found ML Backend API",
  "status": "success",
  "version": "1.0"
}
```

---

## Data Validation

### Transaction Validation Rules

| Field | Type | Rules | Example |
|-------|------|-------|---------|
| transaction_id | String | Required, unique | "TXN001" |
| transaction_date | Date | Required, DD/MM/YYYY | "15/01/2024" |
| merchant_id | String | Required | "MER001" |
| amount | Decimal | Required, > 0 | 150.50 |
| transaction_type | String | Sale, Refund, Void | "Sale" |
| card_type | String | Visa, Mastercard, Amex, Discover | "Visa" |

### Merchant Validation Rules

| Field | Type | Rules |
|-------|------|-------|
| merchant_id | String | Required, unique |
| merchant_name | String | Required |
| mcc | String | Required, valid 4-digit code |
| industry | String | Optional |
| annual_volume | Decimal | Optional |
| average_ticket | Decimal | Optional |
| current_rate | Decimal | Optional, 0-1 |

---

## Error Codes

| Error Type | Status | Description |
|------------|--------|-------------|
| VALIDATION_ERROR | 400 | Validation failed |
| INVALID_FILE_TYPE | 400 | Unsupported file format |
| MISSING_FILE | 400 | File not provided |
| MISSING_DATA | 400 | Required data missing |
| MISSING_MCC | 400 | MCC code not provided |
| INVALID_MCC | 400 | Invalid MCC code format |
| NOT_FOUND | 404 | Resource not found |
| INTERNAL_SERVER_ERROR | 500 | Server error |

---

## Running the Backend

### Development Mode
```bash
cd backend
pip install -r requirements.txt
python app.py
```

Server runs on `http://localhost:5000`

### Production Mode
```bash
FLASK_ENV=production python app.py
```

---

## CORS Configuration
Frontend can make requests from configured origins:
```
http://localhost:3000 (React dev server)
http://localhost:5000 (API server)
```

Modify `CORS_ORIGINS` in `.env` for different environments.

---

## Database

Using SQLAlchemy ORM with SQLite for development.

**Tables:**
- transactions
- merchants
- calculation_results
- upload_batches

Database automatically initialized on app startup via `db.create_all()`.

---

## Frontend Integration

Update frontend API service (`frontend/src/services/api.js`):

```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api/v1';
```

Set environment variable in `.env`:
```
REACT_APP_API_URL=http://localhost:5000/api/v1
```

---

## Future Enhancements

- [ ] Authentication/Authorization (JWT)
- [ ] Rate limiting
- [ ] Request validation middleware
- [ ] Swagger/OpenAPI documentation
- [ ] Unit tests
- [ ] Integration tests
- [ ] Database migrations (Alembic)
- [ ] Logging and monitoring
- [ ] Performance optimization/caching
- [ ] Advanced reporting endpoints
