import { render, screen } from '@testing-library/react';
import { Label } from '../../../components/ui/Label';

describe('Label', () => {
  it('renders text and htmlFor attribute', () => {
    render(<Label htmlFor="merchantId">Merchant ID</Label>);

    const label = screen.getByText('Merchant ID');
    expect(label).toBeInTheDocument();
    expect(label).toHaveAttribute('for', 'merchantId');
  });
});
