/**
 * File parsing utilities - Consolidated file parsing logic
 */
import * as XLSX from 'xlsx';
import { validateDate, validateAmount } from './validators';

const MAX_ERRORS_DEFAULT = 100;

const normalizeCardType = (value) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '';
  if (normalized === 'debit') return 'Debit';
  if (normalized === 'credit') return 'Credit';
  if (normalized === 'debit (prepaid)' || normalized === 'debit(prepaid)' || normalized === 'prepaid') {
    return 'Debit (Prepaid)';
  }
  return '';
};

const buildSummaryResult = (errors, previewRows, summary) => ({
  valid: errors.length === 0,
  data: previewRows,
  errors,
  summary,
});

const parseCSVSummaryMode = (text, requiredColumns, options = {}) => {
  const previewLimit = Number.isInteger(options.previewLimit) ? options.previewLimit : 10;
  const maxErrors = Number.isInteger(options.maxErrors) ? options.maxErrors : MAX_ERRORS_DEFAULT;

  if (!text || !text.trim()) {
    return {
      valid: false,
      data: [],
      errors: [{ row: 0, column: 'file', error: 'File is empty' }],
      summary: { totalTransactions: 0, totalAmount: 0, averageTicket: 0, merchantId: null, mcc: null },
    };
  }

  const firstNewlineIdx = text.search(/\r?\n/);
  const headerLine = firstNewlineIdx === -1 ? text : text.slice(0, firstNewlineIdx);
  const headers = headerLine.split(',').map((h) => h.trim().toLowerCase());

  const missingColumns = requiredColumns.filter((col) => !headers.includes(col));
  if (missingColumns.length > 0) {
    return {
      valid: false,
      data: [],
      errors: [
        {
          row: 0,
          column: missingColumns.join(', '),
          error: `Missing required columns: ${missingColumns.join(', ')}`,
        },
      ],
      summary: { totalTransactions: 0, totalAmount: 0, averageTicket: 0, merchantId: null, mcc: null },
    };
  }

  const errors = [];
  const previewRows = [];
  const summary = {
    totalTransactions: 0,
    totalAmount: 0,
    averageTicket: 0,
    merchantId: null,
    mcc: null,
  };

  const pushError = (row, column, error) => {
    if (errors.length < maxErrors) {
      errors.push({ row, column, error });
    }
  };

  const dataStart = firstNewlineIdx === -1 ? text.length : firstNewlineIdx + (text[firstNewlineIdx] === '\r' ? 2 : 1);
  let start = dataStart;
  let rowIndex = 1;

  while (start <= text.length) {
    const nextLF = text.indexOf('\n', start);
    const end = nextLF === -1 ? text.length : nextLF;
    let line = text.slice(start, end);
    if (line.endsWith('\r')) {
      line = line.slice(0, -1);
    }

    if (line.trim()) {
      const values = line.split(',').map((v) => v.trim());
      const row = {};
      headers.forEach((header, index) => {
        row[header] = values[index] || '';
      });

      let rowHasError = false;
      const addError = (column, message) => {
        rowHasError = true;
        pushError(rowIndex, column, message);
      };

      requiredColumns.forEach((col) => {
        if (!row[col]) {
          addError(col, 'Required field cannot be empty');
        }
      });

      if (row['transaction_date'] && !validateDate(row['transaction_date'])) {
        addError('transaction_date', 'Invalid date/datetime format or future date. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY (datetime also accepted). Date cannot be in the future.');
      }

      if (row['amount'] && !validateAmount(row['amount'])) {
        addError('amount', 'Amount must be a positive number');
      }

      if (row['card_brand'] && !['Visa', 'Mastercard'].includes(row['card_brand'])) {
        addError('card_brand', 'card_brand must be Visa or Mastercard');
      }

      const normalizedCardType = normalizeCardType(row['card_type']);
      if (row['card_type'] && !normalizedCardType) {
        addError('card_type', 'card_type must be Debit, Credit, or Debit (Prepaid)');
      } else if (normalizedCardType) {
        row['card_type'] = normalizedCardType;
      }

      if (!rowHasError) {
        const amount = parseFloat(row['amount']) || 0;
        summary.totalTransactions += 1;
        summary.totalAmount += amount;
        if (!summary.merchantId && row['merchant_id']) {
          summary.merchantId = row['merchant_id'];
        }
        if (!summary.mcc && row['mcc']) {
          summary.mcc = String(row['mcc']).trim();
        }

        if (previewRows.length < previewLimit) {
          previewRows.push(row);
        }
      }

      if (errors.length >= maxErrors) {
        errors.push({
          row: rowIndex,
          column: 'file',
          error: `Validation stopped after ${maxErrors} issues. Please fix these first and retry.`,
        });
        break;
      }

      rowIndex += 1;
    }

    if (nextLF === -1) {
      break;
    }
    start = nextLF + 1;
  }

  if (summary.totalTransactions > 0) {
    summary.averageTicket = summary.totalAmount / summary.totalTransactions;
  }

  return buildSummaryResult(errors, previewRows, summary);
};

