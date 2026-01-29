# Quick Reference Guide

## Frontend Project Structure

```
404_found_us/
├── frontend/
│   ├── src/
│   │   ├── App.js                       # Root app with routing
│   │   ├── App.css                      # Global styles
│   │   ├── components/
│   │   │   ├── LandingPage.jsx
│   │   │   ├── EnhancedMerchantFeeCalculator.jsx
│   │   │   ├── DesiredMarginCalculator.jsx
│   │   │   ├── DataUploadValidator.jsx  # ⭐ Upload + Preview + Validation
│   │   │   ├── ManualTransactionEntry.jsx # ⭐ Form entry + Table actions
│   │   │   ├── MCCDropdown.jsx
│   │   │   ├── ResultsPanel.jsx
│   │   │   ├── DesiredMarginResults.jsx
│   │   │   └── ui/
│   │   │       ├── Button.jsx
│   │   │       ├── Input.jsx
│   │   │       ├── Card.jsx
│   │   │       ├── Label.jsx
│   │   │       └── Tabs.jsx
│   │   └── services/
│   │       └── api.js                  # API integration
│   ├── package.json
│   ├── tailwind.config.js
│   └── postcss.config.js
├── IMPLEMENTATION_SUMMARY.md            # Full documentation
├── SESSION_SUMMARY.md                   # Today's changes
└── Laptop Order Form/                   # Original Figma exports
```

---

## Key Components & Their Responsibilities

### DataUploadValidator.jsx
**Purpose:** Handle CSV/Excel file uploads with validation and preview

**Workflow:**
1. User uploads file (.csv, .xlsx, .xls)
2. System validates file type
3. Shows preview of first 10 rows
4. User confirms preview
5. Full dataset validation
6. Results or error display

**Key Functions:**
- `handleFile()` - File parsing (CSV and Excel)
- `validateCSVStructure()` - Data validation
- `handleProceed()` - Finalize validation
- `handleReupload()` - Error recovery

**State Variables:**
- `showPreview` - Toggle preview/upload UI
- `previewData` - First 10 rows
- `fullData` - All rows
- `validationErrors` - Error list

---

### ManualTransactionEntry.jsx
**Purpose:** Form-based data entry with table interface

**Workflow:**
1. User enters data in table rows
2. System validates in real-time (visual only)
3. User clicks "Validate & Preview"
4. Full validation with error display
5. If valid: Shows preview table
6. User clicks "Proceed to Projection"

**Key Functions:**
- `addTransaction()` - Add new row
- `removeTransaction()` - Delete row
- `duplicateTransaction()` - Copy row
- `clearAllEntries()` - Reset table
- `handleValidateAndPreview()` - Validate all

**Table Actions:**
- ➕ Add Row button
- 🗑️ Delete Row button (per-row)
- 📋 Duplicate Row button (per-row)
- 🧹 Clear All button

---

### MCCDropdown.jsx
**Purpose:** Search and select Merchant Category Codes

**Features:**
- Dropdown with 20+ preset codes
- Real-time search filtering
- Format: "Code - Description"
- Click-outside handling

**Integration:**
- Used in both calculators
- Auto-populate if MCC detected from upload

---

### EnhancedMerchantFeeCalculator.jsx
**Purpose:** Calculate profitability with current merchant rates

**Tabs:**
1. **Upload Tab** - Uses DataUploadValidator
2. **Manual Entry Tab** - Uses ManualTransactionEntry

**Form Fields:**
- MCC (via dropdown)
- Fee Structure
- Current Rate
- Fixed Fee
- Minimum Fee

**Button:** "Proceed to Projection"

---

### DesiredMarginCalculator.jsx
**Purpose:** Calculate rates needed for desired profit margin

**Similar Structure:**
- Same upload/manual entry tabs
- Different calculation logic
- Dedicated results display

---

## Required Fields

All inputs (file upload or manual entry) require:
1. **transaction_id** - Text (e.g., "TXN001")
2. **transaction_date** - Date in DD/MM/YYYY format
3. **merchant_id** - Text (e.g., "M12345")
4. **amount** - Positive number (e.g., "500.00")
5. **transaction_type** - Select: Sale, Refund, or Void
6. **card_type** - Select: Visa, Mastercard, Amex, or Discover

---

## Validation Error Message Format

```
Row X, Column Y: Error Description
```

**Examples:**
- `Row 2, transaction_date: Invalid date format (use DD/MM/YYYY)`
- `Row 5, amount: Amount must be a number greater than 0`
- `Row 1, merchant_id: Required field cannot be empty`

---

## Supported File Formats

