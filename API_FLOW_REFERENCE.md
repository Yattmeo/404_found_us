# Frontend-Backend API Call Flow Reference

## Quick Visual Guide: How Data Flows Through Your Application

---

## 1. CSV/Excel File Upload Flow

```
User uploads file
    ↓
[DataUploadValidator Component]
    ↓
File selected → Backend API Call
    ↓
merchantFeeAPI.uploadTransactionData(file)
    ↓
POST /api/v1/transactions/upload
    ↓
[Flask Backend - routes.py]
@transactions_bp.route('/upload', methods=['POST'])
    ↓
Validates file format (CSV/XLSX)
    ↓
DataProcessingService.parse_csv_file() or parse_excel_file()
    ↓
TransactionValidator validates each row
    ↓
Stores to database (Transaction model)
    ↓
Returns JSON response:
{
  "batch_id": "batch_...",
  "stored_records": 150,
  "errors": [],
  "preview": [first 10 rows]
}
    ↓
Frontend displays preview & confirmation
```

---

## 2. Merchant Fee Calculation Flow

```
User enters transaction data + MCC + rate
    ↓
[EnhancedMerchantFeeCalculator Component]
    ↓
Clicks "Proceed to Projection"
    ↓
merchantFeeAPI.calculateCurrentRates(
  transactions: [...],
  mcc: "5812",
  currentRate: 0.029,
  fixedFee: 0.30
)
    ↓
POST /api/v1/calculations/merchant-fee
    ↓
[Flask Backend - routes.py]
@calculations_bp.route('/merchant-fee', methods=['POST'])
    ↓
MerchantFeeCalculationService.calculate_current_rates()
    ↓
Calculation logic:
- total_volume = sum of all amounts
- total_fees = (volume × rate) + (count × fixed_fee)
- effective_rate = total_fees / total_volume
- average_ticket = total_volume / count
    ↓
Stores result to CalculationResult model
    ↓
Returns JSON response:
{
  "transaction_count": 150,
  "total_volume": 25000.00,
  "total_fees": 751.50,
  "effective_rate": 0.03006,
  "average_ticket": 166.67,
  "mcc": "5812"
}
    ↓
Frontend displays results in ResultsPanel
```

---

## 3. Desired Margin Calculation Flow

```
User enters merchant data + MCC + desired margin
    ↓
[DesiredMarginCalculator Component]
    ↓
Clicks "Proceed to Projection"
    ↓
desiredMarginAPI.calculateDesiredMargin(
  transactions: [...],
  mcc: "5812",
  desiredMargin: 0.015
)
    ↓
POST /api/v1/calculations/desired-margin
    ↓
[Flask Backend - routes.py]
@calculations_bp.route('/desired-margin', methods=['POST'])
    ↓
MerchantFeeCalculationService.calculate_desired_margin()
    ↓
Calculation logic:
- total_volume = sum of all amounts
- required_rate = desired_margin
- estimated_fees = (volume × rate) + (count × fixed_fee)
- estimated_effective_rate = estimated_fees / volume
    ↓
Stores result to CalculationResult model
    ↓
Returns JSON response:
{
  "transaction_count": 150,
  "total_volume": 25000.00,
  "desired_margin": 0.015,
  "recommended_rate": 0.015,
  "estimated_total_fees": 420.00,
  "estimated_effective_rate": 0.0168,
  "mcc": "5812"
}
    ↓
Frontend displays results in DesiredMarginResults
```

---

## 4. MCC Code Dropdown Flow

### Current (Hardcoded):
```
[MCCDropdown Component]
    ↓
Uses static MCC_CODES array
```

### Recommended (Dynamic):
```
Component mounts
    ↓
useEffect hook runs
    ↓
merchantFeeAPI.getMCCList()
    ↓
GET /api/v1/mcc-codes
    ↓
[Flask Backend - routes.py]
@mccs_bp.route('', methods=['GET'])
    ↓
MCCService.get_all_mccs()
    ↓
Returns JSON response:
[
  {
    "code": "5812",
    "description": "Eating Places and Restaurants"
  },
  {
    "code": "5411",
    "description": "Grocery Stores"
  },
  ...
]
    ↓
Frontend populates dropdown
```

---

## 5. Manual Transaction Entry Flow

