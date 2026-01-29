import { useState } from 'react';
import { Upload, FileCheck, AlertCircle, X, Loader2, Download } from 'lucide-react';
import { Alert, AlertDescription } from './ui/alert';
import { Button } from './ui/button';

interface TransactionRow {
  transaction_id: string;
  transaction_date: string;
  merchant_id: string;
  amount: string;
  transaction_type: string;
  card_type: string;
}

interface ValidationError {
  row: number;
  column: string;
  error: string;
  errorType: 'MISSING_VALUE' | 'INVALID_TYPE' | 'INVALID_FORMAT' | 'INVALID_DATE';
}

interface DataUploadValidatorProps {
  onValidDataConfirmed: (data: TransactionRow[], mcc: string) => void;
  onMCCExtracted?: (mcc: string) => void;
}

export function DataUploadValidator({ onValidDataConfirmed, onMCCExtracted }: DataUploadValidatorProps) {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [previewData, setPreviewData] = useState<TransactionRow[]>([]);
  const [allData, setAllData] = useState<TransactionRow[]>([]);
  const [fileError, setFileError] = useState('');
  const [extractedMCC, setExtractedMCC] = useState('');

  const requiredColumns = ['transaction_id', 'transaction_date', 'merchant_id', 'amount', 'transaction_type', 'card_type'];

  const handleDownloadTemplate = () => {
    // Create CSV content
    const headers = requiredColumns.join(',');
    const exampleRow1 = 'TXN001,17/01/2026,M12345,500.00,Sale,Visa';
    const exampleRow2 = 'TXN002,18/01/2026,M12345,250.50,Sale,Mastercard';
    const csvContent = `${headers}\n${exampleRow1}\n${exampleRow2}`;
    
    // Create blob and download
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

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateDate = (dateStr: string): boolean => {
    // Accept formats: DD/MM/YYYY, YYYY-MM-DD, MM/DD/YYYY
    const formats = [
      /^\d{2}\/\d{2}\/\d{4}$/,
      /^\d{4}-\d{2}-\d{2}$/,
      /^\d{2}-\d{2}-\d{4}$/
    ];
    return formats.some(format => format.test(dateStr));
  };

  const validateAmount = (amount: string): boolean => {
    return !isNaN(parseFloat(amount)) && isFinite(Number(amount));
  };

  const validateCSVStructure = (text: string): { valid: boolean; data: TransactionRow[]; errors: ValidationError[] } => {
    const lines = text.split('\n').filter(line => line.trim());
    
    if (lines.length < 1) {
      return { valid: false, data: [], errors: [{ row: 0, column: 'file', error: 'File is empty', errorType: 'MISSING_VALUE' }] };
    }

    // Parse header
    const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
    
    // Check for missing required columns
    const missingColumns = requiredColumns.filter(col => !headers.includes(col));
    if (missingColumns.length > 0) {
      return { 
        valid: false, 
        data: [], 
        errors: [{ 
          row: 0, 
          column: missingColumns.join(', '), 
          error: `Missing required columns: ${missingColumns.join(', ')}`, 
          errorType: 'MISSING_VALUE' 
        }] 
      };
    }

    const errors: ValidationError[] = [];
    const data: TransactionRow[] = [];

    // Parse data rows
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim());
      const row: any = {};
      
      headers.forEach((header, index) => {
        row[header] = values[index] || '';
      });

      // Validate each required field
      requiredColumns.forEach(col => {
        if (!row[col] || row[col] === '') {
          errors.push({
            row: i,
            column: col,
            error: `Required field cannot be empty`,
            errorType: 'MISSING_VALUE'
          });
        }
      });

      // Validate date format
      if (row['transaction_date'] && !validateDate(row['transaction_date'])) {
        errors.push({
          row: i,
          column: 'transaction_date',
          error: 'Invalid date format. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY',
          errorType: 'INVALID_DATE'
        });
      }

      // Validate amount is numeric
      if (row['amount'] && !validateAmount(row['amount'])) {
        errors.push({
          row: i,
          column: 'amount',
          error: 'Amount must be a valid number',
          errorType: 'INVALID_TYPE'
        });
      }

      data.push(row as TransactionRow);
    }

    return { valid: errors.length === 0, data, errors };
  };

  const extractMCCFromData = (data: TransactionRow[]): string => {
    // Try to find MCC in merchant_id or look for a pattern
    // This is a simplified extraction - you might need more sophisticated logic
    if (data.length > 0) {
      // For now, return a placeholder. In production, you'd extract from actual data
      // or have an MCC column in the CSV
      return '5812'; // Default MCC for demonstration
    }
    return '';
  };

  const processFile = async (file: File) => {
    setIsValidating(true);
    setFileError('');
    setValidationErrors([]);
    setPreviewData([]);
    setAllData([]);
    setFileName(file.name);

    // Check file type
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setFileError('Invalid file type. Only CSV files are accepted.');
      setIsValidating(false);
      return;
    }

    try {
      const text = await file.text();
      
      // Simulate processing delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const { valid, data, errors } = validateCSVStructure(text);

      if (!valid) {
        setValidationErrors(errors);
        setIsValidating(false);
        return;
      }

      // Extract MCC
      const mcc = extractMCCFromData(data);
      setExtractedMCC(mcc);
      if (onMCCExtracted) {
        onMCCExtracted(mcc);
      }

      // Set preview (first 10 rows)
      setPreviewData(data.slice(0, 10));
      setAllData(data);
      setIsValidating(false);
    } catch (error) {
      setFileError('Error reading file. Please ensure it\'s a valid CSV file.');
      setIsValidating(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handleReupload = () => {
    setFileName('');
    setFileError('');
    setValidationErrors([]);
    setPreviewData([]);
    setAllData([]);
    setExtractedMCC('');
  };

  const handleProceedToProjection = () => {
    onValidDataConfirmed(allData, extractedMCC);
  };

  const hasErrors = fileError || validationErrors.length > 0;
  const hasValidData = previewData.length > 0 && !hasErrors;

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-gray-700">
            Upload Transaction Data (CSV Only)
          </label>
          <Button
            type="button"
            onClick={handleDownloadTemplate}
            variant="outline"
            size="sm"
            className="flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download Template
          </Button>
        </div>
        
        {!fileName && (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl p-8 transition-all ${
              dragActive 
                ? 'border-orange-500 bg-orange-50' 
                : 'border-gray-300 hover:border-orange-400 hover:bg-orange-50'
            }`}
          >
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
              id="csv-upload"
            />
            
            <div className="text-center">
              <Upload className={`w-12 h-12 mx-auto mb-4 ${dragActive ? 'text-orange-500' : 'text-gray-400'}`} />
              <p className="text-lg font-medium text-gray-700 mb-2">
                Drag and drop your CSV file here
              </p>
              <p className="text-sm text-gray-500 mb-4">or</p>
              <label htmlFor="csv-upload">
                <Button type="button" variant="outline" className="cursor-pointer" asChild>
                  <span>Choose File</span>
                </Button>
              </label>
              <p className="text-xs text-gray-500 mt-4">
                Only CSV files accepted. Required columns: transaction_id, transaction_date, merchant_id, amount, transaction_type, card_type
              </p>
              <p className="text-xs text-orange-600 mt-2 font-medium">
                Need a template? Click "Download Template" button above
              </p>
            </div>
          </div>
        )}

        {/* File Selected - Validating */}
        {fileName && isValidating && (
          <div className="border-2 border-gray-300 rounded-2xl p-6">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-orange-500 animate-spin" />
              <div>
                <p className="font-medium text-gray-700">{fileName}</p>
                <p className="text-sm text-gray-500">Validating file...</p>
              </div>
            </div>
          </div>
        )}

        {/* File Error */}
        {fileError && (
          <Alert variant="destructive" className="mt-3">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <div className="flex items-center justify-between">
                <span>{fileError}</span>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={handleReupload}
                  className="ml-4"
                >
                  Re-upload File
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* Validation Errors */}
        {validationErrors.length > 0 && (
          <div className="mt-3 space-y-3">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <strong>Validation failed for {validationErrors.length} issue(s).</strong> Please fix the highlighted fields.
              </AlertDescription>
            </Alert>

            <div className="bg-red-50 border border-red-200 rounded-2xl p-4 max-h-64 overflow-y-auto">
              <p className="font-medium text-red-900 mb-2">Errors found:</p>
              <ul className="space-y-2">
                {validationErrors.map((error, idx) => (
                  <li key={idx} className="text-sm text-red-700">
                    <span className="font-medium">
                      Row {error.row}, Column "{error.column}":
                    </span>{' '}
                    {error.error}
                    <span className="text-xs text-red-600 ml-2">
                      ({error.errorType.replace('_', ' ')})
                    </span>
                  </li>
                ))}
              </ul>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={handleReupload}
                className="mt-4"
              >
                Re-upload File
              </Button>
            </div>
          </div>
        )}

        {/* Success - Preview Table */}
        {hasValidData && (
          <div className="mt-3 space-y-3">
            <div className="p-4 bg-green-50 border border-green-200 rounded-2xl">
              <div className="flex items-start gap-2">
                <FileCheck className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-green-900">
                    File validated successfully
                  </p>
                  <p className="text-sm text-green-700 mt-1">
                    {fileName} - {allData.length} transactions found
                  </p>
                  {extractedMCC && (
                    <p className="text-sm text-green-700">
                      Extracted MCC: <span className="font-medium">{extractedMCC}</span>
                    </p>
                  )}
                </div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={handleReupload}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Preview Table */}
            <div className="border border-gray-300 rounded-2xl overflow-hidden">
              <div className="bg-gray-50 px-4 py-2 border-b border-gray-300">
                <p className="text-sm font-medium text-gray-700">
                  Preview - First 10 Rows
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 border-b border-gray-300">
                    <tr>
                      {requiredColumns.map(col => (
                        <th key={col} className="px-4 py-2 text-left font-medium text-gray-700 whitespace-nowrap">
                          {col.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.map((row, idx) => (
                      <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                        <td className="px-4 py-2">{row.transaction_id}</td>
                        <td className="px-4 py-2">{row.transaction_date}</td>
                        <td className="px-4 py-2">{row.merchant_id}</td>
                        <td className="px-4 py-2">${parseFloat(row.amount).toFixed(2)}</td>
                        <td className="px-4 py-2">{row.transaction_type}</td>
                        <td className="px-4 py-2">{row.card_type}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Proceed Button */}
            <Button
              onClick={handleProceedToProjection}
              className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600"
            >
              Proceed to Projection
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}