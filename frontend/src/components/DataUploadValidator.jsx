import React, { useState } from 'react';
import { Upload, FileCheck, AlertCircle, X } from 'lucide-react';
import { Button } from './ui/Button';
import { parseFileData } from '../utils/fileParser';

const DataUploadValidator = ({ onValidDataConfirmed, onMCCExtracted }) => {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationErrors, setValidationErrors] = useState([]);
  const [fileError, setFileError] = useState('');
  const [previewData, setPreviewData] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [fullData, setFullData] = useState([]);
  const [detectedMcc, setDetectedMcc] = useState('');

  const requiredColumns = ['transaction_id', 'transaction_date', 'card_brand', 'merchant_id', 'amount', 'card_type'];

  const extractMccFromFilename = (name) => {
    if (!name) return '';
    const match = String(name).match(/(?:^|[_-])mcc[_-]?(\d{4})(?:[_-]|\.|$)/i);
    return match ? match[1] : '';
  };

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
      const validation = await parseFileData(file, requiredColumns, {
        summaryOnly: true,
        previewLimit: 10,
        maxErrors: 100,
      });

      if (validation.errors.length === 0) {
        setPreviewData(validation.data || []);
        setFullData(validation.summary || validation.data || []);
        const mccFromSummary = validation?.summary?.mcc ? String(validation.summary.mcc).trim() : '';
        const mccFromRows = Array.isArray(validation?.data) && validation.data.length > 0 && validation.data[0]?.mcc
          ? String(validation.data[0].mcc).trim()
          : '';
        const mccFromFile = extractMccFromFilename(file.name);
        setDetectedMcc(mccFromSummary || mccFromRows || mccFromFile || '');
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
    const totalRows = Array.isArray(fullData)
      ? fullData.length
      : Number(fullData?.totalTransactions || 0);

    if (totalRows > 0) {
      onValidDataConfirmed(fullData);
      if (detectedMcc && onMCCExtracted) {
        onMCCExtracted(detectedMcc);
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
    setDetectedMcc('');
  };

  const totalRows = Array.isArray(fullData)
    ? fullData.length
    : Number(fullData?.totalTransactions || 0);

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
              dragActive ? 'border-[#22C55E] bg-green-50' : 'border-gray-300 hover:border-[#22C55E]'
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
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#22C55E]"></div>
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
                    <span className="inline-flex items-center gap-2 px-4 py-2 bg-[#22C55E] hover:bg-[#16A34A] text-white rounded-lg font-medium text-sm transition-colors">
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
                      <span className="text-[#22C55E] hover:text-[#16A34A] font-medium">Click to upload</span>
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
                        className="text-[#22C55E] hover:text-[#16A34A] underline font-medium"
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
            <p className="text-sm text-gray-600">{totalRows} total rows</p>
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

          <p className="text-xs text-gray-600">Showing first {previewData.length} rows of {totalRows} total</p>

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
