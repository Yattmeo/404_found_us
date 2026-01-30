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

/**
 * Validate amount - must be positive number
 */
export const validateAmount = (amount) => {
  const num = parseFloat(amount);
  return !isNaN(num) && isFinite(num) && num > 0;
};

/**
 * Validate required field is not empty
 */
export const validateRequired = (value) => {
  return value && String(value).trim().length > 0;
};

/**
 * Validate numeric value
 */
export const validateNumeric = (value) => {
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
