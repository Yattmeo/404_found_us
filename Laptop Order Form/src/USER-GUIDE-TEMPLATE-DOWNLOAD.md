# CSV Template Download - User Guide

## 🎯 Overview

The **Download Template** feature allows users to quickly get a properly formatted CSV template with the correct column headers and example data. This ensures users always upload files in the correct format.

---

## 📥 How to Download the Template

### Step 1: Navigate to Upload Section
1. Open the **Rates Quotation Tool**
2. Click on the **"Merchant Profitability Calculator"** card
3. You'll see the **"Upload CSV"** tab (selected by default)

### Step 2: Click Download Template
1. Look at the top-right corner of the upload section
2. You'll see a **"Download Template"** button with a download icon
3. Click the button

### Step 3: Save the File
1. Your browser will automatically download: **`transaction-template.csv`**
2. Save it to your desired location
3. The file is ready to use!

---

## 📋 What's in the Template?

### File Contents
The template includes:
- ✅ **All required column headers** (properly formatted)
- ✅ **2 example rows** showing the correct data format
- ✅ **Ready to edit** - just replace example data with your own

### Template Structure
```csv
transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type
TXN001,17/01/2026,M12345,500.00,Sale,Visa
TXN002,18/01/2026,M12345,250.50,Sale,Mastercard
```

---

## ✏️ How to Use the Template

### Method 1: Edit in Excel
1. Open the downloaded `transaction-template.csv` in Microsoft Excel
2. Keep the header row (Row 1) unchanged
3. Delete or replace the example rows (Rows 2-3)
4. Add your transaction data starting from Row 2
5. Save the file (keep it as CSV format)

### Method 2: Edit in Google Sheets
1. Open Google Sheets
2. Go to **File** → **Import**
3. Upload the `transaction-template.csv`
4. Keep the header row unchanged
5. Replace example rows with your data
6. Download as CSV: **File** → **Download** → **Comma Separated Values (.csv)**

### Method 3: Edit in Text Editor
1. Open the template in Notepad, TextEdit, or VS Code
2. Keep the first line (headers) exactly as is
3. Add your data following the format:
   ```
   transaction_id,date,merchant_id,amount,type,card
   ```
4. Save the file

---

## 📊 Column Requirements

### Required Columns (All 6 Must Be Present)

| Column | Description | Format | Example |
|--------|-------------|--------|---------|
| **transaction_id** | Unique identifier for each transaction | Any text/number | TXN001, T123, 00001 |
| **transaction_date** | Date of transaction | DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY | 17/01/2026, 2026-01-17 |
| **merchant_id** | Merchant identifier | Any text/number | M12345, MERCH001 |
| **amount** | Transaction amount | Numeric only (no symbols) | 500.00, 1250.50 |
| **transaction_type** | Type of transaction | Any text | Sale, Refund, Chargeback |
| **card_type** | Card brand used | Any text | Visa, Mastercard, Amex |

---

## ✅ Data Entry Best Practices

### DO:
- ✅ Keep the header row exactly as provided
- ✅ Use consistent date formats throughout your file
- ✅ Enter amounts as plain numbers (e.g., 500.00)
- ✅ Fill in all 6 columns for every transaction
- ✅ Use simple text for transaction types
- ✅ Keep merchant_id consistent for the same merchant

### DON'T:
- ❌ Change column names in the header row
- ❌ Rearrange the column order
- ❌ Include currency symbols in amounts ($, €, £)
- ❌ Leave any required fields empty
- ❌ Use special characters that might break CSV format
- ❌ Mix different merchants in one file (recommended)

---

## 🎯 Example: Good vs. Bad Data

### ✅ Good Example
```csv
transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type
TXN001,17/01/2026,M12345,500.00,Sale,Visa
TXN002,18/01/2026,M12345,250.50,Sale,Mastercard
TXN003,19/01/2026,M12345,1000.00,Refund,Visa
```

### ❌ Bad Example
```csv
ID,Date,Merchant,Price,Type,Card                    ← Wrong headers
TXN001,17-01-2026,M12345,$500.00,Sale,Visa         ← $ symbol in amount
TXN002,invalid,M12345,250.50,Sale,                 ← Invalid date, missing card_type
TXN003,19/01/2026,,abc,Sale,Visa                   ← Missing merchant_id, non-numeric amount
```

---

## 🔄 Complete Workflow

### 1. Download Template
```
Click "Download Template" → Save to computer
```

### 2. Fill in Your Data
```
Open in Excel/Sheets → Replace examples → Add your rows
```

### 3. Save as CSV
```
File → Save As → CSV format
```

### 4. Upload to System
```
Drag & drop OR Click "Choose File"
```

### 5. Validation
```
System validates → Shows preview → Proceed or fix errors
```

---

## 🚨 Common Errors & Solutions

### Error: "Missing required columns"
**Problem**: Column headers don't match expected names
**Solution**: Download template again and use exact column names

### Error: "Invalid date format"
**Problem**: Date not in DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY format
**Solution**: Use one of the accepted formats consistently

