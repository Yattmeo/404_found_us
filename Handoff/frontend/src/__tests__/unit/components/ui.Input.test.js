import { render, screen } from '@testing-library/react';
import { Input } from '../../../components/ui/Input';

describe('Input', () => {
  it('renders input with passed attributes', () => {
    render(<Input type="number" placeholder="Enter value" aria-label="amount" />);

    const input = screen.getByLabelText('amount');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('type', 'number');
    expect(input).toHaveAttribute('placeholder', 'Enter value');
  });
});