```
User manually enters transaction rows
    ↓
[ManualTransactionEntry Component]
    ↓
Local validation (date format, amount > 0)
    ↓
Clicks "Validate and Preview"
    ↓
Shows first 10 rows in preview table
    ↓
Highlights rows with errors (red background)
    ↓
Clicks "Proceed to Calculation"
    ↓
Passes validated data to calculator component
    ↓
Same fee calculation flow as CSV upload
```

---

## 6. Error Handling Flow

```
Frontend API Call
    ↓
[api.js Axios Instance]
    ↓
Response Interceptor catches error
    ↓
Error logged to console:
console.error('API Error:', error.response.data)
    ↓
Component try-catch block:
  catch (error) {
    // Use fallback mock data
    // OR show error banner to user
  }
    ↓
Frontend displays:
- Error message banner
- Row-level error highlighting
- Specific error details (row, column, reason)
```

---

## 7. Data Validation Pipeline

### Frontend Validation (Client-Side)
```
File/Data Upload
    ↓
[DataUploadValidator.jsx] or [ManualTransactionEntry.jsx]
    ↓
Check file type (.csv, .xlsx, .xls)
Check required columns present
Check date format (DD/MM/YYYY)
Check amount is positive number
Check required fields not empty
    ↓
If valid → Send to backend
If invalid → Show error to user (don't send)
```

### Backend Validation (Server-Side)
```
Receive data from frontend
    ↓
[validators.py - TransactionValidator]
    ↓
Validate headers again
    ↓
For each row:
- Validate transaction_id (required, unique)
- Validate transaction_date (valid date format)
- Validate amount (positive decimal)
- Validate transaction_type (Sale/Refund/Void)
- Validate card_type (Visa/Mastercard/Amex/Discover)
- Validate merchant_id (required)
    ↓
Return validation results with:
- Row number
- Column name
- Error type (MISSING_VALUE, INVALID_TYPE, etc.)
- Error message
    ↓
Store valid rows to database
Return error list to frontend
```

---

## 8. Database Storage Flow

### Transaction Upload
```
Valid transaction data
    ↓
[Transaction Model - models.py]
    ↓
SQLAlchemy creates Transaction objects
    ↓
Transaction(
  transaction_id="TXN001",
  transaction_date=Date(2024-01-15),
  merchant_id="MER001",
  amount=Decimal(150.50),
  transaction_type="Sale",
  card_type="Visa",
  batch_id="batch_..."
)
    ↓
db.session.add(transaction)
db.session.commit()
    ↓
Data stored in SQLite/PostgreSQL
    ↓
Can be retrieved later via:
Transaction.query.all()
Transaction.query.filter_by(merchant_id="MER001")
```

### Calculation Result Storage
```
Calculation completed
    ↓
[CalculationResult Model - models.py]
    ↓
CalculationResult(
  calculation_type="MERCHANT_FEE",
  mcc="5812",
  transaction_count=150,
  total_volume=Decimal(25000.00),
  total_fees=Decimal(751.50),
  effective_rate=Decimal(0.03006),
  ...
)
    ↓
db.session.add(calculation_result)
db.session.commit()
    ↓
Audit trail created (timestamp automatically set)
Can be retrieved for history/reporting
```

---

## 9. Environment-Based API URLs

### Development Environment
```
.env file contains:
REACT_APP_API_URL=http://localhost:5000/api/v1

Frontend loads:
const API_BASE_URL = 'http://localhost:5000/api/v1'

All requests:
POST http://localhost:5000/api/v1/transactions/upload
GET http://localhost:5000/api/v1/mcc-codes
```

### Production Environment
```
.env file contains:
REACT_APP_API_URL=https://api.404found.com/api/v1

Frontend loads:
const API_BASE_URL = 'https://api.404found.com/api/v1'

All requests:
POST https://api.404found.com/api/v1/transactions/upload
GET https://api.404found.com/api/v1/mcc-codes
```

---

## 10. API Response Structure

### Success Response Format
```javascript
{
  "success": true,
  "message": "Operation message",
  "data": {
    // Response data here
  }
}
```

### Error Response Format
```javascript
{
  "success": false,
  "error": "Error message",
  "error_type": "ERROR_CODE",
  "details": {
    // Error context here
  }
}
```

### Paginated Response Format
```javascript
{
  "success": true,
  "message": "Data retrieved",
  "data": [
    // Array of items
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

## 11. Component State Management Flow

### EnhancedMerchantFeeCalculator State
```
useState Hook → State Variable → Causes Re-render → Update UI

