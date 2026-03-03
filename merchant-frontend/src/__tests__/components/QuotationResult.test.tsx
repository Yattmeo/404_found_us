import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { QuotationResult } from '../../components/QuotationResult';
import type { BusinessData, QuoteResult } from '../../App';

const businessData: BusinessData = {
  businessName: 'Acme Grocer',
  industry: '5411 - General Grocery Stores',
  averageTransactionValue: '25.00',
  monthlyTransactions: '100',
  cardTypes: ['visa', 'mastercard'],
  ecommercePercentage: '20',
  inPersonPercentage: '70',
  phoneMailPercentage: '10',
};

const quoteResult: QuoteResult = {
  in_person_rate_range: '2.1-2.3%',
  online_rate_range: '2.2-2.4%',
  other_potential_transaction_charges: [
    { name: 'Chargeback Fee', value: 25 },
    { name: 'Refund Processing Fee', value: 0.5 },
  ],
  other_monthly_charges: [
    { name: 'Gateway Charge', value: 16 },
    { name: 'Monthly waiver', value: -16, waived: true },
  ],
  quote_summary: {
    payment_brands_accepted: ['Visa', 'Mastercard'],
    business_name: 'Acme Grocer',
    industry: '5411 - General Grocery Stores',
    average_ticket_size: 25,
    monthly_transactions: 100,
    quote_date: 'Mon, 03 Mar 2026',
  },
};

describe('QuotationResult', () => {
  it('renders quote details and marks waived monthly charge', () => {
    render(
      <QuotationResult
        businessData={businessData}
        quoteResult={quoteResult}
        onStartOver={vi.fn()}
      />,
    );

    expect(screen.getByText(/your payment processing quote/i)).toBeTruthy();
    expect(screen.getByText('2.1-2.3%')).toBeTruthy();
    expect(screen.getByText(/waived/i)).toBeTruthy();
    expect(screen.getByText('Visa')).toBeTruthy();
    expect(screen.getByText('Mastercard')).toBeTruthy();
  });

  it('triggers start over callback', () => {
    const onStartOver = vi.fn();
    render(
      <QuotationResult
        businessData={businessData}
        quoteResult={quoteResult}
        onStartOver={onStartOver}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /start over/i }));
    expect(onStartOver).toHaveBeenCalledTimes(1);
  });
});
