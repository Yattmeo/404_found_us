import React, { useState } from 'react';
import { Plus, Trash2, Copy, AlertCircle, X } from 'lucide-react';
import { Button } from './ui/Button';
import { Input } from './ui/Input';

const ManualTransactionEntry = ({ onValidDataConfirmed }) => {
  const [transactions, setTransactions] = useState([
    {
      transaction_id: '',
      transaction_date: '',
      merchant_id: '',
      amount: '',
      transaction_type: '',
      card_type: ''
    }
  ]);
  const [validationErrors, setValidationErrors] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState([]);

  const addTransaction = () => {
    setTransactions([
      ...transactions,
      {
        transaction_id: '',
        transaction_date: '',
        merchant_id: '',
        amount: '',
        transaction_type: '',
        card_type: ''
      }
    ]);
  };

  const removeTransaction = (index) => {
    if (transactions.length > 1) {
      setTransactions(transactions.filter((_, i) => i !== index));
    }
  };

  const duplicateTransaction = (index) => {
    const duplicate = { ...transactions[index] };
    setTransactions([...transactions.slice(0, index + 1), duplicate, ...transactions.slice(index + 1)]);
  };

  const updateTransaction = (index, field, value) => {
    const updated = [...transactions];
    updated[index][field] = value;
    setTransactions(updated);
  };

  const clearAllEntries = () => {
    setTransactions([{
      transaction_id: '',
      transaction_date: '',
      merchant_id: '',
      amount: '',
      transaction_type: '',
      card_type: ''
    }]);
    setValidationErrors([]);
  };

  const validateDate = (dateStr) => {
    const formats = [
      /^\d{2}\/\d{2}\/\d{4}$/,
      /^\d{4}-\d{2}-\d{2}$/,
      /^\d{2}-\d{2}-\d{4}$/
    ];
    return formats.some(format => format.test(dateStr));
  };

  const validateAmount = (amount) => {
    const num = parseFloat(amount);
    return !isNaN(num) && isFinite(num) && num > 0;
  };

  const handleValidateAndPreview = () => {
    const errors = [];
    const validTransactions = [];

    transactions.forEach((t, rowIdx) => {
      const rowNum = rowIdx + 1;
      
      // Check required fields
      if (!t.transaction_id) {
        errors.push({
          row: rowNum,
          column: 'transaction_id',
          error: 'Required field cannot be empty'
        });
      }
      
      if (!t.transaction_date) {
        errors.push({
          row: rowNum,
          column: 'transaction_date',
          error: 'Required field cannot be empty'
        });
      } else if (!validateDate(t.transaction_date)) {
        errors.push({
          row: rowNum,
          column: 'transaction_date',
          error: 'Invalid date format (use DD/MM/YYYY)'
        });
      }
      
      if (!t.merchant_id) {
        errors.push({
          row: rowNum,
          column: 'merchant_id',
          error: 'Required field cannot be empty'
        });
      }
      
      if (!t.amount) {
        errors.push({
          row: rowNum,
          column: 'amount',
          error: 'Required field cannot be empty'
        });
      } else if (!validateAmount(t.amount)) {
        errors.push({
          row: rowNum,
          column: 'amount',
          error: 'Amount must be a number greater than 0'
        });
      }
      
      if (!t.transaction_type) {
        errors.push({
          row: rowNum,
          column: 'transaction_type',
          error: 'Required field cannot be empty'
        });
      }
      
      if (!t.card_type) {
        errors.push({
          row: rowNum,
          column: 'card_type',
          error: 'Required field cannot be empty'
        });
      }

      if (errors.filter(e => e.row === rowNum).length === 0) {
        validTransactions.push(t);
      }
    });

    if (errors.length > 0) {
      setValidationErrors(errors);
      setShowPreview(false);
    } else {
      setValidationErrors([]);
      setPreviewData(validTransactions);
      setShowPreview(true);
    }
  };

  const handleProceed = () => {
    if (previewData.length > 0) {
      onValidDataConfirmed(previewData);
    }
  };

  if (showPreview) {
    return (
      <div className="space-y-4 bg-white rounded-2xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Preview: Manual Entries</h3>
          <p className="text-sm text-gray-600">{previewData.length} rows</p>
        </div>

        {/* Preview Table */}
        <div className="overflow-x-auto border border-gray-200 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-700">transaction_id</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-700">transaction_date</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-700">merchant_id</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-700">amount</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-700">transaction_type</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-700">card_type</th>
              </tr>
            </thead>
            <tbody>
              {previewData.map((row, idx) => (
                <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-4 py-2 text-gray-900">{row.transaction_id}</td>
                  <td className="px-4 py-2 text-gray-900">{row.transaction_date}</td>
                  <td className="px-4 py-2 text-gray-900">{row.merchant_id}</td>
                  <td className="px-4 py-2 text-gray-900">${parseFloat(row.amount).toFixed(2)}</td>
                  <td className="px-4 py-2 text-gray-900">{row.transaction_type}</td>
                  <td className="px-4 py-2 text-gray-900">{row.card_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => setShowPreview(false)}
            className="flex-1"
          >
            Back to Edit
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
    );
  }

  return (
    <div className="space-y-4">
      {/* Global Error Banner */}
      {validationErrors.length > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">
              Validation failed for {validationErrors.length} error(s). Please fix the highlighted fields.
            </p>
          </div>
        </div>
      )}

      {/* Entries Table */}
      <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-lg p-4 bg-white">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700 w-8">#</th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700">transaction_id</th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700">transaction_date</th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700">merchant_id</th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700">amount</th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700">transaction_type</th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-gray-700">card_type</th>
              <th className="px-2 py-2 text-center text-xs font-semibold text-gray-700 w-20">Actions</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((transaction, index) => {
              const rowErrors = validationErrors.filter(e => e.row === index + 1);
              const hasError = rowErrors.length > 0;
              
              return (
                <tr
                  key={index}
                  className={`border-b ${
                    hasError ? 'bg-red-50 border-red-200' : index % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                  }`}
                >
                  <td className="px-2 py-2 text-gray-600 text-xs font-medium">{index + 1}</td>
                  <td className="px-2 py-2">
                    <Input
                      type="text"
                      value={transaction.transaction_id}
                      onChange={(e) => updateTransaction(index, 'transaction_id', e.target.value)}
                      placeholder="TXN001"
                      className={`h-8 text-xs ${
                        rowErrors.some(e => e.column === 'transaction_id') ? 'border-red-500' : ''
                      }`}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      type="text"
                      value={transaction.transaction_date}
                      onChange={(e) => updateTransaction(index, 'transaction_date', e.target.value)}
                      placeholder="DD/MM/YYYY"
                      className={`h-8 text-xs ${
                        rowErrors.some(e => e.column === 'transaction_date') ? 'border-red-500' : ''
                      }`}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      type="text"
                      value={transaction.merchant_id}
                      onChange={(e) => updateTransaction(index, 'merchant_id', e.target.value)}
                      placeholder="M12345"
                      className={`h-8 text-xs ${
                        rowErrors.some(e => e.column === 'merchant_id') ? 'border-red-500' : ''
                      }`}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <Input
                      type="number"
                      step="0.01"
                      value={transaction.amount}
                      onChange={(e) => updateTransaction(index, 'amount', e.target.value)}
                      placeholder="0.00"
                      className={`h-8 text-xs ${
                        rowErrors.some(e => e.column === 'amount') ? 'border-red-500' : ''
                      }`}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <select
                      value={transaction.transaction_type}
                      onChange={(e) => updateTransaction(index, 'transaction_type', e.target.value)}
                      className={`w-full h-8 px-2 py-1 border rounded-lg focus:ring-2 focus:ring-amber-500 text-xs ${
                        rowErrors.some(e => e.column === 'transaction_type') ? 'border-red-500' : 'border-gray-300'
                      }`}
                    >
                      <option value="">Select</option>
                      <option value="Sale">Sale</option>
                      <option value="Refund">Refund</option>
                      <option value="Void">Void</option>
                    </select>
                  </td>
                  <td className="px-2 py-2">
                    <select
                      value={transaction.card_type}
                      onChange={(e) => updateTransaction(index, 'card_type', e.target.value)}
                      className={`w-full h-8 px-2 py-1 border rounded-lg focus:ring-2 focus:ring-amber-500 text-xs ${
                        rowErrors.some(e => e.column === 'card_type') ? 'border-red-500' : 'border-gray-300'
                      }`}
                    >
                      <option value="">Select</option>
                      <option value="Visa">Visa</option>
                      <option value="Mastercard">Mastercard</option>
                      <option value="Amex">American Express</option>
                      <option value="Discover">Discover</option>
                    </select>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex gap-1 justify-center">
                      <button
                        type="button"
                        onClick={() => duplicateTransaction(index)}
                        className="p-1 text-gray-600 hover:text-amber-600 rounded"
                        title="Duplicate"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeTransaction(index)}
                        className="p-1 text-gray-600 hover:text-red-600 rounded disabled:opacity-50"
                        disabled={transactions.length === 1}
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Error Details */}
      {validationErrors.length > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <h4 className="text-sm font-semibold text-red-800 mb-3">Validation Errors</h4>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {validationErrors.map((error, idx) => (
              <div key={idx} className="text-xs text-red-700 p-2 bg-red-100 rounded">
                <span className="font-medium">Row {error.row}, {error.column}:</span> {error.error}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={addTransaction}
          className="flex items-center justify-center gap-2 flex-1"
        >
          <Plus className="w-4 h-4" />
          Add Row
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={clearAllEntries}
          className="flex-1"
        >
          Clear All
        </Button>
      </div>

      {/* Validate & Preview Button */}
      <Button
        type="button"
        onClick={handleValidateAndPreview}
        disabled={transactions.every(t => Object.values(t).every(v => !v))}
        className="w-full"
      >
        Validate & Preview
      </Button>
    </div>
  );
};

export default ManualTransactionEntry;
