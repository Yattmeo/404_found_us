import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DesiredMarginCalculator from '../../../components/DesiredMarginCalculator';
import { desiredMarginAPI } from '../../../services/api';
import * as XLSX from 'xlsx';

jest.mock('../../../services/api', () => ({
  desiredMarginAPI: {
    calculateDesiredMargin: jest.fn(),
  },
}));

jest.mock('xlsx', () => ({
  read: jest.fn(),
  utils: {
    sheet_to_json: jest.fn(),
  },
}));

jest.mock('../../../components/ManualTransactionEntry', () => (props) => (
  <button
    type="button"
    onClick={() =>
      props.onValidDataConfirmed([
        { amount: '100', merchant_id: 'M1' },
        { amount: '50', merchant_id: 'M1' },
      ])
    }
  >
    Mock Manual Confirm
  </button>
));

jest.mock('../../../components/MCCDropdown', () => (props) => (
  <button type="button" onClick={() => props.onChange('5812')}>
    Mock MCC Select
  </button>
));

jest.mock('../../../components/DesiredMarginResults', () => ({ onNewCalculation }) => (
  <div>
    <span>Desired Margin Results Mock</span>
    <button type="button" onClick={onNewCalculation}>Start Over</button>
  </div>
));

describe('DesiredMarginCalculator', () => {
  const OriginalFileReader = global.FileReader;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    global.FileReader = OriginalFileReader;
    jest.restoreAllMocks();
  });

  it('calls back to landing screen', () => {
    const onBackToLanding = jest.fn();
    render(<DesiredMarginCalculator onBackToLanding={onBackToLanding} />);

    fireEvent.click(screen.getByRole('button', { name: /back to home/i }));
    expect(onBackToLanding).toHaveBeenCalledTimes(1);
  });

  it('submits manual data flow and renders results view', async () => {
    desiredMarginAPI.calculateDesiredMargin.mockResolvedValue({
      data: {
        recommended_rate: 0.021,
        desired_margin: 0.015,
        estimated_total_fees: 200,
        average_ticket: 75,
        total_volume: 150,
      },
    });

    render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /manual entry/i }));
    fireEvent.click(screen.getByRole('button', { name: /mock manual confirm/i }));
    fireEvent.click(screen.getByRole('button', { name: /mock mcc select/i }));

    fireEvent.change(screen.getByLabelText(/preferred fee structure/i), {
      target: { value: 'percentage' },
    });

    fireEvent.click(screen.getByRole('button', { name: /calculate results/i }));

    await waitFor(() => expect(desiredMarginAPI.calculateDesiredMargin).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/desired margin results mock/i)).toBeInTheDocument();
  });

  it('shows unsupported file error for invalid upload extension', async () => {
    render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

    const input = document.querySelector('#file-upload');
    const invalidFile = new File(['bad'], 'bad.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [invalidFile] } });

    expect(await screen.findByText(/unsupported file format/i)).toBeInTheDocument();
  });

  it('parses csv upload and submits using parsed transaction data', async () => {
    global.FileReader = class {
      readAsText() {
        this.onload({
          target: {
            result: 'transaction_date,merchant_id,mcc,amount\n2026-01-01,M1,5812,100.5',
          },
        });
      }
    };

    desiredMarginAPI.calculateDesiredMargin.mockResolvedValue({ data: {} });

    render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

    const input = document.querySelector('#file-upload');
    const csvFile = new File(['csv'], 'merchant.csv', { type: 'text/csv' });
    fireEvent.change(input, { target: { files: [csvFile] } });

    await waitFor(() => expect(screen.getByText(/1 transactions parsed/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/preferred fee structure/i), {
      target: { value: 'percentage-fixed' },
    });

    expect(screen.getByLabelText(/fixed fee/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/desired margin/i), { target: { value: '120' } });
    fireEvent.change(screen.getByLabelText(/fixed fee/i), { target: { value: '0.4' } });
    fireEvent.click(screen.getByRole('button', { name: /calculate results/i }));

    await waitFor(() => expect(desiredMarginAPI.calculateDesiredMargin).toHaveBeenCalledTimes(1));
    expect(desiredMarginAPI.calculateDesiredMargin).toHaveBeenCalledWith(
      expect.objectContaining({
        mcc: '5812',
        desired_margin: 0.012,
        fixed_fee: 0.4,
        transactions: expect.arrayContaining([
          expect.objectContaining({ merchantId: 'M1', mcc: '5812', amount: 100.5 }),
        ]),
      }),
    );
  });

  it('parses excel upload path and handles API fallback + reset', async () => {
    global.FileReader = class {
      readAsBinaryString() {
        this.onload({ target: { result: 'binary-data' } });
      }
    };

    XLSX.read.mockReturnValue({
      SheetNames: ['Sheet1'],
      Sheets: { Sheet1: {} },
    });

    XLSX.utils.sheet_to_json.mockReturnValue([
      ['transaction_date', 'merchant_id', 'mcc', 'amount'],
      ['2026-01-01', 'M2', '5411', 230],
    ]);

    desiredMarginAPI.calculateDesiredMargin.mockRejectedValue(new Error('backend down'));

    render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);

    const input = document.querySelector('#file-upload');
    const xlsxFile = new File(['bin'], 'merchant.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    fireEvent.change(input, { target: { files: [xlsxFile] } });

    await waitFor(() => expect(screen.getByText(/1 transactions parsed/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/preferred fee structure/i), {
      target: { value: 'percentage' },
    });

    fireEvent.click(screen.getByRole('button', { name: /calculate results/i }));
    await waitFor(() => expect(screen.getByText(/desired margin results mock/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /start over/i }));
    expect(screen.getByText(/merchant transaction data/i)).toBeInTheDocument();
  });

  it('downloads csv template from upload section', () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    URL.createObjectURL = jest.fn(() => 'blob:template');
    URL.revokeObjectURL = jest.fn();
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<DesiredMarginCalculator onBackToLanding={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /download csv template/i }));

    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:template');

    clickSpy.mockRestore();
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  });
});
