import React, { useState } from 'react';
import { Upload, FileCheck, AlertCircle, X } from 'lucide-react';
import * as XLSX from 'xlsx';
import { Button } from './ui/Button';

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
    const csvContent = headers;
    
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
    if (!dateStr) return false;
    
    const trimmed = dateStr.trim();
    let parsedDate;
    
    // Try to parse different formats - support flexible day/month (1 or 2 digits)
    if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(trimmed)) {
      // D/M/YYYY or DD/MM/YYYY
      const [day, month, year] = trimmed.split('/');
      parsedDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    } else if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(trimmed)) {
      // YYYY-M-D or YYYY-MM-DD
      const [year, month, day] = trimmed.split('-');
      parsedDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    } else if (/^\d{1,2}-\d{1,2}-\d{4}$/.test(trimmed)) {
      // D-M-YYYY or DD-MM-YYYY
      const [day, month, year] = trimmed.split('-');
      parsedDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    } else if (/^\d{8}$/.test(trimmed)) {
      // DDMMYYYY
      const day = trimmed.substring(0, 2);
      const month = trimmed.substring(2, 4);
      const year = trimmed.substring(4, 8);
      parsedDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    } else {
      return false;
    }
    
    // Check if date is valid
    if (!(parsedDate instanceof Date) || isNaN(parsedDate.getTime())) {
      return false;
    }
    
    // Check if date is not in the future
    const today = new Date();
    today.setHours(23, 59, 59, 999); // Set to end of today
    
    return parsedDate <= today;
  };

  const validateAmount = (amount) => {
    const num = parseFloat(amount);
    return !isNaN(num) && isFinite(num) && num > 0;
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
    const transactionIds = new Set();

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

      // Check for duplicate transaction_id
      if (row['transaction_id']) {
        if (transactionIds.has(row['transaction_id'])) {
          errors.push({
            row: i,
            column: 'transaction_id',
            error: 'Duplicate transaction ID - must be unique'
          });
        } else {
          transactionIds.add(row['transaction_id']);
        }
      }

      if (row['transaction_date'] && !validateDate(row['transaction_date'])) {
        errors.push({
          row: i,
          column: 'transaction_date',
          error: 'Invalid date format or future date. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY. Date cannot be in the future.'
        });
      }

      if (row['amount'] && !validateAmount(row['amount'])) {
        errors.push({
          row: i,
          column: 'amount',
          error: 'Amount must be a number greater than 0'
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
        // Include headers as first row
        const rows = [];
        if (jsonData.length > 0) {
          // Get headers from first object
          const headers = Object.keys(jsonData[0]);
          rows.push(headers);
          
          // Add data rows
          jsonData.forEach((row) => {
            const values = headers.map(header => 
              row[header] ? String(row[header]).trim() : ''
            );
            rows.push(values);
          });
        }
        
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
              dragActive ? 'border-[#44D62C] bg-green-50' : 'border-gray-300 hover:border-[#44D62C]'
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
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#44D62C]"></div>
                  <p className="text-sm text-gray-600">Validating file...</p>
                </div>
              ) : fileName && validationErrors.length > 0 ? (
                <div className="flex flex-col items-center gap-3">
                  <AlertCircle className="w-12 h-12 text-red-500" />
                  <div>
                    <p className="text-sm font-medium text-red-900">{fileName}</p>
                    <p className="text-sm text-red-600 mt-1">{validationErrors.length} validation error(s) found</p>
                  </div>
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <span className="inline-flex items-center gap-2 px-4 py-2 bg-[#44D62C] hover:bg-[#3BC424] text-white rounded-lg font-medium text-sm transition-colors">
                      <Upload className="w-4 h-4" />
                      Re-upload File
                    </span>
                  </label>
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
                      <span className="text-[#44D62C] hover:text-[#3BC424] font-medium">Click to upload</span>
                      <span className="text-gray-600"> or drag and drop</span>
                    </label>
                    <p className="text-xs text-gray-500 mt-1">CSV or Excel files (.csv, .xlsx, .xls)</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Need a template?{' '}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadTemplate();
                        }}
                        className="text-[#44D62C] hover:text-[#3BC424] underline font-medium"
                      >
                        Download Template
                      </button>
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
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
