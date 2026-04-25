/**
 * Validation utilities - Consolidated validation logic
 */

/**
 * Validate date in multiple formats
 * Supports: DD/MM/YYYY, D/M/YYYY, YYYY-MM-DD, DD-MM-YYYY, DDMMYYYY
 */
export const validateDate = (dateStr) => {
  if (!dateStr) return false;

  const trimmed = dateStr.trim();
  let normalized = trimmed;

  // Accept datetime values by extracting the date component.
  // Examples: 2025-12-25T10:30:00Z, 2025-12-25 10:30:00, 25/12/2025 10:30:00
  if (/^\d{4}-\d{1,2}-\d{1,2}[T\s].+$/.test(normalized)) {
    normalized = normalized.split(/[T\s]/)[0];
  } else if (/^\d{1,2}\/\d{1,2}\/\d{4}\s.+$/.test(normalized)) {
    normalized = normalized.split(/\s+/)[0];
  } else if (/^\d{1,2}-\d{1,2}-\d{4}\s.+$/.test(normalized)) {
    normalized = normalized.split(/\s+/)[0];
  }

  let day, month, year, parsedDate;

  // Try to parse different formats - support flexible day/month (1 or 2 digits)
  if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(normalized)) {
    // D/M/YYYY or DD/MM/YYYY
    const parts = normalized.split('/');
    day = parseInt(parts[0]);
    month = parseInt(parts[1]);
    year = parseInt(parts[2]);
  } else if (/^\d{4}-\d{1,2}-\d{1,2}$/.test(normalized)) {
    // YYYY-M-D or YYYY-MM-DD
    const parts = normalized.split('-');
    year = parseInt(parts[0]);
    month = parseInt(parts[1]);
    day = parseInt(parts[2]);
  } else if (/^\d{1,2}-\d{1,2}-\d{4}$/.test(normalized)) {
    // D-M-YYYY or DD-MM-YYYY
    const parts = normalized.split('-');
    day = parseInt(parts[0]);
    month = parseInt(parts[1]);
    year = parseInt(parts[2]);
  } else if (/^\d{8}$/.test(normalized)) {
    // DDMMYYYY
    day = parseInt(normalized.substring(0, 2));
    month = parseInt(normalized.substring(2, 4));
    year = parseInt(normalized.substring(4, 8));
  } else {
    return false;
  }

  // Validate month and day ranges
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return false;
  }

  // Create date and check if it's valid (will adjust if invalid day for month)
  parsedDate = new Date(year, month - 1, day);

  // Check if the date is valid by verifying the day wasn't rolled over to next month
  if (parsedDate.getDate() !== day || parsedDate.getMonth() !== month - 1 || parsedDate.getFullYear() !== year) {
    return false;
  }

  // Check if date is not in the future
  const today = new Date();
  today.setHours(23, 59, 59, 999); // Set to end of today

  return parsedDate <= today;
};

/**
 * Validate amount - must be positive number
 */
export const validateAmount = (amount) => {
  // First check if it's a valid number (no partial numeric strings like "100abc")
  if (typeof amount === 'string' && !/^-?\d+(\.\d+)?$/.test(amount.trim())) {
    return false;
  }
  const num = parseFloat(amount);
  return !isNaN(num) && isFinite(num) && num > 0;
};

/**
 * Validate required field is not empty
 */
export const validateRequired = (value) => {
  // Special case: 0 is a valid value for numeric fields
  if (value === 0) return true;
  // Empty string, null, undefined, or whitespace only = invalid
  if (value === '' || value === null || value === undefined) return false;
  if (typeof value === 'string' && value.trim().length === 0) return false;
  return true;
};

/**
 * Validate numeric value
 */
export const validateNumeric = (value) => {
  // First check if it's a valid number (no partial numeric strings like "100abc")
  if (typeof value === 'string' && !/^-?\d+(\.\d+)?$/.test(value.trim())) {
    return false;
  }
  const num = parseFloat(value);
  return !isNaN(num) && isFinite(num);
};

/**
 * Validate number is within range
 */
export const validateRange = (value, min, max) => {
  const num = parseFloat(value);
  return !isNaN(num) && num >= min && num <= max;
};

/**
 * Build error object for a single cell
 */
export const buildCellError = (row, column, message) => ({
  row,
  column,
  error: message,
});

/**
 * Filter unique errors and return count
 */
export const getUniqueErrors = (errors) => {
  const uniqueErrors = {};
  errors.forEach((error) => {
    const key = `${error.row}-${error.column}`;
    if (!uniqueErrors[key]) {
      uniqueErrors[key] = error;
    }
  });
  return Object.values(uniqueErrors);
};
