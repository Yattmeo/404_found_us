/**
 * Unit tests for useTransactionValidation hook
 * Tests manual transaction entry validation according to Story 1.1 acceptance criteria
 */
import { renderHook, act } from '@testing-library/react';
import { useTransactionValidation } from '../../hooks/useTransactionValidation';

describe('useTransactionValidation hook', () => {
  describe('Initial state', () => {
    it('should initialize with one empty transaction', () => {
      const { result } = renderHook(() => useTransactionValidation());

      expect(result.current.transactions).toHaveLength(1);
      expect(result.current.transactions[0]).toEqual({
        transaction_id: '',
        transaction_date: '',
        merchant_id: '',
        amount: '',
        transaction_type: '',
        card_type: '',
      });
      expect(result.current.validationErrors).toEqual([]);
      expect(result.current.showPreview).toBe(false);
      expect(result.current.previewData).toEqual([]);
      expect(result.current.isValidating).toBe(false);
    });
  });

  describe('Transaction management', () => {
    it('should add a new row', () => {
      const { result } = renderHook(() => useTransactionValidation());

      expect(result.current.transactions).toHaveLength(1);

      act(() => {
        result.current.addTransaction();
      });

      expect(result.current.transactions).toHaveLength(2);
    });

    it('should not delete if only one row remains', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.removeTransaction(0);
      });

      expect(result.current.transactions).toHaveLength(1);
    });

    it('should delete a row when multiple rows exist', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.addTransaction();
      });
      act(() => {
        result.current.addTransaction();
      });

      expect(result.current.transactions).toHaveLength(3);

      act(() => {
        result.current.removeTransaction(1);
      });

      expect(result.current.transactions).toHaveLength(2);
    });

    it('should duplicate a row', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'amount', '99.99');
      });

      act(() => {
        result.current.duplicateTransaction(0);
      });

      expect(result.current.transactions).toHaveLength(2);
      expect(result.current.transactions[1].transaction_id).toBe('TXN001');
      expect(result.current.transactions[1].amount).toBe('99.99');
    });

    it('should update transaction field', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
      });

      expect(result.current.transactions[0].transaction_id).toBe('TXN001');
    });

    it('should clear all entries', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.addTransaction();
      });
      act(() => {
        result.current.addTransaction();
      });
      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(1, 'amount', '50.00');
      });

      expect(result.current.transactions).toHaveLength(3);

      act(() => {
        result.current.clearAllEntries();
      });

      expect(result.current.transactions).toHaveLength(1);
      expect(result.current.transactions[0].transaction_id).toBe('');
      expect(result.current.validationErrors).toEqual([]);
    });
  });

  describe('Validation - Required fields', () => {
    it('should reject empty transaction_id', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_id')).toBe(true);
      expect(result.current.showPreview).toBe(false);
    });

    it('should reject empty transaction_date', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_date')).toBe(true);
    });

    it('should reject empty merchant_id', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'merchant_id')).toBe(true);
    });

    it('should reject empty amount', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'amount')).toBe(true);
    });

    it('should reject empty transaction_type', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'card_type', 'Visa');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_type')).toBe(true);
    });

    it('should reject empty card_type', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'card_type')).toBe(true);
    });
  });

  describe('Validation - Date formats', () => {
    const validTransaction = {
      transaction_id: 'TXN001',
      merchant_id: 'M123',
      amount: '99.99',
      transaction_type: 'Purchase',
      card_type: 'Visa',
    };

    it('should accept DD/MM/YYYY date format', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_date')).toBe(false);
      expect(result.current.showPreview).toBe(true);
    });

    it('should accept YYYY-MM-DD date format', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'transaction_date', '2025-12-25');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_date')).toBe(false);
      expect(result.current.showPreview).toBe(true);
    });

    it('should reject invalid date format', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'transaction_date', 'invalid-date');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_date')).toBe(true);
    });

    it('should reject future dates', () => {
      const { result } = renderHook(() => useTransactionValidation());
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const futureDate = `${tomorrow.getDate()}/${tomorrow.getMonth() + 1}/${tomorrow.getFullYear()}`;

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'transaction_date', futureDate);
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_date')).toBe(true);
    });
  });

  describe('Validation - Amount', () => {
    const validTransaction = {
      transaction_id: 'TXN001',
      transaction_date: '25/12/2025',
      merchant_id: 'M123',
      transaction_type: 'Purchase',
      card_type: 'Visa',
    };

    it('should accept positive numeric amount', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'amount')).toBe(false);
      expect(result.current.showPreview).toBe(true);
    });

    it('should reject non-numeric amount', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'amount', 'not-a-number');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'amount')).toBe(true);
    });

    it('should reject zero amount', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'amount', '0');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'amount')).toBe(true);
    });

    it('should reject negative amount', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        Object.entries(validTransaction).forEach(([key, value]) => {
          result.current.updateTransaction(0, key, value);
        });
        result.current.updateTransaction(0, 'amount', '-50.00');
        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'amount')).toBe(true);
    });
  });

  describe('Validation - Duplicate transaction_id', () => {
    it('should reject duplicate transaction_ids', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.addTransaction();
      });

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');

        result.current.updateTransaction(1, 'transaction_id', 'TXN001'); // Duplicate
        result.current.updateTransaction(1, 'transaction_date', '24/12/2025');
        result.current.updateTransaction(1, 'merchant_id', 'M456');
        result.current.updateTransaction(1, 'amount', '50.00');
        result.current.updateTransaction(1, 'transaction_type', 'Refund');
        result.current.updateTransaction(1, 'card_type', 'Mastercard');

        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.column === 'transaction_id' && e.error.includes('Duplicate'))).toBe(true);
      expect(result.current.showPreview).toBe(false);
    });

    it('should allow unique transaction_ids', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.addTransaction();
      });

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');

        result.current.updateTransaction(1, 'transaction_id', 'TXN002'); // Unique
        result.current.updateTransaction(1, 'transaction_date', '24/12/2025');
        result.current.updateTransaction(1, 'merchant_id', 'M456');
        result.current.updateTransaction(1, 'amount', '50.00');
        result.current.updateTransaction(1, 'transaction_type', 'Refund');
        result.current.updateTransaction(1, 'card_type', 'Mastercard');

        result.current.validateAndPreview();
      });

      expect(result.current.showPreview).toBe(true);
      expect(result.current.validationErrors.length).toBe(0);
    });
  });

  describe('Error reporting', () => {
    it('should report specific row numbers for errors', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.addTransaction();
      });

      act(() => {
        // Row 1 with missing date
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');

        // Row 2 with invalid amount
        result.current.updateTransaction(1, 'transaction_id', 'TXN002');
        result.current.updateTransaction(1, 'transaction_date', '24/12/2025');
        result.current.updateTransaction(1, 'merchant_id', 'M456');
        result.current.updateTransaction(1, 'amount', 'invalid');
        result.current.updateTransaction(1, 'transaction_type', 'Refund');
        result.current.updateTransaction(1, 'card_type', 'Mastercard');

        result.current.validateAndPreview();
      });

      expect(result.current.validationErrors.some((e) => e.row === 1)).toBe(true);
      expect(result.current.validationErrors.some((e) => e.row === 2)).toBe(true);
    });
  });

  describe('Preview functionality', () => {
    it('should show preview for valid transactions', () => {
      const { result } = renderHook(() => useTransactionValidation());

      act(() => {
        result.current.updateTransaction(0, 'transaction_id', 'TXN001');
        result.current.updateTransaction(0, 'transaction_date', '25/12/2025');
        result.current.updateTransaction(0, 'merchant_id', 'M123');
        result.current.updateTransaction(0, 'amount', '99.99');
        result.current.updateTransaction(0, 'transaction_type', 'Purchase');
        result.current.updateTransaction(0, 'card_type', 'Visa');
        result.current.validateAndPreview();
      });

      expect(result.current.showPreview).toBe(true);
      expect(result.current.previewData).toHaveLength(1);
      expect(result.current.previewData[0].transaction_id).toBe('TXN001');
    });

    it('should toggle preview visibility', () => {
      const { result } = renderHook(() => useTransactionValidation());

      expect(result.current.showPreview).toBe(false);

      act(() => {
        result.current.setShowPreview(true);
      });

      expect(result.current.showPreview).toBe(true);
    });
  });
});
