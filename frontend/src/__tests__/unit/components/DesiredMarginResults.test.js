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
          estimatedProfit: 3500.45,
          quotableRange: { min: 2.1, max: 2.3 },
          expectedATS: 120,
          expectedVolume: 50000,
          parsedData: {
            merchantId: 'M-101',
            mcc: '5812',
            totalTransactions: 10,
            totalAmount: 1000,
            averageTicket: 100,
          },
        }}
      />,
    );

    expect(screen.getByText(/desired margin results/i)).toBeInTheDocument();
    expect(screen.getAllByText('2.2%').length).toBeGreaterThan(0);
    expect(screen.getByText('150 bps')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /new calculation/i }));
    expect(onNewCalculation).toHaveBeenCalledTimes(1);
  });
});
