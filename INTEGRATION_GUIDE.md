# Frontend-Backend Integration Guide

## Quick Start

### Prerequisites
- Backend running on `http://localhost:5000`
- Frontend running on `http://localhost:3000`
- Both share the same Git repository

## Running Both Servers

### Terminal 1 - Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
python app.py
```

Backend available at: `http://localhost:5000`

### Terminal 2 - Frontend
```bash
cd frontend
npm install
npm start
```

Frontend available at: `http://localhost:3000`

## API Integration Checklist

### ✅ Configuration
- [x] Backend running on port 5000
- [x] Frontend running on port 3000
- [x] CORS enabled for localhost:3000
- [x] API base URL: `http://localhost:5000/api/v1`

### ✅ API Endpoints Ready
- [x] `POST /transactions/upload` - Upload CSV/Excel files
- [x] `GET /transactions` - List transactions
- [x] `POST /calculations/merchant-fee` - Calculate fees
- [x] `POST /calculations/desired-margin` - Calculate margin
- [x] `GET /mcc-codes` - Get MCC list
- [x] `POST /merchants` - Create/update merchant

### ✅ Frontend Components Connected
- [x] `DataUploadValidator.jsx` → POST /transactions/upload
- [x] `ManualTransactionEntry.jsx` → POST /calculations/* endpoints
- [x] `MCCDropdown.jsx` → GET /mcc-codes
- [x] `services/api.js` → Updated with correct endpoints

## Testing the Integration

### 1. Test Upload Endpoint

**Frontend Action:**
1. Open Merchant Profitability Calculator
2. Click "Upload Files"
3. Select a CSV file with transaction data

**Expected Flow:**
1. File sent to `POST /transactions/upload`
2. Backend validates file and returns preview
3. Frontend shows first 10 rows
4. No errors displayed (or specific errors highlighted)

### 2. Test MCC Dropdown

**Frontend Action:**
1. Scroll to "Merchant Category Code" field
2. Click dropdown or type to search

**Expected Flow:**
1. Fetches from `GET /mcc-codes`
2. Search works via `GET /mcc-codes/search?q=<query>`
3. Dropdown displays all available codes

### 3. Test Fee Calculation

**Frontend Action:**
1. Upload transaction data
2. Select MCC code
3. Click "Proceed to Projection"

**Expected Flow:**
1. Sends data to `POST /calculations/merchant-fee`
2. Backend calculates fees
3. Results displayed in calculator

### 4. Test Desired Margin Calculator

**Frontend Action:**
1. Navigate to "Rates Quotation Tool"
2. Enter merchant data
3. Click "Proceed to Projection"

**Expected Flow:**
1. Sends data to `POST /calculations/desired-margin`
2. Backend calculates recommended rate
3. Results displayed

## Debugging Guide

### Issue: CORS Error
**Error Message:** "Access to XMLHttpRequest blocked by CORS policy"

**Solution:**
1. Check backend `.env` has correct CORS_ORIGINS:
   ```
   CORS_ORIGINS=http://localhost:3000,http://localhost:5000
   ```
2. Restart backend server
3. Clear browser cache

### Issue: 404 Error on File Upload
**Error Message:** "POST http://localhost:5000/api/v1/transactions/upload 404 (Not Found)"

**Solution:**
1. Verify backend is running: `curl http://localhost:5000/health`
2. Check blueprints registered in app.py
3. Verify routes.py file exists
4. Restart backend

### Issue: Validation Errors
**Error Message:** "Row 5, Column transaction_date: Invalid date format"

**Solution:**
1. Check CSV has correct date format: DD/MM/YYYY
2. Ensure all required columns present: transaction_id, transaction_date, merchant_id, amount, transaction_type, card_type
3. Verify data types (amount must be numeric)

### Issue: Database Error
**Error Message:** "Database error: ..."

**Solution:**
1. Delete `app.db` if using SQLite
2. Restart backend (will recreate database)
3. Verify DATABASE_URL in .env

### Issue: "Cannot find module" Error
**Error Message:** "ModuleNotFoundError: No module named 'models'"

**Solution:**
1. Ensure all backend Python files are in same directory
2. Activate virtual environment
3. Reinstall requirements: `pip install -r requirements.txt`

## API Response Examples

### Successful Upload
```javascript
{
  "success": true,
  "message": "File uploaded successfully",
  "data": {
    "batch_id": "batch_abc123_20240115120000",
    "stored_records": 150,
    "error_count": 0,
    "preview": [...]
  }
}
```

### Successful Fee Calculation
```javascript
{
  "success": true,
  "message": "Merchant fee calculation completed",
  "data": {
    "total_volume": 25000.00,
    "total_fees": 751.50,
    "effective_rate": 0.03006,
    "average_ticket": 166.67
  }
}
```

### Validation Error
```javascript
{
  "success": false,
  "error": "Validation failed",
  "error_type": "VALIDATION_ERROR",
  "details": {
    "row": 5,
    "column": "amount",
    "message": "Amount must be positive"
  }
}
```

## File Upload Process Flow

```
User selects file
    ↓
Frontend validates file type (.csv, .xlsx, .xls)
    ↓
Frontend sends to POST /transactions/upload
    ↓
Backend parses file
    ↓
Backend validates headers (required columns present)
    ↓
Backend validates each row
    ↓
Backend stores valid transactions in DB
    ↓
Backend returns response with:
  - batch_id (for reference)
  - preview (first 10 rows)
  - error_count (validation failures)
  - specific errors (which rows failed)
    ↓
Frontend displays:
  - Success/error banner
  - Preview table
  - Row-level error highlighting
  - Overall results summary
```

## Data Flow Example

### Upload and Calculate Example

1. **User uploads CSV file with 150 transactions**
   ```
   Transaction ID, Date, Merchant ID, Amount, Type, Card
   TXN001, 15/01/2024, MER001, 150.50, Sale, Visa
   TXN002, 16/01/2024, MER001, 200.00, Sale, Mastercard
   ...
   ```

2. **Frontend sends to backend:**
   ```javascript
   POST /api/v1/transactions/upload
   - file: transactions.csv
   - merchant_id: MER001
   ```

3. **Backend processes:**
   - Parses CSV file
   - Validates each row
   - Stores in database
   - Returns batch_id and preview

4. **Frontend receives and displays:**
   ```
   Uploaded: 150 transactions
   Errors: 0
   [Preview table showing first 10 rows]
   ```

5. **User selects MCC (5812 - Restaurants) and clicks Proceed**

6. **Frontend sends to backend:**
   ```javascript
   POST /api/v1/calculations/merchant-fee
   {
     transactions: [150 transaction objects],
     mcc: "5812",
     current_rate: 0.029,
     fixed_fee: 0.30
   }
   ```

7. **Backend calculates:**
   - Sum transaction volumes: $25,000
   - Calculate fees: ($25,000 × 0.029) + ($0.30 × 150) = $770
   - Effective rate: $770 / $25,000 = 3.08%
   - Average ticket: $25,000 / 150 = $166.67

8. **Backend returns results**

9. **Frontend displays in Merchant Profitability Calculator**

## Environment Setup

### Backend .env
```
FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=dev_secret_key
DATABASE_URL=sqlite:///app.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5000
MAX_UPLOAD_SIZE=5242880
```

### Frontend .env
```
REACT_APP_API_URL=http://localhost:5000/api/v1
```

## Common Operations

### Upload Transaction Data
```javascript
// Frontend code
import { merchantFeeAPI } from './services/api';

const file = document.querySelector('input[type="file"]').files[0];
const result = await merchantFeeAPI.uploadTransactionData(file, 'MER001');
```

### Get MCC Codes
```javascript
import { merchantFeeAPI } from './services/api';

const mccs = await merchantFeeAPI.getMCCList();
// Returns: [{code: '5812', description: 'Restaurants'}, ...]
```

### Calculate Merchant Fee
```javascript
import { merchantFeeAPI } from './services/api';

const result = await merchantFeeAPI.calculateCurrentRates(
  transactions,  // array of transaction objects
  '5812',        // MCC code
  0.029,         // current rate
  0.30           // fixed fee
);
// Returns: {total_volume, total_fees, effective_rate, ...}
```

### Calculate Desired Margin
```javascript
import { desiredMarginAPI } from './services/api';

const result = await desiredMarginAPI.calculateDesiredMargin(
  transactions,  // array of transaction objects
  '5812',        // MCC code
  0.015          // desired margin
);
// Returns: {recommended_rate, estimated_total_fees, ...}
```

## Validation Rules Reference

### Transaction CSV Format
```
Required Columns:
- transaction_id (unique string)
- transaction_date (DD/MM/YYYY format)
- merchant_id (string)
- amount (positive decimal)
- transaction_type (Sale, Refund, or Void)
- card_type (Visa, Mastercard, Amex, or Discover)
```

### MCC Codes
```
Valid codes include:
5812 - Eating Places and Restaurants
5411 - Grocery Stores
5541 - Service Stations
7011 - Hotels and Motels
... (20+ total codes available)
```

## Performance Considerations

- **File Upload Limit**: 5MB per file
- **Pagination**: Default 20 items/page, max 100
- **Response Time**: Most calculations < 500ms
- **Database**: SQLite for dev, PostgreSQL recommended for prod

## Next Steps

1. **Test all endpoints** using the checklist above
2. **Monitor browser console** for API errors
3. **Check backend logs** for processing details
4. **Run in production** when testing complete
5. **Add authentication** for user management
6. **Set up monitoring** for performance tracking

## Useful Commands

```bash
# Test backend health
curl http://localhost:5000/health

# Get all MCCs
curl http://localhost:5000/api/v1/mcc-codes

# Search for restaurants
curl "http://localhost:5000/api/v1/mcc-codes/search?q=restaurant"

# List transactions (page 1)
curl "http://localhost:5000/api/v1/transactions?page=1&per_page=20"
```

## Documentation References

- Backend setup: `backend/BACKEND_SETUP.md`
- API endpoints: `backend/API_DOCUMENTATION.md`
- Frontend components: Individual component files with comments
- User stories: Project documentation

## Support

For issues:
1. Check API_DOCUMENTATION.md for endpoint details
2. Verify both servers are running
3. Check browser Developer Tools (Network tab)
4. Check backend console for error messages
5. Verify file format and data validation rules
