/**
 * File parsing utilities - Consolidated file parsing logic
 */
import * as XLSX from 'xlsx';
import { validateDate, validateAmount } from './validators';

/**
 * Parse CSV or Excel file
 * Returns { valid: boolean, data: array, errors: array }
 */
export const parseFileData = async (file, requiredColumns) => {
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
      rawData = text.split('\n').filter((line) => line.trim());
    }

    return validateFileStructure(rawData, requiredColumns);
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
export const validateFileStructure = (lines, requiredColumns) => {
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

    // Validate required columns
    requiredColumns.forEach((col) => {
      if (!row[col] || row[col] === '') {
        errors.push({
          row: i,
          column: col,
          error: 'Required field cannot be empty',
        });
      }
    });

    // Check for duplicate transaction_id
    if (row['transaction_id']) {
      if (transactionIds.has(row['transaction_id'])) {
        errors.push({
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
      errors.push({
        row: i,
        column: 'transaction_date',
        error: 'Invalid date format or future date. Use DD/MM/YYYY, YYYY-MM-DD, or MM/DD/YYYY. Date cannot be in the future.',
      });
    }

    // Validate amount
    if (row['amount'] && !validateAmount(row['amount'])) {
      errors.push({
        row: i,
        column: 'amount',
        error: 'Amount must be a positive number',
      });
    }

    // Only add row if no errors for this row
    if (errors.filter((e) => e.row === i).length === 0) {
      data.push(row);
    }
  }

  return { valid: errors.length === 0, data, errors };
};