| Format | Extension | Support |
|--------|-----------|---------|
| CSV | .csv | ✅ Full |
| Excel | .xlsx | ✅ Full |
| Excel | .xls | ✅ Full |

**Parsing:**
- CSV: Line-by-line parsing
- Excel: First sheet, JSON conversion, then validation

---

## API Endpoints (in services/api.js)

### Merchant Fee Calculator
```javascript
merchantFeeAPI.calculateCurrentRates(payload)
merchantFeeAPI.uploadTransactionData(formData)
merchantFeeAPI.getMCCList()
```

### Desired Margin Calculator
```javascript
desiredMarginAPI.calculateDesiredMargin(payload)
desiredMarginAPI.uploadMerchantData(formData)
```

**Fallback:** Mock data returned if API unavailable

---

## UI Component Variants

### Button.jsx
```javascript
<Button variant="default">Primary</Button>
<Button variant="outline">Secondary</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>

<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
```

### Input.jsx
```javascript
<Input type="text" placeholder="Enter text" />
<Input type="number" step="0.01" placeholder="0.00" />
<Input type="email" placeholder="email@example.com" />
```

### Card.jsx
```javascript
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
    <CardDescription>Description</CardDescription>
  </CardHeader>
  <CardContent>Content</CardContent>
  <CardFooter>Footer</CardFooter>
</Card>
```

---

## Tailwind CSS Configuration

**Color Scheme:**
- Primary: Amber (#FBBF24)
- Gray: Standard gray palette
- Red: Error states
- Green: Success states

**Custom Config:** `tailwind.config.js`
- Extended spacing
- Custom font sizes
- Custom colors
- Border radius utilities

---

## Environment Setup

**.env file:**
```
REACT_APP_API_URL=http://localhost:5000/api
```

**Usage:**
```javascript
const apiUrl = process.env.REACT_APP_API_URL;
```

---

## Common Development Commands

```bash
# Start dev server
npm start

# Build for production
npm run build

# Run tests
npm test

# Add dependency
npm install [package-name]
```

---

## Git Branch Info

**Current Branch:** `ui-ux-branch` (local only)
**Remote URL:** https://github.com/Yattmeo/404_found_us.git

**Note:** Branch not yet pushed to remote per user instruction

**Recent Commits:**
```
daa6187 - docs: Add session summary
459e43a - docs: Add comprehensive implementation summary
7b6d6ee - feat: Add Excel file support
7a6f681 - feat: Enhance ManualTransactionEntry
a0bba32 - feat: Implement dynamic React frontend
```

---

## Testing Checklist

### File Upload Testing
- [ ] Upload valid CSV file
- [ ] Upload valid Excel file (.xlsx)
- [ ] Upload valid Excel file (.xls)
- [ ] Upload invalid file type
- [ ] Upload empty file
- [ ] Upload file with missing columns
- [ ] Upload file with invalid data
- [ ] Re-upload after error

### Manual Entry Testing
- [ ] Add multiple rows
- [ ] Duplicate row
- [ ] Delete row
- [ ] Clear all entries
- [ ] Validate with errors
- [ ] Validate successfully
- [ ] Preview table display
- [ ] Proceed to projection

### UI/UX Testing
- [ ] Tab switching
- [ ] Error banner display
- [ ] Field error highlighting
- [ ] Error message clarity
- [ ] Responsive on mobile
- [ ] Responsive on tablet
- [ ] Responsive on desktop
- [ ] Button states (hover, active, disabled)

### API Testing
- [ ] API endpoint responding
- [ ] Fallback to mock data
- [ ] Error handling
- [ ] Loading states

---

## Performance Tips

1. **File Upload:** Large Excel files (>10MB) may take time to parse
2. **Validation:** Real-time validation happens only after user action
3. **Preview:** Limits to first 10 rows for performance
4. **Dropdown:** MCC list is searchable and filtered in real-time

---

## Troubleshooting

### File Won't Upload
- Check file format (CSV, XLSX, or XLS)
- Check file size
- Verify file has required columns

### Validation Fails
- Check date format (DD/MM/YYYY)
- Check amounts are positive numbers
- Check all required fields are filled
- Review error messages for specifics

### Preview Not Showing
- Ensure file has valid data
- Check for missing columns
- Verify at least 1 row of data

### Button Not Working
- Check if form is valid
- Check loading state
- Check network/API connection

---

## Next Steps

1. **Integrate Backend API** - Replace mock data with real endpoints
2. **Deploy to Staging** - Test in staging environment
3. **User Testing** - Gather feedback from sales team
4. **Refinements** - Make adjustments based on feedback
5. **Production Release** - Deploy to production

---

**Documentation Last Updated:** [Today's Date]  
**Status:** ✅ Ready for Testing & Integration
