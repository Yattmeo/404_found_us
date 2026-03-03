import { render, screen, fireEvent } from '@testing-library/react';
import LandingPage from '../../../components/LandingPage';

describe('LandingPage', () => {
  it('renders both calculator options', () => {
    render(<LandingPage onNavigate={jest.fn()} />);

    expect(screen.getByText('Merchant Fee Calculator')).toBeInTheDocument();
    expect(screen.getByText('Merchant Profitability Calculator')).toBeInTheDocument();
    expect(screen.getByText('Rates Quotation Tool')).toBeInTheDocument();
  });

  it('navigates to current rates and desired margin', () => {
    const onNavigate = jest.fn();
    render(<LandingPage onNavigate={onNavigate} />);

    const startButtons = screen.getAllByRole('button', { name: /get started/i });
    fireEvent.click(startButtons[0]);
    expect(onNavigate).toHaveBeenCalledWith('current-rates');

    fireEvent.click(screen.getByText('Rates Quotation Tool'));
    expect(onNavigate).toHaveBeenCalledWith('desired-margin');
  });
});
