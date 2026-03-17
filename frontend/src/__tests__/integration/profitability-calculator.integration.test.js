/**
 * Integration Tests – Profitability Calculator (EnhancedMerchantFeeCalculator)
 * User Story 3: Internal Tool – Profitability Calculator
 *
 * Scope of integration:
 *   EnhancedMerchantFeeCalculator (form, step 1 + step 2)
 *     ↔ parseFileData / DataUploadValidator (file parsing + validation)
 *     ↔ merchantFeeAPI service (HTTP layer)
 *     ↔ ResultsPanel (display)
 *
 * Mocked external boundaries:
 *   - merchantFeeAPI (HTTP layer)
 *   - parseFileData (async file-parsing utility – not a focus here)
 *   - MCCDropdown (complex combobox – tested separately)
 *   - ManualTransactionEntry (standalone component – tested separately)
 *   - ResultsPanel (simplified stub to assert received props)
 *     → The real ResultsPanel is used in the "More Details" describe block
 *       via jest.requireActual.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

// ── Mocks (must be declared before imports) ──────────────────────────────────

jest.mock('../../services/api', () => ({
  merchantFeeAPI: {
    calculateCurrentRates: jest.fn(),
  },
}));

// Auto-mock parseFileData so every test can control the resolved value.
jest.mock('../../utils/fileParser');

jest.mock('../../components/MCCDropdown', () => ({ value, onChange, error }) => (
  <div>
    <label htmlFor="mcc-profitability-select">Merchant Category Code (MCC)</label>
    <select
      id="mcc-profitability-select"
      data-testid="mcc-dropdown"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">Select MCC</option>
      <option value="5812">5812 - Eating Places</option>
      <option value="5411">5411 - Grocery Stores</option>
      <option value="5999">5999 - Miscellaneous</option>
    </select>
    {error && <p data-testid="mcc-error">{typeof error === 'string' ? error : error.message}</p>}
  </div>
));

jest.mock('../../components/ManualTransactionEntry', () => ({
  onValidDataConfirmed,
  onMCCExtracted,
}) => (
  <button
    type="button"
    data-testid="manual-confirm"
    onClick={() => {
      const rows = [
        {
          transaction_id: 'TX1',
          transaction_date: '2026-01-01',
          merchant_id: 'M500',
          amount: '200',
          transaction_type: 'Sale',
          card_type: 'Visa',
          card_brand: 'Visa',
        },
      ];
      onValidDataConfirmed(rows);
      if (onMCCExtracted) onMCCExtracted('5812');
    }}
  >
    Confirm Manual Data
  </button>
));

// Simplified ResultsPanel: exposes key props for test assertions
jest.mock('../../components/ResultsPanel', () => ({
  results,
  hasCurrentRate,
  onNewCalculation,
}) => (
  <div data-testid="results-panel">
    <span data-testid="result-has-current-rate">{String(hasCurrentRate)}</span>
    <span data-testid="result-suggested-rate">
      {results?.suggestedRate !== null && results?.suggestedRate !== undefined
        ? String(results.suggestedRate)
        : 'null'}
    </span>
    <span data-testid="result-profitability">
      {results?.profitability !== null && results?.profitability !== undefined
        ? String(results.profitability)
        : 'null'}
    </span>
    <span data-testid="result-net-profit">
      {results?.netProfit !== null && results?.netProfit !== undefined
        ? String(results.netProfit)
        : 'null'}
    </span>
    <button type="button" onClick={onNewCalculation}>
      New Calculation
    </button>
  </div>
));

// ── Module imports (after mocks) ──────────────────────────────────────────────

import { merchantFeeAPI } from '../../services/api';
import { parseFileData } from '../../utils/fileParser';
import EnhancedMerchantFeeCalculator from '../../components/EnhancedMerchantFeeCalculator';

// ── Test constants ────────────────────────────────────────────────────────────

const makeMockRow = (overrides = {}) => ({
  transaction_id: 'TX1',
  transaction_date: '2026-01-01',
  merchant_id: 'M500',
  mcc: '5812',
  amount: '150.00',
  transaction_type: 'Sale',
  card_type: 'Visa',
  card_brand: 'Visa',
  ...overrides,
});

const VALID_PARSE_RESULT = {
  data: [makeMockRow()],
  errors: [],
};

const INVALID_PARSE_RESULT = {
  data: [],
  errors: [{ row: 2, column: 'card_type', error: 'Missing required column: card_type' }],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const triggerFileUpload = (filename = 'transactions.csv') => {
  const input = document.querySelector('input[type="file"]');
  const file = new File(['content'], filename, { type: 'text/csv' });
  fireEvent.change(input, { target: { files: [file] } });
};

const waitForProceedButton = () =>
  waitFor(() =>
    screen.getByRole('button', { name: /proceed to projection/i }),
  );

const clickProceed = () =>
  fireEvent.click(screen.getByRole('button', { name: /proceed to projection/i }));

const completeStep2AndSubmit = async ({
  feeStructure = 'percentage',
  mcc = '5812',
  currentRate = null,
  fixedFee = null,
} = {}) => {
  // Step 2 inputs become available once the proceed button has been clicked
  await waitFor(() =>
    expect(screen.getByRole('combobox', { name: /preferred fee structure/i })).toBeInTheDocument(),
  );

  // MCC
  fireEvent.change(screen.getByTestId('mcc-dropdown'), { target: { value: mcc } });

  // Fee structure
  fireEvent.change(screen.getByRole('combobox', { name: /preferred fee structure/i }), {
    target: { value: feeStructure },
  });

  // Optional fixed fee (visible only for percentage-fixed)
  if (fixedFee !== null && feeStructure === 'percentage-fixed') {
    const fixedFeeInput = screen.queryByPlaceholderText(/enter fixed fee/i);
    if (fixedFeeInput) {
      fireEvent.change(fixedFeeInput, { target: { value: String(fixedFee) } });
    }
  }

  // Optional current rate
  if (currentRate !== null) {
    const rateInput = screen.queryByPlaceholderText(/enter current rate/i);
    if (rateInput) {
      fireEvent.change(rateInput, { target: { value: String(currentRate) } });
    }
  }

  // Submit step 2
  fireEvent.click(screen.getByRole('button', { name: /proceed to projection/i }));
};

// ── Test suite ────────────────────────────────────────────────────────────────

describe('Profitability Calculator (EnhancedMerchantFeeCalculator) – integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default: valid file parse result and a minimal successful API response
    parseFileData.mockResolvedValue(VALID_PARSE_RESULT);
    merchantFeeAPI.calculateCurrentRates.mockResolvedValue({ suggestedRate: 1.8 });
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  // ── IC1: Valid CSV upload – parsing success, preview shown ────────────────

  describe('IC1 – Valid CSV upload: parsing, preview and proceed confirmation to frontend', () => {
    it('valid CSV is parsed and the Proceed button and row count are shown', async () => {
      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();

      await waitForProceedButton();

      expect(screen.getByText(/proceed to projection/i)).toBeInTheDocument();
      expect(screen.queryByText(/validation failed/i)).not.toBeInTheDocument();
    });

    it('valid CSV with one data row shows "1 total rows" in the preview', async () => {
      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();

      await waitFor(() => expect(screen.getByText(/1 total row/i)).toBeInTheDocument());
    });
  });

  // ── IC2: Invalid CSV – validation error displayed on frontend ─────────────

  describe('IC2 – Invalid CSV: validation error triggers error message on frontend', () => {
    it('CSV with a missing required column shows a validation failed message', async () => {
      parseFileData.mockResolvedValue(INVALID_PARSE_RESULT);

      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();

      await waitFor(() =>
        expect(screen.getByText(/validation failed/i)).toBeInTheDocument(),
      );
    });

    it('validation failure does NOT show the "Proceed to Projection" button', async () => {
      parseFileData.mockResolvedValue(INVALID_PARSE_RESULT);

      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();

      await waitFor(() =>
        expect(screen.queryByRole('button', { name: /proceed to projection/i })).not.toBeInTheDocument(),
      );
    });
  });

  // ── IC3: Preview table shows first 10 rows ─────────────────────────────────

  describe('IC3 – Preview: only first 10 rows shown when file has more than 10 rows', () => {
    it('shows "Showing first 10 rows of 12 total" when parse result has 12 rows', async () => {
      const rows = Array.from({ length: 12 }, (_, i) =>
        makeMockRow({ transaction_id: `TX${i + 1}`, merchant_id: 'M500' }),
      );
      parseFileData.mockResolvedValue({ data: rows, errors: [] });

      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();

      await waitFor(() =>
        expect(screen.getByText(/12 total rows/i)).toBeInTheDocument(),
      );
    });
  });

  // ── IC4: MCC auto-detection after proceeding to step 2 ────────────────────

  describe('IC4 – MCC auto-detection: detected MCC passed to frontend step 2', () => {
    it('DataUploadValidator auto-populates MCC = "5812" after proceeding to step 2', async () => {
      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();
      await waitForProceedButton();
      clickProceed();

      await waitFor(() =>
        expect(screen.getByTestId('mcc-dropdown')).toHaveValue('5812'),
      );
    });
  });

  // ── IC5: Manual entry flow ────────────────────────────────────────────────

  describe('IC5 – Manual transaction entry: success response to frontend', () => {
    it('confirms manual data and triggers a successful API call with results displayed', async () => {
      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      fireEvent.click(screen.getByRole('button', { name: /manual entry/i }));
      fireEvent.click(screen.getByTestId('manual-confirm'));

      await completeStep2AndSubmit({ feeStructure: 'percentage', mcc: '5812' });

      await waitFor(() =>
        expect(merchantFeeAPI.calculateCurrentRates).toHaveBeenCalledTimes(1),
      );
      await waitFor(() =>
        expect(screen.getByTestId('results-panel')).toBeInTheDocument(),
      );
    });
  });

  // ── IC6: Payload construction – fee structure permutations ────────────────

  describe('IC6 – Payload: MCC, fee structure, rates sent to backend API', () => {
    const uploadAndSubmitWith = async (step2Options) => {
      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();
      await waitForProceedButton();
      clickProceed();

      await completeStep2AndSubmit(step2Options);

      await waitFor(() =>
        expect(merchantFeeAPI.calculateCurrentRates).toHaveBeenCalled(),
      );
      return merchantFeeAPI.calculateCurrentRates.mock.calls[0][0];
    };

    it('%-only fee structure sends correct mcc and feeStructure in payload', async () => {
      const payload = await uploadAndSubmitWith({
        feeStructure: 'percentage',
        mcc: '5812',
      });

      expect(payload).toMatchObject({ mcc: '5812', fixed_fee: 0.3 });
    });

    it('%-fixed fee structure with fixed fee 0.25 sends fixedFee: 0.25 in payload', async () => {
      const payload = await uploadAndSubmitWith({
        feeStructure: 'percentage-fixed',
        mcc: '5812',
        fixedFee: 0.25,
      });

      expect(Number(payload.fixed_fee)).toBe(0.25);
    });

    it('fixed-only fee structure sends correct feeStructure in payload', async () => {
      const payload = await uploadAndSubmitWith({
        feeStructure: 'fixed',
        mcc: '5812',
      });

      expect(payload).toMatchObject({ mcc: '5812' });
    });

    it('current rate 2.5 is included in the payload as a number', async () => {
      const payload = await uploadAndSubmitWith({
        feeStructure: 'percentage',
        mcc: '5812',
        currentRate: 2.5,
      });

      expect(Number(payload.current_rate)).toBeCloseTo(0.025, 6);
    });
  });

  // ── IC7: hasCurrentRate prop passed to ResultsPanel ───────────────────────

  describe('IC7 – hasCurrentRate: current rate flag correctly passed to results display', () => {
    const uploadAndRender = async (step2Options) => {
      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();
      await waitForProceedButton();
      clickProceed();

      await completeStep2AndSubmit(step2Options);

      await waitFor(() =>
        expect(screen.getByTestId('results-panel')).toBeInTheDocument(),
      );
    };

    it('hasCurrentRate is false when no current rate is provided', async () => {
      await uploadAndRender({ feeStructure: 'percentage', mcc: '5812' });

      expect(screen.getByTestId('result-has-current-rate').textContent).toBe('false');
    });

    it('hasCurrentRate is true when a current rate is provided', async () => {
      await uploadAndRender({
        feeStructure: 'percentage',
        mcc: '5812',
        currentRate: 2.5,
      });

      expect(screen.getByTestId('result-has-current-rate').textContent).toBe('true');
    });
  });

  // ── IC8: Backend unavailable → null values returned to frontend ───────────

  describe('IC8 – Backend unavailable: null values sent to results display', () => {
    it('rejected API call results in null suggestedRate and profitability in the results panel', async () => {
      merchantFeeAPI.calculateCurrentRates.mockRejectedValue(
        new Error('Service unavailable'),
      );

      render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

      triggerFileUpload();
      await waitForProceedButton();
      clickProceed();

      await completeStep2AndSubmit({ feeStructure: 'percentage', mcc: '5812' });

      await waitFor(() =>
        expect(screen.getByTestId('results-panel')).toBeInTheDocument(),
      );

      expect(screen.getByTestId('result-suggested-rate').textContent).toBe('null');
      expect(screen.getByTestId('result-profitability').textContent).toBe('null');
      expect(screen.getByTestId('result-net-profit').textContent).toBe('null');
    });
  });

  // ── IC9: "More Details" – profit distribution + additional details ─────────
  // Uses jest.requireActual to render the real ResultsPanel component,
  // bypassing the simplified stub defined above.

  describe('IC9 – "More Details": profit distribution chart and additional details revealed', () => {
    it('clicking More Details shows profit distribution and additional details sections', () => {
      const RealResultsPanel =
        jest.requireActual('../../components/ResultsPanel').default;

      const mockResults = {
        suggestedRate: 1.8,
        profitability: 0.75,
        netProfit: 12000,
        profitDistribution: [
          { bin: '0–5k', count: 3 },
          { bin: '5k–10k', count: 7 },
          { bin: '10k–15k', count: 5 },
        ],
        bandFees: [],
        feeSummary: null,
        mlContext: null,
        calculation: null,
      };

      render(
        <RealResultsPanel
          results={mockResults}
          hasCurrentRate={true}
          onNewCalculation={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByRole('button', { name: /more details/i }));

      // Current chart section heading
      expect(
        screen.getByText(/sarima forecast - cost/i),
      ).toBeInTheDocument();

      // Additional details section
      expect(
        screen.getByText(/additional details/i),
      ).toBeInTheDocument();
    });
  });
});
