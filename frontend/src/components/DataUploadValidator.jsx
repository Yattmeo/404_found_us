import React, { useState } from 'react';
import { Upload, FileCheck, AlertCircle, Download, X } from 'lucide-react';
import * as XLSX from 'xlsx';
import { Button } from './ui/Button';
import { Label } from './ui/Label';

const DataUploadValidator = ({ onValidDataConfirmed, onMCCExtracted }) => {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [fileError, setFileError] = useState('');
  const [previewData, setPreviewData] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [fullData, setFullData] = useState([]);

  const requiredColumns = ['transaction_id', 'transaction_date', 'merchant_id', 'amount', 'transaction_type', 'card_type'];

  const handleDownloadTemplate = () => {
    const headers = requiredColumns.join(',');
    const exampleRow1 = 'TXN001,17/01/2026,M12345,500.00,Sale,Visa';
    const exampleRow2 = 'TXN002,18/01/2026,M12345,250.50,Sale,Mastercard';
    const csvContent = `${headers}\\n${exampleRow1}\\n${exampleRow2}`;
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', 'transaction-template.csv');
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateDate = (dateStr) => {
    const formats = [
      /^\\d{2}\\/\\d{2}\\/\\d{4}$/,
      /^\\d{4}-\\d{2}-\\d{2}$/,
      /^\\d{2}-\\d{2}-\\d{4}$/
    ];
    return formats.some(format => format.test(dateStr));
  };

  const validateAmount = (amount) => {
    return !isNaN(parseFloat(amount)) && isFinite(Number(amount));
  };

  const validateCSVStructure = (input) => {
    let lines;
    
    // Handle both CSV string and Excel array inputs
    if (typeof input === 'string') {
      lines = input.split('\n').filter(line => line.trim());
    } else if (Array.isArray(input)) {
      lines = input;
    } else {
      return { valid: false, data: [], errors: [{ row: 0, column: 'file', error: 'Invalid file format' }] };
    }
    
    if (lines.length < 1) {
      return { valid: false, data: [], errors: [{ row: 0, column: 'file', error: 'File is empty' }] };
    }

    // Get headers
    let headers = [];
    if (typeof lines[0] === 'string') {
      headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    } else if (Array.isArray(lines[0])) {
      headers = lines[0].map(h => String(h).trim().toLowerCase());
    }
    
    const missingColumns = requiredColumns.filter(col => !headers.includes(col));
    if (missingColumns.length > 0) {
      return { 
        valid: false, 
        data: [], 
        errors: [{ 
          row: 0, 
          column: missingColumns.join(', '), 
          error: `Missing required columns: ${missingColumns.join(', ')}` 
        }] 
      };
    }

    const errors = [];
    const data = [];

    for (let i = 1; i < lines.length; i++) {
      let values;
      
      if (typeof lines[i] === 'string') {
        values = lines[i].split(',').map(v => v.trim());
      } else if (Array.isArray(lines[i])) {
        values = lines[i].map(v => String(v).trim());
      } else {
        continue;
      }
      
      const row = {};
      
      headers.forEach((header, index) => {
        row[header] = values[index] || '';
      });

      requiredColumns.forEach(col => {
        if (!row[col] || row[col] === '') {
          errors.push({
            row: i,
            column: col,
            error: `Required field cannot be empty`
          });
        }
      });

      if (row['transaction_date'] && !validateDate(row['transaction_date'])) {
        errors.push({
          row: i,
          column: 'transaction_date',
          error: 'Invalid date format. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY'
        });
      }

      if (row['amount'] && !validateAmount(row['amount'])) {
        errors.push({
          row: i,
          column: 'amount',
          error: 'Amount must be a valid number'
        });
      }

      if (errors.filter(e => e.row === i).length === 0) {
        data.push(row);
      }
    }

    return { valid: errors.length === 0, data, errors };
  };

  const handleFile = async (file) => {
    // Check file type - allow CSV or Excel
    const isCSV = file.type === 'text/csv' || file.name.endsWith('.csv');
    const isExcel = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || 
                    file.type === 'application/vnd.ms-excel' ||
                    file.name.endsWith('.xlsx') || 
                    file.name.endsWith('.xls');
    
    if (!isCSV && !isExcel) {
      setFileError('Invalid file type. Please upload a CSV or Excel file (.csv, .xlsx, .xls).');
      setFileName('');
      setValidationErrors([]);
      return;
    }

    setFileError('');
    setValidationErrors([]);
    setFileName(file.name);
    setIsValidating(true);

    try {
      let validation;
      
      if (isExcel) {
        // Parse Excel file
        const arrayBuffer = await file.arrayBuffer();
        const workbook = XLSX.read(arrayBuffer, { type: 'array' });
        const worksheet = workbook.Sheets[workbook.SheetNames[0]];
        const jsonData = XLSX.utils.sheet_to_json(worksheet);
        
        // Convert to array format matching CSV structure
        const rows = jsonData.map((row, idx) => {
          const values = Object.values(row).map(v => v ? String(v).trim() : '');
          return values;
        });
        
        validation = validateCSVStructure(rows);
      } else {
        // Parse CSV file
        const text = await file.text();
        validation = validateCSVStructure(text);
      }

      if (validation.errors.length === 0) {
        // Show preview of first 10 rows
        setPreviewData(validation.data.slice(0, 10));
        setFullData(validation.data);
        setShowPreview(true);
        setValidationErrors([]);
      } else {
        setValidationErrors(validation.errors);
        setShowPreview(false);
        setFileError(`Validation failed: ${validation.errors.length} issue(s) found. Please review the errors below.`);
      }
    } catch (error) {
      setFileError('Error reading file. Please ensure it\'s a valid CSV or Excel file.');
      setValidationErrors([]);
    } finally {
      setIsValidating(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleProceed = () => {
    if (fullData.length > 0) {
      onValidDataConfirmed(fullData);
      // Auto-detect MCC if present in data
      if (fullData[0].merchant_id && onMCCExtracted) {
        onMCCExtracted('5812'); // Placeholder - would extract from data
      }
    }
  };

  const handleReupload = () => {
    setFileName('');
    setFileError('');
    setValidationErrors([]);
    setShowPreview(false);
    setPreviewData([]);
    setFullData([]);
  };

  return (
    <div className="space-y-4">
      {/* Global Error Banner */}
      {fileError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">{fileError}</p>
          </div>
          <button onClick={() => setFileError('')} className="text-red-600 hover:text-red-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {!showPreview ? (
        <>
          <div
            className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition-colors ${
              dragActive ? 'border-amber-500 bg-amber-50' : 'border-gray-300 hover:border-amber-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              type="file"
              id="file-upload"
              className="hidden"
              accept=".csv,.xlsx,.xls"
              onChange={handleChange}
            />
            
            <div className="space-y-4">
              {isValidating ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500"></div>
                  <p className="text-sm text-gray-600">Validating file...</p>
                </div>
              ) : fileName && validationErrors.length === 0 ? (
                <div className="flex flex-col items-center gap-2">
                  <FileCheck className="w-12 h-12 text-green-500" />
                  <p className="text-sm font-medium text-gray-900">{fileName}</p>
                  <p className="text-sm text-green-600">{previewData.length} rows ready for preview</p>
                </div>
              ) : (
                <>
                  <Upload className="w-12 h-12 text-gray-400 mx-auto" />
                  <div>
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <span className="text-amber-600 hover:text-amber-700 font-medium">Click to upload</span>
                      <span className="text-gray-600"> or drag and drop</span>
                    </label>
                    <p className="text-xs text-gray-500 mt-1">CSV or Excel files (.csv, .xlsx, .xls)</p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Download Template Button */}
          <Button
            type="button"
            variant="outline"
            onClick={handleDownloadTemplate}
            className="w-full flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download CSV Template
          </Button>
        </>
      ) : (
        // Preview Section
        <div className="space-y-4 bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Preview: {fileName}</h3>
            <p className="text-sm text-gray-600">{fullData.length} total rows</p>
          </div>

          {/* Preview Table */}
          <div className="overflow-x-auto border border-gray-200 rounded-lg">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {requiredColumns.map(col => (
                    <th key={col} className="px-4 py-2 text-left text-xs font-semibold text-gray-700">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewData.map((row, idx) => (
                  <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    {requiredColumns.map(col => (
                      <td key={col} className="px-4 py-2 text-gray-900">
                        {row[col] || '-'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-gray-600">Showing first 10 rows of {fullData.length} total</p>

          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleReupload}
              className="flex-1"
            >
              Re-upload File
            </Button>
            <Button
              type="button"
              onClick={handleProceed}
              className="flex-1"
            >
              Proceed to Projection
            </Button>
          </div>
        </div>
      )}

      {/* Validation Errors Display */}
      {validationErrors.length > 0 && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <h4 className="text-sm font-semibold text-red-800 mb-3">
            Validation Errors ({validationErrors.length})
          </h4>
          <div className="max-h-60 overflow-y-auto space-y-1">
            {validationErrors.map((error, index) => (
              <div key={index} className="text-xs text-red-700 p-2 bg-red-100 rounded">
                <span className="font-medium">Row {error.row}, {error.column}:</span> {error.error}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DataUploadValidator;
