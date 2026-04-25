import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { QuotationForm } from '../../components/QuotationForm';
import type { BusinessData } from '../../App';

describe('QuotationForm', () => {
  const completeForm = () => {
    fireEvent.change(screen.getByPlaceholderText(/enter your business name/i), {
      target: { value: 'Acme Grocer' },
    });

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: '5411 - General Grocery Stores' },
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    fireEvent.change(screen.getByPlaceholderText('0.00'), {
      target: { value: '100' },
    });

    fireEvent.change(screen.getByPlaceholderText('0'), {
      target: { value: '12' },
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));
  };

  it('submits normalized values after all steps', () => {
    const onSubmit = vi.fn();
    render(<QuotationForm onSubmit={onSubmit} />);

    completeForm();

    fireEvent.click(screen.getByLabelText(/visa/i));
    fireEvent.click(screen.getByRole('button', { name: /get my quote/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0] as BusinessData;
    expect(payload.businessName).toBe('Acme Grocer');
    expect(payload.industry).toBe('5411 - General Grocery Stores');
    expect(payload.averageTransactionValue).toBe('100.00');
    expect(payload.monthlyTransactions).toBe('12');
    expect(payload.cardTypes).toEqual(['visa']);
  });

  it('shows card type validation error when submitting without selection', () => {
    render(<QuotationForm onSubmit={vi.fn()} />);

    completeForm();

    fireEvent.submit(screen.getByRole('button', { name: /get my quote/i }).closest('form')!);
    expect(screen.getByText(/select at least one payment channel/i)).toBeTruthy();
  });

  it('formats amount on blur and supports previous-step navigation', () => {
    render(<QuotationForm onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText(/enter your business name/i), {
      target: { value: 'Acme Grocer' },
    });
    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: '5411 - General Grocery Stores' },
    });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    const amountInput = screen.getByPlaceholderText('0.00') as HTMLInputElement;
    fireEvent.change(amountInput, {
      target: { value: '25' },
    });
    fireEvent.blur(amountInput);
    expect((screen.getByPlaceholderText('0.00') as HTMLInputElement).value).toBe('25.00');

    fireEvent.click(screen.getByRole('button', { name: /previous/i }));
    expect(screen.getByText(/business information/i)).toBeTruthy();
  });

  it('ignores blocked numeric keys and lets user deselect and reselect card types', () => {
    render(<QuotationForm onSubmit={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText(/enter your business name/i), {
      target: { value: 'Acme Grocer' },
    });
    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: '5411 - General Grocery Stores' },
    });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    const amountInput = screen.getByPlaceholderText('0.00');
    fireEvent.keyDown(amountInput, { key: '-' });
    expect((amountInput as HTMLInputElement).value).toBe('');

    fireEvent.change(amountInput, {
      target: { value: '100' },
    });
    fireEvent.change(screen.getByPlaceholderText('0'), {
      target: { value: '12' },
    });
    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    const visaCheckbox = screen.getByLabelText(/visa/i) as HTMLInputElement;
    expect(visaCheckbox.checked).toBe(false);
    fireEvent.click(visaCheckbox);
    expect(visaCheckbox.checked).toBe(true);
    fireEvent.click(visaCheckbox);
    expect(visaCheckbox.checked).toBe(false);

    fireEvent.click(screen.getByLabelText(/mastercard/i));
    expect((screen.getByLabelText(/mastercard/i) as HTMLInputElement).checked).toBe(true);

    const processingTypeSelect = screen.getAllByRole('combobox')[0] as HTMLSelectElement;
    fireEvent.change(processingTypeSelect, { target: { value: 'online' } });
    expect(processingTypeSelect.value).toBe('online');
  });
});
