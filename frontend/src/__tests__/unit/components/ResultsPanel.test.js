import { render, screen, fireEvent } from '@testing-library/react';
import ResultsPanel from '../../../components/ResultsPanel';

describe('ResultsPanel', () => {
  it('shows placeholder when no results are provided', () => {
    render(<ResultsPanel results={null} hasCurrentRate={false} />);
    expect(screen.getByText(/submit the form to see results/i)).toBeInTheDocument();
  });

  it('renders quotation results and handles new calculation click', () => {
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

    expect(screen.getByText(/quotation results/i)).toBeInTheDocument();
    expect(screen.getAllByText('2.5%').length).toBeGreaterThan(0);

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
});