### Error: "Amount must be a valid number"
**Problem**: Amount field contains text or currency symbols
**Solution**: Enter amounts as plain numbers (e.g., 500.00 not $500.00)

### Error: "Required field cannot be empty"
**Problem**: One or more cells are blank
**Solution**: Fill in all required fields for every transaction

---

## 💡 Pro Tips

### Tip 1: Keep a Master Template
Save a blank template on your computer for future use. No need to download every time!

### Tip 2: Use Excel Formulas
You can use Excel formulas to generate transaction IDs:
```excel
=TEXT(ROW()-1,"TXN000")
```

### Tip 3: Date Formatting in Excel
If Excel changes your date format, use TEXT formula:
```excel
=TEXT(A2,"DD/MM/YYYY")
```

### Tip 4: Validate Before Upload
Review your data before uploading:
- All dates in same format
- All amounts are numbers
- No empty cells
- Headers unchanged

### Tip 5: Use Consistent Transaction IDs
Follow a pattern like:
- TXN001, TXN002, TXN003
- 2026-001, 2026-002, 2026-003
- T20260117-001

---

## 📱 Quick Reference Card

```
┌─────────────────────────────────────────────────┐
│         CSV TEMPLATE QUICK GUIDE                │
├─────────────────────────────────────────────────┤
│                                                 │
│ 📥 Download: Click "Download Template" button  │
│                                                 │
│ ✏️ Edit: Replace example rows with your data   │
│                                                 │
│ 💾 Save: Keep as CSV format                     │
│                                                 │
│ 📤 Upload: Drag & drop or choose file          │
│                                                 │
│ ✅ Validate: Review preview before proceeding   │
│                                                 │
├─────────────────────────────────────────────────┤
│ Required Columns (6):                           │
│ • transaction_id                                │
│ • transaction_date (DD/MM/YYYY)                 │
│ • merchant_id                                   │
│ • amount (numeric only)                         │
│ • transaction_type                              │
│ • card_type                                     │
└─────────────────────────────────────────────────┘
```

---

## 🎓 Video Tutorial (Conceptual Flow)

### Step-by-Step Visual Guide

**1. Download (5 seconds)**
```
[Screenshot: Download Template button highlighted]
Click the Download Template button
↓
File saves to Downloads folder
```

**2. Open (10 seconds)**
```
[Screenshot: Excel with template open]
Open transaction-template.csv in Excel
↓
See headers + 2 example rows
```

**3. Edit (30 seconds)**
```
[Screenshot: Adding data in Excel]
Delete example rows
Add your transaction data
Ensure all 6 columns filled
```

**4. Save (5 seconds)**
```
[Screenshot: Save As dialog]
File → Save
Keep CSV format
```

**5. Upload (10 seconds)**
```
[Screenshot: Drag & drop area]
Return to application
Drag file to upload area
OR click Choose File
```

**6. Success (5 seconds)**
```
[Screenshot: Preview table]
See preview of 10 rows
Click "Proceed to Projection"
```

---

## ❓ Frequently Asked Questions

### Q1: Can I add more columns to the template?
**A:** Yes, but the 6 required columns must remain. Extra columns will be ignored.

### Q2: How many transactions can I include?
**A:** There's no strict limit, but for best performance keep it under 10,000 rows.

### Q3: Can I use the template multiple times?
**A:** Yes! Download once and reuse it as many times as needed.

### Q4: What if my date format is different?
**A:** The system accepts DD/MM/YYYY, YYYY-MM-DD, and MM/DD/YYYY. Choose one and be consistent.

### Q5: Do I need to include the example rows?
**A:** No, you should delete them and add your own data.

### Q6: Can I save the file with a different name?
**A:** Yes, you can rename it. The system only checks the content, not the filename.

### Q7: What if I make a mistake?
**A:** The system will show detailed errors. Fix them and re-upload.

### Q8: Can I edit the file after uploading?
**A:** Yes, click "Re-upload File" or "Edit Data" to make changes.

---

## 📞 Support

### Need Help?
- Check the error messages - they're detailed and helpful
- Review this guide for data format requirements
- Download a fresh template if columns are wrong
- Use the sample files for reference:
  - `sample-transactions-correct-format.csv` (valid)
  - `sample-transactions-with-errors.csv` (invalid examples)

### Still Having Issues?
The system provides specific error messages showing:
- Which row has an error
- Which column has an error
- What the error is
- How to fix it

---

## ✨ Summary

The **Download Template** feature provides:
- ✅ Correct CSV structure
- ✅ Proper column headers
- ✅ Example data format
- ✅ Quick start for data entry
- ✅ Error-free uploads

**Download → Edit → Save → Upload → Success!** 🎉

---

## 🔗 Related Documentation
- **QUICK-REFERENCE.md** - Overall system features
- **USER-STORY-CHECKLIST.md** - Complete requirements
- **DATA-VALIDATION-FEATURES.md** - Technical details
- **IMPLEMENTATION-SUMMARY.md** - Feature overview

---

*Last Updated: January 2026*
*Version: 1.0*
