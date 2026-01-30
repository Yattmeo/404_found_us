/**
 * Unit tests for validators.js
 * Tests all validation functions according to Story 1.1 acceptance criteria
 */
import {
  validateDate,
  validateAmount,
  validateRequired,
  validateNumeric,
  validateRange,
  buildCellError,
  getUniqueErrors,
} from '../../src/utils/validators';

describe('validators.js', () => {
  describe('validateDate', () => {
    describe('Valid dates', () => {
      it('should accept DD/MM/YYYY format', () => {
        expect(validateDate('25/12/2025')).toBe(true);
      });

      it('should accept D/M/YYYY format with single digits', () => {
        expect(validateDate('5/1/2025')).toBe(true);
      });

      it('should accept YYYY-MM-DD format', () => {
        expect(validateDate('2025-12-25')).toBe(true);
      });

      it('should accept YYYY-M-D format with single digits', () => {
        expect(validateDate('2025-1-5')).toBe(true);
      });

      it('should accept DD-MM-YYYY format', () => {
        expect(validateDate('25-12-2025')).toBe(true);
      });

      it('should accept DDMMYYYY format', () => {
        expect(validateDate('25122025')).toBe(true);
      });

      it('should accept today date', () => {
        const today = new Date();
        const dateStr = `${today.getDate()}/${today.getMonth() + 1}/${today.getFullYear()}`;
        expect(validateDate(dateStr)).toBe(true);
      });
    });

    describe('Invalid dates', () => {
      it('should reject future dates', () => {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const dateStr = `${tomorrow.getDate()}/${tomorrow.getMonth() + 1}/${tomorrow.getFullYear()}`;
        expect(validateDate(dateStr)).toBe(false);
      });

      it('should reject invalid date formats', () => {
        expect(validateDate('2025/12/25')).toBe(false);
        expect(validateDate('12-25-2025')).toBe(false);
        expect(validateDate('not-a-date')).toBe(false);
      });

      it('should reject empty/whitespace strings', () => {
        expect(validateDate('')).toBe(false);
        expect(validateDate('   ')).toBe(false);
        expect(validateDate(null)).toBe(false);
      });

      it('should reject invalid dates (e.g., Feb 30)', () => {
        expect(validateDate('30/02/2025')).toBe(false);
      });

      it('should reject invalid month 13', () => {
        expect(validateDate('25/13/2025')).toBe(false);
      });

      it('should reject invalid day 32', () => {
        expect(validateDate('32/01/2025')).toBe(false);
      });
    });
  });

  describe('validateAmount', () => {
    describe('Valid amounts', () => {
      it('should accept positive integers', () => {
        expect(validateAmount('100')).toBe(true);
        expect(validateAmount('1')).toBe(true);
      });

      it('should accept positive decimals', () => {
        expect(validateAmount('99.99')).toBe(true);
        expect(validateAmount('0.01')).toBe(true);
      });

      it('should accept numbers without quotes', () => {
        expect(validateAmount(100)).toBe(true);
        expect(validateAmount(99.99)).toBe(true);
      });

      it('should accept large amounts', () => {
        expect(validateAmount('999999.99')).toBe(true);
      });
    });

    describe('Invalid amounts', () => {
      it('should reject zero', () => {
        expect(validateAmount('0')).toBe(false);
        expect(validateAmount(0)).toBe(false);
      });

      it('should reject negative amounts', () => {
        expect(validateAmount('-50')).toBe(false);
        expect(validateAmount(-50)).toBe(false);
      });

      it('should reject non-numeric values', () => {
        expect(validateAmount('abc')).toBe(false);
        expect(validateAmount('100abc')).toBe(false);
      });

      it('should reject empty strings', () => {
        expect(validateAmount('')).toBe(false);
      });

      it('should reject NaN', () => {
        expect(validateAmount(NaN)).toBe(false);
      });

      it('should reject Infinity', () => {
        expect(validateAmount(Infinity)).toBe(false);
      });
    });
  });

  describe('validateRequired', () => {
    describe('Valid required fields', () => {
      it('should accept non-empty strings', () => {
        expect(validateRequired('transaction_001')).toBe(true);
        expect(validateRequired('merchant_123')).toBe(true);
      });

      it('should accept numbers', () => {
        expect(validateRequired(123)).toBe(true);
        expect(validateRequired(0)).toBe(true);
      });

      it('should trim whitespace', () => {
        expect(validateRequired('  value  ')).toBe(true);
      });
    });

    describe('Invalid required fields', () => {
      it('should reject empty strings', () => {
        expect(validateRequired('')).toBe(false);
      });

      it('should reject whitespace only', () => {
        expect(validateRequired('   ')).toBe(false);
      });

      it('should reject null', () => {
        expect(validateRequired(null)).toBe(false);
      });

      it('should reject undefined', () => {
        expect(validateRequired(undefined)).toBe(false);
      });
    });
  });

  describe('validateNumeric', () => {
    describe('Valid numeric values', () => {
      it('should accept integers', () => {
        expect(validateNumeric('100')).toBe(true);
        expect(validateNumeric(100)).toBe(true);
      });

      it('should accept decimals', () => {
        expect(validateNumeric('99.99')).toBe(true);
        expect(validateNumeric(99.99)).toBe(true);
      });

      it('should accept negative numbers', () => {
        expect(validateNumeric('-50')).toBe(true);
        expect(validateNumeric(-50)).toBe(true);
      });

      it('should accept zero', () => {
        expect(validateNumeric('0')).toBe(true);
        expect(validateNumeric(0)).toBe(true);
      });
    });

    describe('Invalid numeric values', () => {
      it('should reject non-numeric strings', () => {
        expect(validateNumeric('abc')).toBe(false);
        expect(validateNumeric('100abc')).toBe(false);
      });

      it('should reject empty strings', () => {
        expect(validateNumeric('')).toBe(false);
      });

      it('should reject NaN', () => {
        expect(validateNumeric(NaN)).toBe(false);
      });

      it('should reject Infinity', () => {
        expect(validateNumeric(Infinity)).toBe(false);
      });
    });
  });

  describe('validateRange', () => {
    describe('Valid range values', () => {
      it('should accept values within range', () => {
        expect(validateRange('50', 0, 100)).toBe(true);
        expect(validateRange(50, 0, 100)).toBe(true);
      });

      it('should accept boundary values', () => {
        expect(validateRange('0', 0, 100)).toBe(true);
        expect(validateRange('100', 0, 100)).toBe(true);
      });

      it('should accept decimal values in range', () => {
        expect(validateRange('2.5', 0, 5)).toBe(true);
      });
    });

    describe('Invalid range values', () => {
      it('should reject values below min', () => {
        expect(validateRange('-1', 0, 100)).toBe(false);
      });

      it('should reject values above max', () => {
        expect(validateRange('101', 0, 100)).toBe(false);
      });

      it('should reject non-numeric values', () => {
        expect(validateRange('abc', 0, 100)).toBe(false);
      });
    });
  });

  describe('buildCellError', () => {
    it('should create error object with correct structure', () => {
      const error = buildCellError(5, 'transaction_date', 'Invalid date format');
      expect(error).toEqual({
        row: 5,
        column: 'transaction_date',
        error: 'Invalid date format',
      });
    });

    it('should handle different row and column values', () => {
      const error = buildCellError(1, 'amount', 'Amount must be positive');
      expect(error.row).toBe(1);
      expect(error.column).toBe('amount');
      expect(error.error).toBe('Amount must be positive');
    });
  });

  describe('getUniqueErrors', () => {
    it('should return all errors if no duplicates', () => {
      const errors = [
        { row: 1, column: 'date', error: 'Invalid date' },
        { row: 2, column: 'amount', error: 'Invalid amount' },
      ];
      const unique = getUniqueErrors(errors);
      expect(unique).toHaveLength(2);
    });

    it('should remove duplicate row-column errors', () => {
      const errors = [
        { row: 1, column: 'date', error: 'Invalid date' },
        { row: 1, column: 'date', error: 'Different error message' },
        { row: 2, column: 'amount', error: 'Invalid amount' },
      ];
      const unique = getUniqueErrors(errors);
      expect(unique).toHaveLength(2);
    });

    it('should handle empty error array', () => {
      const unique = getUniqueErrors([]);
      expect(unique).toHaveLength(0);
    });

    it('should preserve first occurrence of duplicate error', () => {
      const errors = [
        { row: 1, column: 'date', error: 'First error' },
        { row: 1, column: 'date', error: 'Second error' },
      ];
      const unique = getUniqueErrors(errors);
      expect(unique[0].error).toBe('First error');
    });
  });
});
