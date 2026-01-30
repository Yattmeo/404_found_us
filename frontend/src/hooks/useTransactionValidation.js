/**
 * useTransactionValidation Hook - Consolidate transaction data validation
 * Reduces complexity in components that validate transaction data
 */
import { useState } from 'react';
import { validateDate, validateAmount, validateRequired } from '../utils/validators';

const DEFAULT_TRANSACTION = {
  transaction_id: '',
  transaction_date: '',
  merchant_id: '',
  amount: '',
  transaction_type: '',
  card_type: '',
};

export const useTransactionValidation = () => {
  const [transactions, setTransactions] = useState([{ ...DEFAULT_TRANSACTION }]);
  const [validationErrors, setValidationErrors] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState([]);
  const [isValidating, setIsValidating] = useState(false);

  const addTransaction = () => {
    setTransactions([...transactions, { ...DEFAULT_TRANSACTION }]);
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
    setTransactions([{ ...DEFAULT_TRANSACTION }]);
    setValidationErrors([]);
  };

  const validateAndPreview = () => {
    setIsValidating(true);
    const errors = [];
    const validTransactions = [];
    const transactionIds = new Set();

    transactions.forEach((t, rowIdx) => {
      const rowNum = rowIdx + 1;

      // Validate transaction_id
      if (!validateRequired(t.transaction_id)) {
        errors.push({
          row: rowNum,
          column: 'transaction_id',
          error: 'Required field cannot be empty',
        });
      } else {
        if (transactionIds.has(t.transaction_id)) {
          errors.push({
            row: rowNum,
            column: 'transaction_id',
            error: 'Duplicate transaction ID - must be unique',
          });
        } else {
          transactionIds.add(t.transaction_id);
        }
      }

      // Validate transaction_date
      if (!validateRequired(t.transaction_date)) {
        errors.push({
          row: rowNum,
          column: 'transaction_date',
          error: 'Required field cannot be empty',
        });
      } else if (!validateDate(t.transaction_date)) {
        errors.push({
          row: rowNum,
          column: 'transaction_date',
          error: 'Invalid date format or future date (use DD/MM/YYYY or DDMMYYYY, date cannot be in the future)',
        });
      }

      // Validate merchant_id
      if (!validateRequired(t.merchant_id)) {
        errors.push({
          row: rowNum,
          column: 'merchant_id',
          error: 'Required field cannot be empty',
        });
      }

      // Validate amount
      if (!validateRequired(t.amount)) {
        errors.push({
          row: rowNum,
          column: 'amount',
          error: 'Required field cannot be empty',
        });
      } else if (!validateAmount(t.amount)) {
        errors.push({
          row: rowNum,
          column: 'amount',
          error: 'Amount must be a number greater than 0',
        });
      }

      // Validate transaction_type
      if (!validateRequired(t.transaction_type)) {
        errors.push({
          row: rowNum,
          column: 'transaction_type',
          error: 'Required field cannot be empty',
        });
      }

      // Validate card_type
      if (!validateRequired(t.card_type)) {
        errors.push({
          row: rowNum,
          column: 'card_type',
          error: 'Required field cannot be empty',
        });
      }

      // Add to valid transactions if no errors for this row
      if (errors.filter((e) => e.row === rowNum).length === 0) {
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

    setIsValidating(false);
  };

  return {
    transactions,
    validationErrors,
    showPreview,
    previewData,
    isValidating,
    addTransaction,
    removeTransaction,
    duplicateTransaction,
    updateTransaction,
    clearAllEntries,
    validateAndPreview,
    setShowPreview,
    setTransactions,
  };
};