/**
 * Parse CSV or Excel file
 * Returns { valid: boolean, data: array, errors: array }
 */
export const parseFileData = async (file, requiredColumns, options = {}) => {
  const isCSV = file.type === 'text/csv' || file.name.endsWith('.csv');
  const isExcel =
    file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    file.type === 'application/vnd.ms-excel' ||
    file.name.endsWith('.xlsx') ||
    file.name.endsWith('.xls');

  if (!isCSV && !isExcel) {
    return {
      valid: false,
      data: [],
      errors: [
        {
          row: 0,
          column: 'file',
          error: 'Invalid file type. Please upload a CSV or Excel file (.csv, .xlsx, .xls).',
        },
      ],
    };
  }

  try {
    let rawData;

    if (isExcel) {
      const arrayBuffer = await file.arrayBuffer();
      const workbook = XLSX.read(arrayBuffer, { type: 'array' });
      const worksheet = workbook.Sheets[workbook.SheetNames[0]];
      const jsonData = XLSX.utils.sheet_to_json(worksheet);

      // Convert to array format with headers
      rawData = [];
      if (jsonData.length > 0) {
        const headers = Object.keys(jsonData[0]);
        rawData.push(headers);
        jsonData.forEach((row) => {
          const values = headers.map((header) => (row[header] ? String(row[header]).trim() : ''));
          rawData.push(values);
        });
      }
    } else {
      // Parse CSV file
      const text = await file.text();
      if (options.summaryOnly === true) {
        return parseCSVSummaryMode(text, requiredColumns, options);
      }
      rawData = text.split('\n').filter((line) => line.trim());
    }

    return validateFileStructure(rawData, requiredColumns, options);
  } catch (error) {
    return {
      valid: false,
      data: [],
      errors: [
        {
          row: 0,
          column: 'file',
          error: `Error parsing file: ${error.message}`,
        },
      ],
    };
  }
};

/**
 * Validate CSV/Excel file structure and data
 */