isLoading (true/false)
  ↓ Shows loading spinner while API call in progress
  
results (null | object)
  ↓ Populated when API returns, triggers ResultsPanel display
  
transactionData (array)
  ↓ Stores validated transactions from upload
  
dataValidated (true/false)
  ↓ Tracks if user confirmed data preview
```

### Error Handling State
```
validationErrors (array of objects)
  ↓ Each error has: row, column, message, error_type
  
fileError (string)
  ↓ General file upload errors
  
globalErrorBanner
  ↓ Displays error message to user
```

---

## 12. Real API Call Examples

### Upload Transaction File
```javascript
// Frontend
const response = await merchantFeeAPI.uploadTransactionData(
  csvFile,
  'MER001'
);

// HTTP Request
POST http://localhost:5000/api/v1/transactions/upload
Content-Type: multipart/form-data

file: [binary file data]
merchant_id: MER001

// Backend Response
{
  "success": true,
  "data": {
    "batch_id": "batch_abc123_20240115120000",
    "filename": "transactions.csv",
    "total_records": 150,
    "stored_records": 148,
    "error_count": 2,
    "errors": [
      {
        "row": 5,
        "column": "amount",
        "error": "Amount must be positive",
        "error_type": "INVALID_TYPE"
      }
    ],
    "preview": [...]
  }
}

// Frontend handles response
setPreviewData(response.data.preview);
setValidationErrors(response.data.errors);
```

### Calculate Merchant Fee
```javascript
// Frontend
const response = await merchantFeeAPI.calculateCurrentRates(
  transactionData,
  "5812",
  0.029,
  0.30
);

// HTTP Request
POST http://localhost:5000/api/v1/calculations/merchant-fee
Content-Type: application/json

{
  "transactions": [
    {
      "transaction_id": "TXN001",
      "transaction_date": "15/01/2024",
      "amount": 150.50,
      ...
    }
  ],
  "mcc": "5812",
  "current_rate": 0.029,
  "fixed_fee": 0.30
}

// Backend Response
{
  "success": true,
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

// Frontend displays results
setResults(response.data);
```

### Get MCC Codes
```javascript
// Frontend
const response = await merchantFeeAPI.getMCCList();

// HTTP Request
GET http://localhost:5000/api/v1/mcc-codes

// Backend Response
{
  "success": true,
  "data": [
    {
      "code": "5812",
      "description": "Eating Places and Restaurants"
    },
    {
      "code": "5411",
      "description": "Grocery Stores"
    },
    ... (18 more)
  ]
}

// Frontend populates dropdown
setMccList(response.data);
```

---

## 13. Running the Full Stack

### Terminal 1: Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py

✅ Backend running on http://localhost:5000
```

### Terminal 2: Frontend
```bash
cd frontend
npm install
npm start

✅ Frontend running on http://localhost:3000
```

### Result
```
Frontend at http://localhost:3000
  ↓ (API calls)
Backend at http://localhost:5000
```

---

## 14. Debugging API Issues

### Browser DevTools Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Perform action (upload file, calculate fee, etc.)
4. Look for API requests:
   - POST /api/v1/transactions/upload
   - POST /api/v1/calculations/merchant-fee
   - GET /api/v1/mcc-codes
5. Click request to see:
   - Request headers
   - Request body
   - Response body
   - Response status (200, 400, 500, etc.)

### Common Status Codes
```
200 - Success
201 - Created successfully
400 - Bad request (validation error)
404 - Endpoint not found
500 - Server error
503 - Service unavailable
```

### Console Errors
```javascript
// Check frontend console for:
console.error('API Error:', error.response.data)
console.error('Error uploading transaction data:', error)
console.error('Error calculating desired margin:', error)
```

### Backend Logs
```
Flask prints to console:
- Request received logs
- Error messages with tracebacks
- Database query logs (if enabled)
```

---

## 15. Summary

Your application has a **complete, functional API integration**:

✅ Frontend sends data to backend via HTTP
✅ Backend validates, processes, stores data
✅ Backend sends results back to frontend
✅ Frontend displays results to user
✅ Error handling at all levels
✅ Database persistence
✅ Environment-based configuration

**Everything is connected and ready to use!** 🚀
