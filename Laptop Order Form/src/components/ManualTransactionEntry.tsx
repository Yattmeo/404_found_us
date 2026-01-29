import { useState } from 'react';
import { Plus, Trash2, Copy, X, AlertCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Alert, AlertDescription } from './ui/alert';

interface TransactionRow {
  transaction_id: string;
  transaction_date: string;
  merchant_id: string;
  amount: string;
  transaction_type: string;
  card_type: string;
}

interface ManualTransactionEntryProps {
  onValidDataConfirmed: (data: TransactionRow[]) => void;
}

interface RowError {
  field: keyof TransactionRow;
  message: string;
}

export function ManualTransactionEntry({ onValidDataConfirmed }: ManualTransactionEntryProps) {
  const [rows, setRows] = useState<TransactionRow[]>([
    {
      transaction_id: '',
      transaction_date: '',
      merchant_id: '',
      amount: '',
      transaction_type: '',
      card_type: ''
    }
  ]);
  const [errors, setErrors] = useState<Map<number, RowError[]>>(new Map());
  const [globalError, setGlobalError] = useState('');

  const validateDate = (dateStr: string): boolean => {
    if (!dateStr) return false;
    const formats = [
      /^\d{2}\/\d{2}\/\d{4}$/,
      /^\d{4}-\d{2}-\d{2}$/,
      /^\d{2}-\d{2}-\d{4}$/
    ];
    return formats.some(format => format.test(dateStr));
  };

  const validateRow = (row: TransactionRow): RowError[] => {
    const rowErrors: RowError[] = [];

    if (!row.transaction_id.trim()) {
      rowErrors.push({ field: 'transaction_id', message: 'Required field cannot be empty' });
    }

    if (!row.transaction_date.trim()) {
      rowErrors.push({ field: 'transaction_date', message: 'Required field cannot be empty' });
    } else if (!validateDate(row.transaction_date)) {
      rowErrors.push({ field: 'transaction_date', message: 'Invalid date format' });
    }

    if (!row.merchant_id.trim()) {
      rowErrors.push({ field: 'merchant_id', message: 'Required field cannot be empty' });
    }

    if (!row.amount.trim()) {
      rowErrors.push({ field: 'amount', message: 'Required field cannot be empty' });
    } else if (isNaN(parseFloat(row.amount))) {
      rowErrors.push({ field: 'amount', message: 'Amount must be a valid number' });
    }

    if (!row.transaction_type.trim()) {
      rowErrors.push({ field: 'transaction_type', message: 'Required field cannot be empty' });
    }

    if (!row.card_type.trim()) {
      rowErrors.push({ field: 'card_type', message: 'Required field cannot be empty' });
    }

    return rowErrors;
  };

  const validateAllRows = (): boolean => {
    const newErrors = new Map<number, RowError[]>();
    let hasErrors = false;

    rows.forEach((row, index) => {
      const rowErrors = validateRow(row);
      if (rowErrors.length > 0) {
        newErrors.set(index, rowErrors);
        hasErrors = true;
      }
    });

    setErrors(newErrors);
    
    if (hasErrors) {
      const errorCount = Array.from(newErrors.values()).reduce((sum, errs) => sum + errs.length, 0);
      setGlobalError(`Validation failed for ${errorCount} field(s). Please fix the highlighted fields.`);
    } else {
      setGlobalError('');
    }

    return !hasErrors;
  };

  const handleAddRow = () => {
    setRows([...rows, {
      transaction_id: '',
      transaction_date: '',
      merchant_id: '',
      amount: '',
      transaction_type: '',
      card_type: ''
    }]);
  };

  const handleDeleteRow = (index: number) => {
    if (rows.length > 1) {
      const newRows = rows.filter((_, i) => i !== index);
      setRows(newRows);
      
      // Update errors map
      const newErrors = new Map<number, RowError[]>();
      errors.forEach((value, key) => {
        if (key < index) {
          newErrors.set(key, value);
        } else if (key > index) {
          newErrors.set(key - 1, value);
        }
      });
      setErrors(newErrors);
    }
  };

  const handleDuplicateRow = (index: number) => {
    const duplicatedRow = { ...rows[index] };
    const newRows = [...rows];
    newRows.splice(index + 1, 0, duplicatedRow);
    setRows(newRows);
  };

  const handleClearAll = () => {
    if (confirm('Are you sure you want to clear all entries?')) {
      setRows([{
        transaction_id: '',
        transaction_date: '',
        merchant_id: '',
        amount: '',
        transaction_type: '',
        card_type: ''
      }]);
      setErrors(new Map());
      setGlobalError('');
    }
  };

  const handleFieldChange = (index: number, field: keyof TransactionRow, value: string) => {
    const newRows = [...rows];
    newRows[index][field] = value;
    setRows(newRows);
    
    // Clear error for this field if it exists
    if (errors.has(index)) {
      const rowErrors = errors.get(index)!.filter(e => e.field !== field);
      if (rowErrors.length === 0) {
        const newErrors = new Map(errors);
        newErrors.delete(index);
        setErrors(newErrors);
      } else {
        const newErrors = new Map(errors);
        newErrors.set(index, rowErrors);
        setErrors(newErrors);
      }
    }
  };

  const handleProceed = () => {
    if (validateAllRows()) {
      onValidDataConfirmed(rows);
    }
  };

  const getFieldError = (rowIndex: number, field: keyof TransactionRow): string | undefined => {
    const rowErrors = errors.get(rowIndex);
    return rowErrors?.find(e => e.field === field)?.message;
  };

  const hasErrors = (rowIndex: number, field: keyof TransactionRow): boolean => {
    return !!getFieldError(rowIndex, field);
  };

  const hasValidData = rows.some(row => 
    Object.values(row).some(value => value.trim() !== '')
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-700">
          Manual Transaction Entry
        </label>
        <div className="flex gap-2">
          <Button 
            type="button" 
            variant="outline" 
            size="sm" 
            onClick={handleAddRow}
          >
            <Plus className="w-4 h-4 mr-1" />
            Add Row
          </Button>
          <Button 
            type="button" 
            variant="outline" 
            size="sm" 
            onClick={handleClearAll}
            disabled={rows.length === 1 && !hasValidData}
          >
            <X className="w-4 h-4 mr-1" />
            Clear All
          </Button>
        </div>
      </div>

      {/* Global Error Banner */}
      {globalError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{globalError}</AlertDescription>
        </Alert>
      )}

      {/* Table */}
      <div className="border border-gray-300 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 border-b border-gray-300">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Transaction ID</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Date</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Merchant ID</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Amount</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Type</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Card Type</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr 
                  key={index} 
                  className={`border-b border-gray-200 ${errors.has(index) ? 'bg-red-50' : 'hover:bg-gray-50'}`}
                >
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.transaction_id}
                      onChange={(e) => handleFieldChange(index, 'transaction_id', e.target.value)}
                      className={`w-full px-2 py-1 border rounded ${
                        hasErrors(index, 'transaction_id') 
                          ? 'border-red-500 bg-red-50' 
                          : 'border-gray-300'
                      } focus:ring-1 focus:ring-orange-500 focus:border-orange-500`}
                      placeholder="TXN001"
                    />
                    {hasErrors(index, 'transaction_id') && (
                      <p className="text-xs text-red-600 mt-1">{getFieldError(index, 'transaction_id')}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.transaction_date}
                      onChange={(e) => handleFieldChange(index, 'transaction_date', e.target.value)}
                      className={`w-full px-2 py-1 border rounded ${
                        hasErrors(index, 'transaction_date') 
                          ? 'border-red-500 bg-red-50' 
                          : 'border-gray-300'
                      } focus:ring-1 focus:ring-orange-500 focus:border-orange-500`}
                      placeholder="DD/MM/YYYY"
                    />
                    {hasErrors(index, 'transaction_date') && (
                      <p className="text-xs text-red-600 mt-1">{getFieldError(index, 'transaction_date')}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.merchant_id}
                      onChange={(e) => handleFieldChange(index, 'merchant_id', e.target.value)}
                      className={`w-full px-2 py-1 border rounded ${
                        hasErrors(index, 'merchant_id') 
                          ? 'border-red-500 bg-red-50' 
                          : 'border-gray-300'
                      } focus:ring-1 focus:ring-orange-500 focus:border-orange-500`}
                      placeholder="M001"
                    />
                    {hasErrors(index, 'merchant_id') && (
                      <p className="text-xs text-red-600 mt-1">{getFieldError(index, 'merchant_id')}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.amount}
                      onChange={(e) => handleFieldChange(index, 'amount', e.target.value)}
                      className={`w-full px-2 py-1 border rounded ${
                        hasErrors(index, 'amount') 
                          ? 'border-red-500 bg-red-50' 
                          : 'border-gray-300'
                      } focus:ring-1 focus:ring-orange-500 focus:border-orange-500`}
                      placeholder="100.00"
                    />
                    {hasErrors(index, 'amount') && (
                      <p className="text-xs text-red-600 mt-1">{getFieldError(index, 'amount')}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.transaction_type}
                      onChange={(e) => handleFieldChange(index, 'transaction_type', e.target.value)}
                      className={`w-full px-2 py-1 border rounded ${
                        hasErrors(index, 'transaction_type') 
                          ? 'border-red-500 bg-red-50' 
                          : 'border-gray-300'
                      } focus:ring-1 focus:ring-orange-500 focus:border-orange-500`}
                      placeholder="Sale"
                    />
                    {hasErrors(index, 'transaction_type') && (
                      <p className="text-xs text-red-600 mt-1">{getFieldError(index, 'transaction_type')}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={row.card_type}
                      onChange={(e) => handleFieldChange(index, 'card_type', e.target.value)}
                      className={`w-full px-2 py-1 border rounded ${
                        hasErrors(index, 'card_type') 
                          ? 'border-red-500 bg-red-50' 
                          : 'border-gray-300'
                      } focus:ring-1 focus:ring-orange-500 focus:border-orange-500`}
                      placeholder="Visa"
                    />
                    {hasErrors(index, 'card_type') && (
                      <p className="text-xs text-red-600 mt-1">{getFieldError(index, 'card_type')}</p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDuplicateRow(index)}
                        title="Duplicate row"
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteRow(index)}
                        disabled={rows.length === 1}
                        title="Delete row"
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Proceed Button */}
      <Button
        type="button"
        onClick={handleProceed}
        disabled={!hasValidData}
        className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Validate & Proceed to Projection
      </Button>
    </div>
  );
}
