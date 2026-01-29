# Data Validation & Upload Features

## Overview
This document outlines all the data validation and upload features implemented for the Rates Quotation Tool based on the user story: "As a Sales Team Member, I want to upload it via CSV, so that I can validate the data completeness/accuracy before running a projection."

## ✅ Implemented Features

### 1. CSV File Upload with Drag & Drop
- **Location**: `DataUploadValidator` component
- **Features**:
  - Drag and drop area with visual feedback
  - "Choose File" button for traditional file selection
  - Visual state changes on drag enter/leave
  - Accepts only CSV files

### 2. File Type Restrictions
- **CSV Only**: System now explicitly accepts only CSV files
- **Error Message**: Clear message displayed when wrong file type is uploaded
- **Required Columns**: 
  - `transaction_id`
  - `transaction_date`
  - `merchant_id`
  - `amount`
  - `transaction_type`
  - `card_type`

### 3. Data Preview Table
- **Shows First 10 Rows**: After successful validation, displays a preview table
- **Table Columns**: Displays all required columns in a formatted table
- **Formatted Data**: Amounts are displayed with currency formatting

### 4. Comprehensive Validation
- **Header Validation**: Checks for all required column headers
- **Missing Values**: Detects empty required fields
- **Date Format Validation**: Accepts DD/MM/YYYY, YYYY-MM-DD, MM/DD/YYYY
- **Numeric Validation**: Ensures amount field contains valid numbers
- **Row-Level Errors**: Identifies specific row and column for each error

### 5. Error Handling & Display
- **Global Error Banner**: Shows total count of validation errors
- **Detailed Error List**: Lists each error with:
  - Row number
  - Column name
  - Error description
  - Error type (MISSING_VALUE, INVALID_TYPE, INVALID_FORMAT, INVALID_DATE)
- **Row Highlighting**: Errors are shown with red background in manual entry
- **Re-upload Button**: Displayed on error, allows user to upload a new file

### 6. Manual Transaction Entry
- **Location**: `ManualTransactionEntry` component
- **Features**:
  - Grid/table interface for manual data entry
  - All required columns as input fields
  - Add Row button
  - Delete Row button (disabled when only 1 row)
  - Duplicate Row button
  - Clear All button (with confirmation dialog)
  - Real-time validation
  - Field-level error messages
  - Row highlighting for errors

### 7. MCC Dropdown with Search
- **Location**: `MCCDropdown` component
- **Features**:
  - Searchable dropdown with 100+ MCC codes
  - Displays both code and description
  - Type-ahead filtering
  - Professional UI with Combobox pattern
  - Auto-population from uploaded data

### 8. Two-Step Validation Process
1. **Step 1: Data Input**
   - Choose between Upload CSV or Manual Entry (tabs)
   - Validate & Preview button (disabled until data is present)
   - Loading spinner during validation
   - Preview of validated data

2. **Step 2: Fee Configuration**
   - Only shown after data is validated
   - Shows count of validated transactions
   - "Edit Data" button to go back to Step 1
   - MCC selection with searchable dropdown
   - Fee structure configuration

### 9. Loading States
- **Validation Spinner**: Animated spinner shown during file validation
- **Visual Feedback**: Progress indication with "Validating file..." message

### 10. Success Indicators
- **Green Success Box**: Shows validation success with checkmark icon
- **Transaction Count**: Displays total validated transactions
- **Extracted MCC**: Shows MCC code if detected from data
- **Proceed Button**: Enabled only after successful validation

## File Structure

### New Components Created
1. `/components/DataUploadValidator.tsx` - CSV upload and validation
2. `/components/ManualTransactionEntry.tsx` - Manual entry table
3. `/components/MCCDropdown.tsx` - Searchable MCC selector
4. `/components/EnhancedMerchantFeeCalculator.tsx` - Main calculator with new features

### Sample Files
1. `/sample-transactions-correct-format.csv` - Valid CSV example
2. `/sample-transactions-with-errors.csv` - Invalid CSV for testing

## Usage Examples

### Valid CSV Format
```csv
transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type
TXN001,17/01/2026,M12345,500.00,Sale,Visa
TXN002,18/01/2026,M12345,250.50,Sale,Mastercard
```

### Error Messages Examples
- **Missing Header**: "Missing required columns: transaction_id, amount"
- **Invalid Date**: "Row 2, Column 'transaction_date': Invalid date format. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY (INVALID_DATE)"
- **Missing Value**: "Row 4, Column 'merchant_id': Required field cannot be empty (MISSING_VALUE)"
- **Invalid Type**: "Row 3, Column 'amount': Amount must be a valid number (INVALID_TYPE)"

## User Flow

### Upload Flow
1. User lands on calculator page
2. Sees two tabs: "Upload CSV" and "Manual Entry"
3. Selects "Upload CSV" tab
4. Drags and drops CSV file OR clicks "Choose File"
5. System validates file (shows loading spinner)
6. **If errors**: Shows detailed error list with "Re-upload File" button
7. **If valid**: Shows success message + preview table (first 10 rows) + "Proceed to Projection" button
8. User clicks "Proceed to Projection"
9. Step 2 appears with fee configuration form
10. User fills form and submits for calculation

### Manual Entry Flow
1. User lands on calculator page
2. Selects "Manual Entry" tab
3. Enters transactions in table grid
4. Uses Add/Delete/Duplicate buttons as needed
5. Clicks "Validate & Proceed to Projection"
6. **If errors**: Rows highlighted in red with specific field errors
7. **If valid**: Proceeds to Step 2
8. User fills form and submits for calculation

## Validation Rules

### Date Formats Accepted
- DD/MM/YYYY (e.g., 17/01/2026)
- YYYY-MM-DD (e.g., 2026-01-17)
- MM/DD/YYYY (e.g., 01/17/2026)

### Amount Validation
- Must be numeric
- Can include decimals
- No currency symbols in CSV

### Required Fields
All fields are required and cannot be empty:
- transaction_id
- transaction_date
- merchant_id
- amount
- transaction_type
- card_type

## Accessibility Features
- Keyboard navigation support
- ARIA labels for screen readers
- Focus management
- Error announcements
- Clear visual indicators

## Future Enhancements (Not Yet Implemented)
- Excel file support in upload validator
- Bulk edit capabilities
- CSV template download
- More sophisticated MCC extraction from transaction data
- Transaction data statistics dashboard
- Export validated data
