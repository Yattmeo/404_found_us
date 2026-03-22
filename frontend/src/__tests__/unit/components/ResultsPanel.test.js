import { render, screen, fireEvent } from '@testing-library/react';
import ResultsPanel from '../../../components/ResultsPanel';

describe('ResultsPanel', () => {
  it('shows placeholder when no results are provided', () => {
    render(<ResultsPanel results={null} hasCurrentRate={false} />);
    expect(screen.getByText(/submit the form to see results/i)).toBeInTheDocument();
  });

  it('renders no-current-rate results and handles new calculation click', () => {
    const onNewCalculation = jest.fn();
    render(
      <ResultsPanel
        hasCurrentRate={false}
        onNewCalculation={onNewCalculation}
        results={{
          suggestedRate: 2.5,
          margin: 120,
          estimatedProfit: 5000,
          quotableRange: { min: 2.3, max: 2.7 },
          expectedATS: 200,
          expectedVolume: 120000,
          adoptionProbability: 75,
        }}
      />,
    );

    expect(screen.getByText(/profitability calculation results/i)).toBeInTheDocument();
    expect(screen.getAllByText('2.50%').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /new calculation/i }));
    expect(onNewCalculation).toHaveBeenCalledTimes(1);
  });

  it('renders current-rate view and toggles more details', () => {
    render(
      <ResultsPanel
        hasCurrentRate
        results={{
          profitability: 12,
          margin: 90,
          estimatedProfit: 4200,
          expectedATS: 80,
          processingVolume: 5000,
          averageTransactionSize: 100,
          transactionCount: 50,
          suggestedRate: 1.9,
          profitDistribution: [{ value: 30, label: 'A' }],
        }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /more details/i }));
    expect(screen.getByText(/additional details/i)).toBeInTheDocument();
  });

  it('orders negative estimated profit range and colors both bounds red', () => {
    render(
      <ResultsPanel
        hasCurrentRate
        results={{
          profitability: -0.8,
          margin: -80,
          estimatedProfitMin: -169455,
          estimatedProfitMax: -207112,
          processingVolume: 100000,
          suggestedRate: 2.1,
          averageTransactionSize: 100,
          profitDistribution: [],
        }}
      />,
    );

    const lowerBound = screen.getByText('-$207,112');
    const upperBound = screen.getByText('-$169,455');

    expect(lowerBound).toHaveClass('text-red-600');
    expect(upperBound).toHaveClass('text-red-600');
    expect(
      screen.getByText((_, element) => element?.textContent === '-$207,112 - -$169,455'),
    ).toBeInTheDocument();
  });
});
