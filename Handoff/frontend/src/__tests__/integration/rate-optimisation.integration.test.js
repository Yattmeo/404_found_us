/**
 * Integration Tests – Rate Optimisation Tool (DesiredMarginCalculator)
 * User Story 2: Internal Tool – Rate Optimisation
 *
 * Scope of integration:
 *   DesiredMarginCalculator (form) ↔ desiredMarginAPI service ↔ DesiredMarginResults (display)
 *
 * Mocked external boundaries:
 *   - desiredMarginAPI (HTTP layer)
 *   - xlsx (browser file API – not available in jsdom)
 *   - MCCDropdown (complex combobox – not the focus of these tests)
 *   - ManualTransactionEntry (standalone component tested separately)
 *   - DesiredMarginResults (simplified stub to assert received props)
 *     → The real DesiredMarginResults is used in the "More Details" describe block
 *       via jest.requireActual.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// ── Mocks (must be declared before imports) ──────────────────────────────────

jest.mock('../../services/api', () => ({
  desiredMarginAPI: {
    getDesiredMarginDetails: jest.fn(),
  },
}));

jest.mock('xlsx', () => ({
  read: jest.fn(),
  utils: { sheet_to_json: jest.fn() },
}));

jest.mock('../../components/MCCDropdown', () => ({ value, onChange, error }) => (
  <div>
    <label htmlFor="mcc-test-select">Merchant Category Code (MCC)</label>
    <select
      id="mcc-test-select"
      data-testid="mcc-dropdown"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">Select MCC</option>
      <option value="5812">5812 - Eating Places</option>
      <option value="5411">5411 - Grocery Stores</option>
    </select>
    {error && <p data-testid="mcc-error">{typeof error === 'string' ? error : error.message}</p>}
  </div>
));

jest.mock('../../components/ManualTransactionEntry', () => ({ onValidDataConfirmed }) => (
  <button
    type="button"
    data-testid="manual-confirm"
    onClick={() =>
      onValidDataConfirmed([
        { amount: '150', merchant_id: 'M200' },
        { amount: '75', merchant_id: 'M200' },
      ])
    }
  >
    Confirm Manual Data
  </button>
));

// Simplified DesiredMarginResults: exposes key result props for test assertions
jest.mock('../../components/DesiredMarginResults', () => ({ results, onNewCalculation }) => (
  <div data-testid="results-view">
    <span data-testid="result-suggested-rate">
      {results?.suggestedRate !== null && results?.suggestedRate !== undefined
        ? String(results.suggestedRate)
        : 'null'}
    </span>
    <span data-testid="result-margin-bps">
      {results?.marginBps !== null && results?.marginBps !== undefined
        ? String(results.marginBps)
        : 'null'}
    </span>
    <span data-testid="result-profit-min">
      {results?.estimatedProfitMin !== null && results?.estimatedProfitMin !== undefined
        ? String(results.estimatedProfitMin)
        : 'null'}
    </span>
    <button type="button" onClick={onNewCalculation}>
      New Calculation
    </button>
  </div>
));

// ── Module imports (after mocks) ──────────────────────────────────────────────

import { desiredMarginAPI } from '../../services/api';
import DesiredMarginCalculator from '../../components/DesiredMarginCalculator';

// ── Test constants ────────────────────────────────────────────────────────────

const VALID_CSV =
  'transaction_date,merchant_id,mcc,amount\n' +
  '2026-01-01,M100,5812,100.50\n' +
  '2026-01-02,M100,5812,75.25';

const INVALID_CSV_MISSING_MCC =
  'transaction_date,merchant_id,amount\n' +
  '2026-01-01,M100,100.50';

const SUCCESS_API_RESPONSE = {
  data: {
    summary: {
      suggested_rate_pct: 2.1,
      margin_bps: 150,
      estimated_profit_min: 5000,
      estimated_profit_max: 7000,
    },
    cost_forecast: [],
    volume_forecast: [],
    profitability_curve: [],
  },
};

const OriginalFileReader = global.FileReader;

// ── Helpers ───────────────────────────────────────────────────────────────────

const mockCsvFileReader = (content) => {
  global.FileReader = class {
    readAsText() {
      this.onload({ target: { result: content } });
    }
  };
};

const uploadCsvFile = (csvContent, filename = 'transactions.csv') => {
  mockCsvFileReader(csvContent);
  const input = document.querySelector('#file-upload');
  const file = new File([csvContent], filename, { type: 'text/csv' });
  fireEvent.change(input, { target: { files: [file] } });
};

const selectFeeStructure = (value) => {
  fireEvent.change(screen.getByRole('combobox', { name: /preferred fee structure/i }), {
    target: { value },
  });
};

const submitForm = () => {
  fireEvent.click(screen.getByRole('button', { name: /calculate results/i }));
};

// ── Test suite ────────────────────────────────────────────────────────────────

describe('Rate Optimisation Tool (DesiredMarginCalculator) – integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    global.FileReader = OriginalFileReader;
    jest.restoreAllMocks();
  });

  // ── IC1: Valid CSV upload – parsing, format validation, success response ───

  describe('IC1 – Valid CSV upload: parsing, format validation and success state', () => {
    it('valid CSV is parsed successfully and transaction count is displayed without errors', () => {
      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      uploadCsvFile(VALID_CSV);

      expect(screen.getByText(/2 transactions parsed/i)).toBeInTheDocument();
      expect(screen.queryByText(/missing required columns/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/error parsing/i)).not.toBeInTheDocument();
    });

    it('uploads an unsupported file format and shows an unsupported format error', () => {
      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      const input = document.querySelector('#file-upload');
      const file = new File(['bad'], 'upload.txt', { type: 'text/plain' });
      fireEvent.change(input, { target: { files: [file] } });

      expect(screen.getByText(/unsupported file format/i)).toBeInTheDocument();
    });
  });

  // ── IC2: Manual input flow ────────────────────────────────────────────────

  describe('IC2 – Manual transaction entry: success response to frontend', () => {
    it('confirms manual data and triggers a successful API call', async () => {
      desiredMarginAPI.getDesiredMarginDetails.mockResolvedValue({ data: {} });

      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      fireEvent.click(screen.getByRole('button', { name: /manual entry/i }));
      fireEvent.click(screen.getByTestId('manual-confirm'));

      fireEvent.change(screen.getByTestId('mcc-dropdown'), { target: { value: '5411' } });
      selectFeeStructure('percentage');
      submitForm();

      await waitFor(() =>
        expect(desiredMarginAPI.getDesiredMarginDetails).toHaveBeenCalledTimes(1),
      );
      await waitFor(() =>
        expect(screen.getByTestId('results-view')).toBeInTheDocument(),
      );
    });

    it('calculates correct average ticket size and transaction count from manual entries', async () => {
      desiredMarginAPI.getDesiredMarginDetails.mockResolvedValue({ data: {} });

      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      fireEvent.click(screen.getByRole('button', { name: /manual entry/i }));
      // Mock provides 2 transactions: $150 and $75 → avg = 112.5, count = 2
      fireEvent.click(screen.getByTestId('manual-confirm'));

      fireEvent.change(screen.getByTestId('mcc-dropdown'), { target: { value: '5411' } });
      selectFeeStructure('percentage');
      submitForm();

      await waitFor(() =>
        expect(desiredMarginAPI.getDesiredMarginDetails).toHaveBeenCalled(),
      );

      const payload = desiredMarginAPI.getDesiredMarginDetails.mock.calls[0][0];
      expect(payload.average_transaction_value).toBeCloseTo(112.5);
      expect(payload.monthly_transactions).toBe(2);
      expect(payload.mcc).toBe('5411');
    });
  });

  // ── IC3: Invalid CSV – validation error displayed to frontend ─────────────

  describe('IC3 – Invalid CSV: validation error triggers error message on frontend', () => {
    it('CSV with missing required column shows a missing columns error message', () => {
      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      uploadCsvFile(INVALID_CSV_MISSING_MCC);

        expect(screen.getByText(/missing required columns.*mcc/i)).toBeInTheDocument();
    });

    it('CSV with fewer than 2 rows shows a no-data error message', () => {
      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      uploadCsvFile('transaction_date,merchant_id,mcc,amount');

      expect(
        screen.getByText(/must contain at least a header row and one data row/i),
      ).toBeInTheDocument();
    });
  });

  // ── IC4: MCC auto-detection from uploaded CSV ─────────────────────────────

  describe('IC4 – MCC auto-detection: detected MCC returned to frontend', () => {
    it('MCC field is auto-populated from the first row of the uploaded CSV', () => {
      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

      uploadCsvFile(VALID_CSV); // first row mcc = '5812'

      expect(screen.getByTestId('mcc-dropdown')).toHaveValue('5812');
    });
  });

  // ── IC5: Payload construction – all fee × desired-margin permutations ─────

  describe('IC5 – Payload: MCC, fee structure, desired margin sent to backend API', () => {
    const uploadAndSubmitWith = async (setupFn) => {
      desiredMarginAPI.getDesiredMarginDetails.mockResolvedValue({ data: {} });
      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);
      uploadCsvFile(VALID_CSV); // sets parsedData and mcc = '5812'
      setupFn();
      submitForm();
      await waitFor(() =>
        expect(desiredMarginAPI.getDesiredMarginDetails).toHaveBeenCalled(),
      );
      return desiredMarginAPI.getDesiredMarginDetails.mock.calls[0][0];
    };

    it('%-only, no desired margin → desired_margin defaults to 0.015, fixed_fee defaults to 0.30', async () => {
      const payload = await uploadAndSubmitWith(() => selectFeeStructure('percentage'));

      expect(payload).toMatchObject({
        mcc: '5812',
        desired_margin: 0.015,
        fixed_fee: 0.3,
      });
    });

    it('%-only, desired margin 150 bps → desired_margin sent as 0.015 (150 / 10000)', async () => {
      const payload = await uploadAndSubmitWith(() => {
        selectFeeStructure('percentage');
        fireEvent.change(screen.getByPlaceholderText(/enter desired margin/i), {
          target: { value: '150' },
        });
      });

      expect(payload.desired_margin).toBeCloseTo(0.015, 4);
    });

    it('%-fixed with fixed fee 0.25 → fixed_fee sent as 0.25', async () => {
      const payload = await uploadAndSubmitWith(() => {
        selectFeeStructure('percentage-fixed');
        fireEvent.change(screen.getByPlaceholderText(/enter fixed fee \(\$\)/i), {
          target: { value: '0.25' },
        });
      });

      expect(payload.fixed_fee).toBe(0.25);
    });

    it('fixed-only, no desired margin → desired_margin defaults to 0.015', async () => {
      const payload = await uploadAndSubmitWith(() => selectFeeStructure('fixed'));

      expect(payload.desired_margin).toBe(0.015);
      expect(payload.mcc).toBe('5812');
    });
  });

  // ── IC6: Backend response format displayed to frontend ────────────────────

  describe('IC6 – Backend JSON response rendered correctly on frontend', () => {
    it('suggested rate and margin from successful backend response are displayed', async () => {
      desiredMarginAPI.getDesiredMarginDetails.mockResolvedValue(SUCCESS_API_RESPONSE);

      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);
      uploadCsvFile(VALID_CSV);
      selectFeeStructure('percentage');
      submitForm();

      await waitFor(() =>
        expect(screen.getByTestId('results-view')).toBeInTheDocument(),
      );

      expect(screen.getByTestId('result-suggested-rate').textContent).toBe('2.1');
      expect(screen.getByTestId('result-margin-bps').textContent).toBe('150');
      expect(screen.getByTestId('result-profit-min').textContent).toBe('5000');
    });
  });

  // ── IC7: Backend unavailable → null values returned to frontend ───────────

  describe('IC7 – Backend unavailable: null values sent to results view', () => {
    it('rejected API call results in null suggestedRate and marginBps in the results view', async () => {
      desiredMarginAPI.getDesiredMarginDetails.mockRejectedValue(
        new Error('Service unavailable'),
      );

      render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);
      uploadCsvFile(VALID_CSV);
      selectFeeStructure('percentage');
      submitForm();

      await waitFor(() =>
        expect(screen.getByTestId('results-view')).toBeInTheDocument(),
      );

      expect(screen.getByTestId('result-suggested-rate').textContent).toBe('null');
      expect(screen.getByTestId('result-margin-bps').textContent).toBe('null');
      expect(screen.getByTestId('result-profit-min').textContent).toBe('null');
    });
  });

  // ── IC8: "More Details" – cost forecasts, volume, profitability sections ──────────
  // Uses jest.requireActual to render the real DesiredMarginResults component,
  // bypassing the simplified stub defined above.

  describe('IC8 – "More Details": cost forecasts, volume trends, profitability curve', () => {
    it('clicking More Details reveals the cost forecast chart, volume trend, and profitability sections', () => {
      const RealDesiredMarginResults =
        jest.requireActual('../../components/DesiredMarginResults').default;

      const mockResults = {
        suggestedRate: 2.1,
        marginBps: 150,
        estimatedProfitMin: 5000,
        estimatedProfitMax: 7000,
        costForecast: [
          { label: 'W1-Jan (2026-01-07)', mid: 0.021, lower: 0.018, upper: 0.024 },
        ],
        volumeForecast: [
          { label: 'W1-Jan (2026-01-07)', mid: 10000, lower: 9000, upper: 11000 },
        ],
        profitabilityCurve: [
          { label: 'W1-Jan (2026-01-07)', mid: 0.8, lower: 0.7, upper: 0.9 },
        ],
        transactionSummary: null,
        mlContext: null,
        calculation: null,
        parsedData: null,
      };

      render(
        <RealDesiredMarginResults results={mockResults} onNewCalculation={jest.fn()} />,
      );

      fireEvent.click(screen.getByRole('button', { name: /more details/i }));

      // Cost forecast chart
      expect(screen.getByRole('img', { name: /cost forecast chart/i })).toBeInTheDocument();

      // Volume trend chart
      expect(screen.getByText(/volume trend/i)).toBeInTheDocument();

      // Profitability probability curve chart
      expect(screen.getByText(/probability of profitability/i)).toBeInTheDocument();
    });
  });
});
