import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EnhancedMerchantFeeCalculator from '../../../components/EnhancedMerchantFeeCalculator';
import { merchantFeeAPI } from '../../../services/api';

jest.mock('../../../services/api', () => ({
  merchantFeeAPI: {
    calculateCurrentRates: jest.fn(),
  },
}));

jest.mock('../../../components/DataUploadValidator', () => (props) => (
  <button
    type="button"
    onClick={() => {
      props.onValidDataConfirmed([{ amount: '100.00' }], '5812');
      props.onMCCExtracted?.('5812');
    }}
  >
    Mock Upload Confirm
  </button>
));

jest.mock('../../../components/ManualTransactionEntry', () => () => <div>Manual Entry Mock</div>);
jest.mock('../../../components/MCCDropdown', () => (props) => (
  <button type="button" onClick={() => props.onChange('5812')}>
    Mock MCC Select
  </button>
));

jest.mock('../../../components/ResultsPanel', () => ({ results, onNewCalculation }) => (
  <div>
    <span>Results Panel Mock</span>
    <button type="button" onClick={onNewCalculation}>Mock New Calculation</button>
    <span>{results?.suggestedRate}</span>
  </div>
));

describe('EnhancedMerchantFeeCalculator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('calls back to landing screen', () => {
    const onBackToLanding = jest.fn();
    render(<EnhancedMerchantFeeCalculator onBackToLanding={onBackToLanding} />);

    fireEvent.click(screen.getByRole('button', { name: /back to home/i }));
    expect(onBackToLanding).toHaveBeenCalledTimes(1);
  });

  it('submits validated data and shows results', async () => {
    merchantFeeAPI.calculateCurrentRates.mockResolvedValue({ suggestedRate: 1.8 });

    render(<EnhancedMerchantFeeCalculator onBackToLanding={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /mock upload confirm/i }));
    fireEvent.click(screen.getByRole('button', { name: /mock mcc select/i }));

    fireEvent.change(screen.getByLabelText(/preferred fee structure/i), {
      target: { value: 'percentage' },
    });

    fireEvent.click(screen.getByRole('button', { name: /proceed to projection/i }));

    await waitFor(() => expect(merchantFeeAPI.calculateCurrentRates).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/results panel mock/i)).toBeInTheDocument();
  });
});
