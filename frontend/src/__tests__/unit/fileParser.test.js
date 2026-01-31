/**
 * Unit tests for fileParser.js (updated for new schema)
 * Tests CSV/Excel parsing and validation according to latest acceptance criteria
 */
import { validateFileStructure } from '../../utils/fileParser';

describe('fileParser.js', () => {
  const REQUIRED_COLUMNS = [
    'transaction_id',
    'transaction_date',
    'card_brand',
    'merchant_id',
    'amount',
    'transaction_type',
    'card_type',
  ];
  const VALID_HEADERS = 'transaction_id,transaction_date,card_brand,merchant_id,amount,transaction_type,card_type';

  describe('Header validation', () => {
    it('should accept valid headers with all required columns', () => {
      const data = [VALID_HEADERS];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(true);
    });
    it('should accept headers regardless of case', () => {
      const data = ['TRANSACTION_ID,Transaction_Date,CARD_BRAND,Merchant_ID,Amount,Transaction_Type,Card_Type'];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(true);
    });
    it('should reject missing required columns', () => {
      const data = ['transaction_id,transaction_date,merchant_id,amount,transaction_type'];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors[0].column).toContain('card_type');
      expect(result.errors[0].column).toContain('card_brand');
    });
    it('should report multiple missing columns', () => {
      const data = ['transaction_id,merchant_id,amount'];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors[0].column).toContain('transaction_date');
      expect(result.errors[0].column).toContain('transaction_type');
      expect(result.errors[0].column).toContain('card_type');
      expect(result.errors[0].column).toContain('card_brand');
    });
    it('should reject empty file', () => {
      const result = validateFileStructure([], REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors[0].error).toContain('empty');
    });
  });

  describe('Data row validation', () => {
    it('should accept valid data rows', () => {
      const data = [
        VALID_HEADERS,
        '1234567,25/12/2025,Visa,654321,99.99,Online,Debit',
        '2345678,24/12/2025,Mastercard,123456,50.00,Offline,Credit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(true);
      expect(result.data).toHaveLength(2);
    });
    it('should reject rows with empty required fields', () => {
      const data = [
        VALID_HEADERS,
        '1234567,,Visa,654321,99.99,Online,Debit', // Missing transaction_date
        '2345678,24/12/2025,Mastercard,123456,50.00,Offline,Credit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.row === 1 && e.column === 'transaction_date')).toBe(true);
    });
    it('should reject rows with invalid date format', () => {
      const data = [VALID_HEADERS, '1234567,invalid-date,Visa,654321,99.99,Online,Debit'];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors[0].column).toBe('transaction_date');
      expect(result.errors[0].error).toContain('Invalid date');
    });
    it('should reject rows with future dates', () => {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const futureDate = `${tomorrow.getDate()}/${tomorrow.getMonth() + 1}/${tomorrow.getFullYear()}`;
      const data = [VALID_HEADERS, `1234567,${futureDate},Visa,654321,99.99,Online,Debit`];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors[0].column).toBe('transaction_date');
    });
    it('should reject rows with invalid amount (non-numeric)', () => {
      const data = [VALID_HEADERS, '1234567,25/12/2025,Visa,654321,not-a-number,Online,Debit'];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors[0].column).toBe('amount');
    });
    it('should reject rows with zero or negative amounts', () => {
      const data = [
        VALID_HEADERS,
        '1234567,25/12/2025,Visa,654321,0,Online,Debit',
        '2345678,25/12/2025,Mastercard,123456,-50.00,Offline,Credit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.column === 'amount')).toBe(true);
    });
    it('should report specific row and column for each error', () => {
      const data = [
        VALID_HEADERS,
        '1234567,,Visa,654321,99.99,Online,Debit', // Row 1: missing date
        '2345678,24/12/2025,Mastercard,123456,-50.00,Offline,Credit', // Row 2: negative amount
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.errors.some((e) => e.row === 1 && e.column === 'transaction_date')).toBe(true);
      expect(result.errors.some((e) => e.row === 2 && e.column === 'amount')).toBe(true);
    });
  });

  describe('Duplicate transaction_id detection', () => {
    it('should reject duplicate transaction_ids', () => {
      const data = [
        VALID_HEADERS,
        '1234567,25/12/2025,Visa,654321,99.99,Online,Debit',
        '1234567,24/12/2025,Mastercard,123456,50.00,Offline,Credit', // Duplicate 1234567
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.column === 'transaction_id' && e.error.includes('Duplicate'))).toBe(true);
    });
    it('should allow unique transaction_ids', () => {
      const data = [
        VALID_HEADERS,
        '1234567,25/12/2025,Visa,654321,99.99,Online,Debit',
        '2345678,24/12/2025,Mastercard,123456,50.00,Offline,Credit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(true);
    });
  });

  describe('Preview data handling', () => {
    it('should parse valid data correctly', () => {
      const data = [
        VALID_HEADERS,
        '1234567,25/12/2025,Visa,654321,99.99,Online,Debit',
        '2345678,24/12/2025,Mastercard,123456,50.00,Offline,Credit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.data[0].transaction_id).toBe('1234567');
      expect(result.data[0].amount).toBe('99.99');
      expect(result.data[1].transaction_id).toBe('2345678');
    });
    it('should preserve data order', () => {
      const data = [
        VALID_HEADERS,
        '3456789,25/12/2025,Visa,654321,99.99,Online,Debit',
        '1234567,24/12/2025,Mastercard,123456,50.00,Offline,Credit',
        '2345678,23/12/2025,Visa,654321,75.50,Online,Debit (Prepaid)',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.data[0].transaction_id).toBe('3456789');
      expect(result.data[1].transaction_id).toBe('1234567');
      expect(result.data[2].transaction_id).toBe('2345678');
    });
  });

  describe('Edge cases', () => {
    it('should handle whitespace in headers', () => {
      const data = [
        ' transaction_id , transaction_date , card_brand , merchant_id , amount , transaction_type , card_type ',
        '1234567,25/12/2025,Visa,654321,99.99,Online,Debit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(true);
    });
    it('should handle whitespace in data values', () => {
      const data = [
        VALID_HEADERS,
        ' 1234567 , 25/12/2025 , Visa , 654321 , 99.99 , Online , Debit ',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.data[0].transaction_id).toBe('1234567');
    });
    it('should handle array input format (from Excel)', () => {
      const data = [
        ['transaction_id', 'transaction_date', 'card_brand', 'merchant_id', 'amount', 'transaction_type', 'card_type'],
        ['1234567', '25/12/2025', 'Visa', '654321', '99.99', 'Online', 'Debit'],
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(true);
    });
    it('should skip empty rows', () => {
      const data = [
        VALID_HEADERS,
        '1234567,25/12/2025,Visa,654321,99.99,Online,Debit',
        '',
        '2345678,24/12/2025,Mastercard,123456,50.00,Offline,Credit',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.data.length).toBeGreaterThan(0);
    });
    it('should reject invalid card_brand, transaction_type, card_type, transaction_id, merchant_id', () => {
      const data = [
        VALID_HEADERS,
        'abcdefg,25/12/2025,Amex,12345,99.99,InvalidType,InvalidCard',
      ];
      const result = validateFileStructure(data, REQUIRED_COLUMNS);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.column === 'card_brand')).toBe(true);
      expect(result.errors.some((e) => e.column === 'transaction_type')).toBe(true);
      expect(result.errors.some((e) => e.column === 'card_type')).toBe(true);
      expect(result.errors.some((e) => e.column === 'transaction_id')).toBe(true);
      expect(result.errors.some((e) => e.column === 'merchant_id')).toBe(true);
    });
  });
});
