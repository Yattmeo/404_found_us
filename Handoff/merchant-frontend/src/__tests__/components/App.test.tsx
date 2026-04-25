import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import App from '../../App';

vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
  },
}));

const mockedAxios = axios as unknown as {
  post: ReturnType<typeof vi.fn>;
};

describe('Merchant App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const fillAndSubmitForm = () => {
    fireEvent.change(screen.getByPlaceholderText(/enter your business name/i), {
      target: { value: 'Demo Biz' },
    });

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: '5411 - General Grocery Stores' },
    });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));

    fireEvent.change(screen.getByPlaceholderText('0.00'), { target: { value: '10' } });
    fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '50' } });

    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    fireEvent.click(screen.getByLabelText(/visa/i));
    fireEvent.click(screen.getByRole('button', { name: /get my quote/i }));
  };

  it('renders backend quote on successful API response', async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        in_person_rate_range: '2.0-2.2%',
        online_rate_range: '2.2-2.4%',
        other_potential_transaction_charges: [{ name: 'Chargeback Fee', value: 25 }],
        other_monthly_charges: [{ name: 'Gateway Charge', value: 16 }],
        quote_summary: {
          payment_brands_accepted: ['Visa'],
          business_name: 'Demo Biz',
          industry: '5411 - General Grocery Stores',
          average_ticket_size: 10,
          monthly_transactions: 50,
          quote_date: 'Mon, 03 Mar 2026',
        },
      },
    });

    render(<App />);
    fillAndSubmitForm();

    await waitFor(() => expect(screen.getByText(/your payment processing quote/i)).toBeTruthy());
    expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    expect(screen.getByText('2.0-2.2%')).toBeTruthy();
  });

  it('falls back to placeholder quote when API fails', async () => {
    mockedAxios.post.mockRejectedValue(new Error('backend down'));

    render(<App />);
    fillAndSubmitForm();

    await waitFor(() => expect(screen.getByText(/your payment processing quote/i)).toBeTruthy());
    expect(screen.getAllByText('Demo Biz').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /start over/i }));
    expect(screen.getByText(/online quotation tool/i)).toBeTruthy();
  });
});
