# Backend Setup Guide

## Project Structure

```
backend/
├── app.py                    # Flask application factory
├── config.py               # Configuration management (dev/prod/test)
├── models.py               # SQLAlchemy ORM models
├── validators.py           # Data validation logic
├── services.py             # Business logic services
├── routes.py               # API endpoints and blueprints
├── errors.py               # Error handling utilities
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── Dockerfile              # Docker containerization
└── API_DOCUMENTATION.md    # Comprehensive API docs
```

## Dependencies

### Core Framework
- **Flask 3.0+**: Lightweight Python web framework
- **Flask-CORS 4.0+**: Cross-Origin Resource Sharing support
- **Flask-SQLAlchemy 3.1+**: ORM for database operations
- **Werkzeug 3.0+**: WSGI utilities for Flask

### Data Processing
- **python-dotenv 1.0+**: Environment variable management
- **openpyxl 3.1+**: Excel file parsing (.xlsx, .xls)
- **pandas 2.1+**: Data manipulation
- **numpy 1.26+**: Numerical operations

### ML/Analytics (existing)
- **scikit-learn 1.4+**
- **seaborn 0.13+**
- **wandb 0.16+**

## Installation

### 1. Install Python Dependencies

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file in backend directory:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```
FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=your_super_secret_key_here
DATABASE_URL=sqlite:///app.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5000
MAX_UPLOAD_SIZE=5242880
```

### 3. Initialize Database

```bash
python
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
>>>     db.create_all()
>>> exit()
```

Or automatically on first run - `app.py` calls `db.create_all()` on startup.

## Running the Application

### Development Mode

```bash
python app.py
```

Server starts on `http://localhost:5000`

- Auto-reloads on code changes
- Debug mode enabled
- Full error messages

### Production Mode

```bash
# Set environment
export FLASK_ENV=production  # On macOS/Linux
set FLASK_ENV=production     # On Windows

# Run with production WSGI server
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:create_app()
```

## Module Overview

### app.py
**Application Factory Pattern**

- `create_app(config_name)`: Creates and configures Flask application
  - Loads environment-specific config
  - Initializes database and extensions
  - Registers API blueprints
  - Sets up error handlers
  - Creates database tables

### config.py
**Configuration Management**

- `Config`: Base configuration class
  - Database URL
  - Upload settings (5MB max)
  - CORS origins
  - API configuration
  
- `DevelopmentConfig`: Debug enabled, SQLite database
- `ProductionConfig`: Debug disabled, production settings
- `TestingConfig`: Testing environment setup
- `config_by_name`: Dictionary mapping config names to classes

### models.py
**Database Models (SQLAlchemy ORM)**

- `Transaction`: Stores transaction data
  - transaction_id, transaction_date, merchant_id
  - amount, transaction_type, card_type
  - Indexes on transaction_id, merchant_id
  
- `Merchant`: Merchant profiles
  - merchant_id, merchant_name, mcc
  - annual_volume, average_ticket
  - current_rate, fixed_fee
  
- `CalculationResult`: Audit trail for calculations
  - Stores merchant fee and desired margin results
  - Timestamped for history
  
- `UploadBatch`: Tracks file uploads
  - batch_id, filename, file_type
  - record_count, error_count, status

### validators.py
**Data Validation Logic**

- `ValidationError`: Custom exception with context
  - row, column, error_type, message
  
- `TransactionValidator`: Validates transaction data
  - Static methods for each field
  - Support for multiple date formats
  - Card type and transaction type validation
  - `validate_headers()`: Check required columns
  - `validate_row()`: Validate single transaction
  
- `MerchantValidator`: Validates merchant data
  - MCC code validation
  - Merchant profile structure validation

### services.py
**Business Logic Services**

- `DataProcessingService`: File upload handling
  - `parse_csv_file()`: Parse CSV with validation
  - `parse_excel_file()`: Parse Excel with validation
  
- `MerchantFeeCalculationService`: Fee calculations
  - `calculate_current_rates()`: Calculate fees based on rates
  - `calculate_desired_margin()`: Calculate rate for margin
  - MCC-based rate lookups
  
- `MCCService`: Merchant Category Code operations
  - `get_all_mccs()`: Get full MCC list
  - `search_mccs()`: Search by code/description
  - `get_mcc_by_code()`: Lookup single code

### routes.py
**API Endpoints (Flask Blueprints)**

**Transaction Routes** (`/api/v1/transactions`)
- POST `/upload`: Upload CSV/Excel files
- GET `/`: List transactions (paginated)
- GET `/<id>`: Get single transaction

**Calculation Routes** (`/api/v1/calculations`)
- POST `/merchant-fee`: Calculate current rates
- POST `/desired-margin`: Calculate desired margin

**Merchant Routes** (`/api/v1/merchants`)
- GET `/`: List merchants (paginated)
- GET `/<id>`: Get merchant profile
- POST `/`: Create/update merchant

