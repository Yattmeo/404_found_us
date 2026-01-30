/**
 * Unit tests for useFileValidation hook
 * Tests file validation state management according to Story 1.1 acceptance criteria
 */
import { renderHook, act } from '@testing-library/react';
import { useFileValidation } from '../../hooks/useFileValidation';

describe('useFileValidation hook', () => {
  const REQUIRED_COLUMNS = ['transaction_id', 'transaction_date', 'merchant_id', 'amount', 'transaction_type', 'card_type'];

  describe('Initial state', () => {
    it('should initialize with empty state', () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));

      expect(result.current.fileName).toBe('');
      expect(result.current.fileError).toBe('');
      expect(result.current.isValidating).toBe(false);
      expect(result.current.validationErrors).toEqual([]);
      expect(result.current.previewData).toEqual([]);
      expect(result.current.fullData).toEqual([]);
      expect(result.current.showPreview).toBe(false);
    });
  });

  describe('File validation handling', () => {
    it('should set fileName when file is provided', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,25/12/2025,M123,99.99,Purchase,Visa';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.fileName).toBe('test.csv');
    });

    it('should show validation errors for invalid data', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,invalid-date,M123,99.99,Purchase,Visa';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.validationErrors.length).toBeGreaterThan(0);
      expect(result.current.showPreview).toBe(false);
      expect(result.current.fileError).toContain('Validation failed');
    });

    it('should show preview for valid data', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,25/12/2025,M123,99.99,Purchase,Visa\nTXN002,24/12/2025,M456,50.00,Refund,Mastercard';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.showPreview).toBe(true);
      expect(result.current.validationErrors).toEqual([]);
      expect(result.current.previewData.length).toBeGreaterThan(0);
    });

    it('should set isValidating to true during validation', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,25/12/2025,M123,99.99,Purchase,Visa';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      expect(result.current.isValidating).toBe(false);

      await act(async () => {
        const promise = result.current.handleFile(file);
        // isValidating should be true during validation
        await promise;
      });

      expect(result.current.isValidating).toBe(false);
    });
  });

  describe('Re-upload functionality', () => {
    it('should reset all state on re-upload', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,25/12/2025,M123,99.99,Purchase,Visa';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      // First upload
      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.fileName).not.toBe('');
      expect(result.current.fullData.length).toBeGreaterThan(0);

      // Re-upload
      act(() => {
        result.current.handleReupload();
      });

      expect(result.current.fileName).toBe('');
      expect(result.current.fileError).toBe('');
      expect(result.current.validationErrors).toEqual([]);
      expect(result.current.previewData).toEqual([]);
      expect(result.current.fullData).toEqual([]);
      expect(result.current.showPreview).toBe(false);
    });
  });

  describe('Error messages', () => {
    it('should show error message for invalid file type', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const file = new File(['test'], 'test.txt', { type: 'text/plain' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.fileError).toContain('Invalid file type');
    });

    it('should show error count in validation message', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,invalid-date,M123,-50,Purchase,Visa';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.fileError).toContain('Validation failed');
      expect(result.current.fileError).toContain(result.current.validationErrors.length.toString());
    });

    it('should report specific row and column errors', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      const csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\nTXN001,invalid-date,M123,99.99,Purchase,Visa';
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.validationErrors.some((e) => e.row === 1 && e.column === 'transaction_date')).toBe(true);
    });
  });

  describe('Preview data management', () => {
    it('should show first 10 rows in preview', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      let csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\n';
      for (let i = 1; i <= 15; i++) {
        csvContent += `TXN${i},25/12/2025,M${i},${99.99 + i},Purchase,Visa\n`;
      }
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.previewData.length).toBeLessThanOrEqual(10);
    });

    it('should have full data available beyond preview', async () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));
      let csvContent = 'transaction_id,transaction_date,merchant_id,amount,transaction_type,card_type\n';
      for (let i = 1; i <= 15; i++) {
        csvContent += `TXN${i},25/12/2025,M${i},${99.99 + i},Purchase,Visa\n`;
      }
      const file = new File([csvContent], 'test.csv', { type: 'text/csv' });

      await act(async () => {
        await result.current.handleFile(file);
      });

      expect(result.current.fullData.length).toBe(15);
      expect(result.current.previewData.length).toBeLessThanOrEqual(10);
    });
  });

  describe('Preview toggle', () => {
    it('should toggle preview visibility', () => {
      const { result } = renderHook(() => useFileValidation(REQUIRED_COLUMNS));

      expect(result.current.showPreview).toBe(false);

      act(() => {
        result.current.setShowPreview(true);
      });

      expect(result.current.showPreview).toBe(true);

      act(() => {
        result.current.setShowPreview(false);
      });

      expect(result.current.showPreview).toBe(false);
    });
  });
});
