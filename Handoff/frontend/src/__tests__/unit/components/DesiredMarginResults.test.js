import { render, screen, fireEvent } from '@testing-library/react';
import DesiredMarginResults from '../../../components/DesiredMarginResults';

describe('DesiredMarginResults', () => {
  it('renders nothing when results are missing', () => {
    const { container } = render(<DesiredMarginResults results={null} onNewCalculation={jest.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders key metrics and handles new calculation', () => {
    const onNewCalculation = jest.fn();

    render(
      <DesiredMarginResults
        onNewCalculation={onNewCalculation}
        results={{
          suggestedRate: 2.2,
          marginBps: 150,
          estimatedProfitMin: 12500,
          estimatedProfitMax: 32500,
          transactionSummary: {
            mcc: 5812,
            transaction_count: 10,
            total_volume: 1000,
            average_ticket: 100,
            start_date: '2026-01-01',
            end_date: '2026-01-31',
          },
          mlContext: { matched_neighbor_merchant_ids: [1001, 1002] },
          costForecast: [{ week_index: 1, label: 'W1', mid: 0.02 }],
          volumeForecast: [{ week_index: 1, label: 'W1', mid: 64000 }],
          profitabilityCurve: [{ rate_pct: 2.2, probability_pct: 80 }],
        }}
      />,
    );

    expect(screen.getByText(/rates quotation results/i)).toBeInTheDocument();
    expect(screen.getByText('2.20%')).toBeInTheDocument();
    expect(screen.getByText('150')).toBeInTheDocument();
    expect(screen.getByText('$12,500.00 - $32,500.00')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /more details/i }));
    expect(screen.getByText(/cost forecast/i)).toBeInTheDocument();
    expect(screen.getByText(/transaction summary/i)).toBeInTheDocument();
    expect(screen.getByText(/volume trend/i)).toBeInTheDocument();
    expect(screen.getByText(/probability of profitability/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /new calculation/i }));
    expect(onNewCalculation).toHaveBeenCalledTimes(1);
  });
});
