import React, { useState } from 'react';
import { Upload, FileCheck, AlertCircle, Download } from 'lucide-react';
import { Button } from './ui/Button';
import { Label } from './ui/Label';

const DataUploadValidator = ({ onValidDataConfirmed, onMCCExtracted }) => {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [fileError, setFileError] = useState('');

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

  const validateCSVStructure = (text) => {
    const lines = text.split('\\n').filter(line => line.trim());
    
    if (lines.length < 1) {
      return { valid: false, data: [], errors: [{ row: 0, column: 'file', error: 'File is empty' }] };
    }

    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    
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
      const values = lines[i].split(',').map(v => v.trim());
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
    setFileError('');
    setValidationErrors([]);
    setFileName(file.name);
    setIsValidating(true);

    try {
      const text = await file.text();
      const validation = validateCSVStructure(text);

      if (validation.valid) {
        onValidDataConfirmed(validation.data, 'M123');
        if (onMCCExtracted) {
          onMCCExtracted('5812');
        }
      } else {
        setValidationErrors(validation.errors);
        setFileError('Validation failed. Please fix the errors and try again.');
      }
    } catch (error) {
      setFileError('Error reading file. Please make sure it\\'s a valid CSV file.');
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

  return (
    <div className="space-y-4">
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
          accept=".csv"
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
              <p className="text-sm text-green-600">File validated successfully</p>
            </div>
          ) : (
            <>
              <Upload className="w-12 h-12 text-gray-400 mx-auto" />
              <div>
                <label htmlFor="file-upload" className="cursor-pointer">
                  <span className="text-amber-600 hover:text-amber-700 font-medium">Click to upload</span>
                  <span className="text-gray-600"> or drag and drop</span>
                </label>
                <p className="text-xs text-gray-500 mt-1">CSV files only</p>
              </div>
            </>
          )}
        </div>

        {fileError && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="text-left">
              <p className="text-sm font-medium text-red-800">{fileError}</p>
            </div>
          </div>
        )}
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

      {/* Validation Errors Display */}
      {validationErrors.length > 0 && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg max-h-60 overflow-y-auto">
          <h4 className="text-sm font-semibold text-red-800 mb-2">Validation Errors ({validationErrors.length})</h4>
          <ul className="space-y-1 text-xs text-red-700">
            {validationErrors.slice(0, 10).map((error, index) => (
              <li key={index}>
                Row {error.row}, Column "{error.column}": {error.error}
              </li>
            ))}
            {validationErrors.length > 10 && (
              <li className="font-medium">... and {validationErrors.length - 10} more errors</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
};

export default DataUploadValidator;