**MCC Routes** (`/api/v1/mcc-codes`)
- GET `/`: Get all MCC codes
- GET `/search`: Search MCCs
- GET `/<code>`: Get single MCC

**Error Handlers**
- Standardized error responses
- HTTP status codes
- Validation error details

### errors.py
**Error Handling Utilities**

- `APIError`: Base error class
- `ValidationAPIError`: Validation errors
- `NotFoundError`: 404 errors
- `InternalServerError`: 500 errors
- `error_response()`: Format errors for API
- `success_response()`: Format successes
- `paginated_response()`: Format paginated data

## API Integration

### Frontend Configuration

Update `frontend/src/services/api.js`:

```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api/v1';
```

Set `.env` in frontend:
```
REACT_APP_API_URL=http://localhost:5000/api/v1
```

### API Endpoints Match Frontend Calls

Frontend API calls → Backend routes:

```
merchantFeeAPI.uploadTransactionData() → POST /transactions/upload
merchantFeeAPI.calculateCurrentRates() → POST /calculations/merchant-fee
desiredMarginAPI.calculateDesiredMargin() → POST /calculations/desired-margin
merchantFeeAPI.getMCCList() → GET /mcc-codes
```

## Database Schema

### Transactions Table
```sql
CREATE TABLE transactions (
  id INTEGER PRIMARY KEY,
  transaction_id VARCHAR(100) UNIQUE NOT NULL,
  transaction_date DATE NOT NULL,
  merchant_id VARCHAR(100) NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  transaction_type VARCHAR(20) NOT NULL,
  card_type VARCHAR(20) NOT NULL,
  batch_id VARCHAR(100),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Merchants Table
```sql
CREATE TABLE merchants (
  id INTEGER PRIMARY KEY,
  merchant_id VARCHAR(100) UNIQUE NOT NULL,
  merchant_name VARCHAR(255) NOT NULL,
  mcc VARCHAR(4) NOT NULL,
  industry VARCHAR(100),
  annual_volume NUMERIC(15,2),
  average_ticket NUMERIC(10,2),
  current_rate NUMERIC(5,4),
  fixed_fee NUMERIC(6,2) DEFAULT 0.30,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Testing

### Manual API Testing

Use curl, Postman, or frontend to test:

```bash
# Check health
curl http://localhost:5000/health

# Get MCC list
curl http://localhost:5000/api/v1/mcc-codes

# Search MCCs
curl "http://localhost:5000/api/v1/mcc-codes/search?q=restaurant"
```

### Testing File Upload

```python
import requests

with open('transactions.csv', 'rb') as f:
    files = {'file': f}
    response = requests.post(
        'http://localhost:5000/api/v1/transactions/upload',
        files=files
    )
    print(response.json())
```

## Deployment

### Docker Deployment

```bash
# Build image
docker build -t 404-found-backend .

# Run container
docker run -p 5000:5000 -e FLASK_ENV=production 404-found-backend
```

### Docker Compose

```bash
# From project root
docker-compose up -d
```

### Environment Variables for Production

```
FLASK_ENV=production
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://user:password@localhost/404_found
CORS_ORIGINS=https://yourdomain.com
```

## Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :5000
kill -9 <PID>
```

### Database Locked
```bash
# Remove SQLite database and recreate
rm app.db
python app.py
```

### CORS Errors
- Check `CORS_ORIGINS` in `.env`
- Verify frontend URL is in list
- Restart Flask server

### Import Errors
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check Python version (3.8+)

## Performance Tips

1. **Database Indexing**: Indexes on transaction_id, merchant_id
2. **Pagination**: Default 20 items, max 100 per page
3. **File Upload Limits**: Max 5MB per file
4. **Connection Pooling**: SQLAlchemy handles automatically
5. **Caching**: Consider Redis for MCC lookups

## Security Considerations

1. **Environment Variables**: Keep `.env` in `.gitignore`
2. **CORS**: Whitelist specific domains only
3. **Input Validation**: All data validated before processing
4. **SQL Injection**: SQLAlchemy ORM prevents injection
5. **Future Enhancements**:
   - Add authentication (JWT)
   - Rate limiting
   - HTTPS/SSL
   - Request signing

## Monitoring & Logging

### Current Logging
- Console output during development
- Error traceback in debug mode

### Future Enhancements
- Structured logging (JSON format)
- Application Performance Monitoring (APM)
- Error tracking (Sentry)
- Metrics collection (Prometheus)
- Log aggregation (ELK Stack)

## Contact & Support

For issues or questions about the backend:
1. Check API documentation
2. Review error messages (clear context in responses)
3. Check configuration in `.env`
4. Verify database connection
5. Run tests for validation

## Next Steps

1. ✅ Core infrastructure complete
2. ⏭️ Add authentication layer
3. ⏭️ Implement rate limiting
4. ⏭️ Add comprehensive logging
5. ⏭️ Create unit tests
6. ⏭️ Add Swagger documentation
7. ⏭️ Performance optimization
8. ⏭️ Production deployment
