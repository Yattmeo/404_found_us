import { render, screen, fireEvent } from '@testing-library/react';
import MCCDropdown from '../../../components/MCCDropdown';

describe('MCCDropdown', () => {
  it('shows placeholder and selects a predefined MCC', () => {
    const onChange = jest.fn();
    render(<MCCDropdown value="" onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: /select or enter mcc/i }));
    fireEvent.click(screen.getByText('5812'));

    expect(onChange).toHaveBeenCalledWith('5812');
  });

  it('submits a custom MCC value', () => {
    const onChange = jest.fn();
    render(<MCCDropdown value="" onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: /select or enter mcc/i }));
    fireEvent.change(screen.getByPlaceholderText(/search or enter custom mcc code/i), {
      target: { value: '9999' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Use "9999" as custom MCC' }));
    expect(onChange).toHaveBeenCalledWith('9999');
  });

  it('renders error text when provided', () => {
    render(<MCCDropdown value="" onChange={jest.fn()} error="MCC is required" />);
    expect(screen.getByText('MCC is required')).toBeInTheDocument();
  });
});