export const validateFileStructure = (lines, requiredColumns, options = {}) => {
  const summaryOnly = options.summaryOnly === true;
  const previewLimit = Number.isInteger(options.previewLimit) ? options.previewLimit : 10;

  if (!lines || lines.length < 1) {
    return {
      valid: false,
      data: [],
      errors: [{ row: 0, column: 'file', error: 'File is empty' }],
    };
  }

  // Get headers
  let headers = [];
  if (typeof lines[0] === 'string') {
    headers = lines[0].split(',').map((h) => h.trim().toLowerCase());
  } else if (Array.isArray(lines[0])) {
    headers = lines[0].map((h) => String(h).trim().toLowerCase());
  }

  const missingColumns = requiredColumns.filter((col) => !headers.includes(col));
  if (missingColumns.length > 0) {
    return {
      valid: false,
      data: [],
      errors: [
        {
          row: 0,
          column: missingColumns.join(', '),
          error: `Missing required columns: ${missingColumns.join(', ')}`,
        },
      ],
    };
  }

  const errors = [];
  const data = [];
  const transactionIds = new Set();
  const summary = {
    totalTransactions: 0,
    totalAmount: 0,
    averageTicket: 0,
    merchantId: null,
    mcc: null,
  };

  for (let i = 1; i < lines.length; i++) {
    let values;

    if (typeof lines[i] === 'string') {
      values = lines[i].split(',').map((v) => v.trim());
    } else if (Array.isArray(lines[i])) {
      values = lines[i].map((v) => String(v).trim());
    } else {
      continue;
    }

    const row = {};

    headers.forEach((header, index) => {
      row[header] = values[index] || '';
    });

    let rowHasError = false;
    const addError = (error) => {
      errors.push(error);
      rowHasError = true;
    };

    // Validate required columns
    requiredColumns.forEach((col) => {
      if (!row[col] || row[col] === '') {
        addError({
          row: i,
          column: col,
          error: 'Required field cannot be empty',
        });
      }
    });

    // Check for duplicate transaction_id
    if (row['transaction_id']) {
      if (transactionIds.has(row['transaction_id'])) {
        addError({
          row: i,
          column: 'transaction_id',
          error: 'Duplicate transaction ID - must be unique',
        });
      } else {
        transactionIds.add(row['transaction_id']);
      }
    }

    // Validate date
    if (row['transaction_date'] && !validateDate(row['transaction_date'])) {
      addError({
        row: i,
        column: 'transaction_date',
        error: 'Invalid date/datetime format or future date. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY (datetime also accepted). Date cannot be in the future.',
      });
    }

    // Validate amount
    if (row['amount'] && !validateAmount(row['amount'])) {
      addError({
        row: i,
        column: 'amount',
        error: 'Amount must be a positive number',
      });
    }

    // Validate permissible values for card_brand
    if (row['card_brand'] && !['Visa', 'Mastercard'].includes(row['card_brand'])) {
      addError({
        row: i,
        column: 'card_brand',
        error: 'card_brand must be Visa or Mastercard',
      });
    }

    // TEMP BYPASS: defer transaction_type value enforcement during integration.
    // Keep presence validation only via requiredColumns checks above.

    // Validate permissible values for card_type
    const normalizedCardType = normalizeCardType(row['card_type']);
    if (row['card_type'] && !normalizedCardType) {
      addError({
        row: i,
        column: 'card_type',
        error: 'card_type must be Debit, Credit, or Debit (Prepaid)',
      });
    } else if (normalizedCardType) {
      row['card_type'] = normalizedCardType;
    }

    // Validate transaction_id is 7-digit integer
    if (row['transaction_id'] && !/^\d{7}$/.test(row['transaction_id'])) {
      addError({
        row: i,
        column: 'transaction_id',
        error: 'transaction_id must be a 7-digit integer',
      });
    }

    // Validate merchant_id is 6-digit integer
    if (row['merchant_id'] && !/^\d{6}$/.test(row['merchant_id'])) {
      addError({
        row: i,
        column: 'merchant_id',
        error: 'merchant_id must be a 6-digit integer',
      });
    }

    // Only add row if no errors for this row
    if (!rowHasError) {
      if (summaryOnly) {
        const amount = parseFloat(row['amount']) || 0;
        summary.totalTransactions += 1;
        summary.totalAmount += amount;
        if (!summary.merchantId && row['merchant_id']) {
          summary.merchantId = row['merchant_id'];
        }
        if (!summary.mcc && row['mcc']) {
          summary.mcc = String(row['mcc']).trim();
        }
        if (data.length < previewLimit) {
          data.push(row);
        }
      } else {
        data.push(row);
      }
    }
  }

  if (summary.totalTransactions > 0) {
    summary.averageTicket = summary.totalAmount / summary.totalTransactions;
  }

  return {
    valid: errors.length === 0,
    data,
    errors,
    summary: summaryOnly ? summary : undefined,
  };
};
