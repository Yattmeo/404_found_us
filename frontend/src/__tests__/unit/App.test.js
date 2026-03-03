import { render, screen, fireEvent } from '@testing-library/react';
import App from '../../App';

jest.mock('../../components/LandingPage', () => (props) => (
  <div>
    <button type="button" onClick={() => props.onNavigate('current-rates')}>
      Go Current
    </button>
    <button type="button" onClick={() => props.onNavigate('desired-margin')}>
      Go Desired
    </button>
  </div>
));

jest.mock('../../components/EnhancedMerchantFeeCalculator', () => (props) => (
  <div>
    <span>Enhanced Calculator Mock</span>
    <button type="button" onClick={props.onBackToLanding}>Back Home</button>
  </div>
));

jest.mock('../../components/DesiredMarginCalculator', () => (props) => (
  <div>
    <span>Desired Margin Calculator Mock</span>
    <button type="button" onClick={props.onBackToLanding}>Back Home</button>
  </div>
));

describe('App', () => {
  it('renders landing page by default', () => {
    render(<App />);
    expect(screen.getByRole('button', { name: /go current/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /go desired/i })).toBeInTheDocument();
  });

  it('navigates to current-rates view and back to landing', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /go current/i }));
    expect(screen.getByText(/enhanced calculator mock/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /back home/i }));
    expect(screen.getByRole('button', { name: /go desired/i })).toBeInTheDocument();
  });

  it('navigates to desired-margin view', () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: /go desired/i }));
    expect(screen.getByText(/desired margin calculator mock/i)).toBeInTheDocument();
  });
});
