import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

const expectedIndustryOptions = [
  '5411 - General Grocery Stores',
  '5732 - Electronics Stores',
  '5812 - Eating Places and Restaurants',
  '5814 - Fast Food Restaurants',
  '5967 - Direct Marketing',
  '7011 - Lodging and Hotels',
  '7399 - Business Services',
  '7999 - Recreation Services',
  '8062 - Hospitals',
  '8999 - Professional Services',
];

const successfulQuoteResponse = {
  data: {
    in_person_rate_range: '1.9-2.1%',
    online_rate_range: '2.0-2.2%',
    other_potential_transaction_charges: [{ name: 'Chargeback Fee', value: 25 }],
    other_monthly_charges: [{ name: 'Gateway Charge', value: 16, waived: false }],
    quote_summary: {
      payment_brands_accepted: ['Visa', 'Mastercard'],
      business_name: 'Downtown Deli',
      industry: '5411 - General Grocery Stores',
      average_ticket_size: 12.5,
      monthly_transactions: 1200,
      quote_date: 'Mon, 17 Mar 2026',
    },
    ml_insights: null,
  },
};

const completeMerchantQuoteJourney = async () => {
  const user = userEvent.setup();

  await user.type(screen.getByPlaceholderText(/enter your business name/i), 'Downtown Deli');
  await user.selectOptions(screen.getByRole('combobox'), '5411 - General Grocery Stores');
  await user.click(screen.getByRole('button', { name: /next/i }));

  await user.type(screen.getByPlaceholderText('0.00'), '12.5');
  await user.type(screen.getByPlaceholderText('0'), '1200');
  await user.click(screen.getByRole('button', { name: /next/i }));

  await user.click(screen.getByLabelText(/visa/i));
  await user.click(screen.getByLabelText(/mastercard/i));
  await user.selectOptions(screen.getByRole('combobox'), 'online');
  await user.click(screen.getByRole('button', { name: /get my quote/i }));
};

describe('Merchant tool integration flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads the full Step 1 MCC industry list into the dropdown', () => {
    render(<App />);

    const industrySelect = screen.getByRole('combobox');
    const industryOptions = within(industrySelect).getAllByRole('option');

    expect(industryOptions).toHaveLength(expectedIndustryOptions.length + 1);
    expect(industryOptions[0]).toHaveTextContent(/select mcc industry/i);

    expectedIndustryOptions.forEach((industryLabel) => {
      expect(within(industrySelect).getByRole('option', { name: industryLabel })).toBeInTheDocument();
    });
  });

  it('packages data from steps 2 and 3 into the expected merchant quote payload', async () => {
    mockedAxios.post.mockResolvedValue(successfulQuoteResponse);

    render(<App />);
    await completeMerchantQuoteJourney();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/merchant-quote',
        {
          business_name: 'Downtown Deli',
          industry: '5411 - General Grocery Stores',
          average_transaction_value: 12.5,
          monthly_transactions: 1200,
          payment_brands_accepted: ['Visa', 'Mastercard'],
        },
      );
    });
  });

  it('shows an error message when the ML-backed quote service is unreachable', async () => {
    mockedAxios.post.mockRejectedValue(new Error('ml-service unreachable'));

    render(<App />);
    await completeMerchantQuoteJourney();

    expect(await screen.findByRole('alert')).toHaveTextContent(/backend unavailable/i);
    expect(screen.getByText(/your payment processing quote/i)).toBeInTheDocument();
    expect(screen.getByText('Waived')).toBeInTheDocument();
  });

  it('renders waivers returned by the fee engine on high-volume quotes', async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        ...successfulQuoteResponse.data,
        other_monthly_charges: [
          { name: 'Point-of-sale terminal (per terminal)', value: 25, waived: false },
          { name: 'Gateway Charge', value: 16, waived: true },
        ],
      },
    });

    render(<App />);
    await completeMerchantQuoteJourney();

    expect(await screen.findByText(/other monthly charges/i)).toBeInTheDocument();
    expect(screen.getByText('Gateway Charge')).toBeInTheDocument();
    expect(screen.getByText('Waived')).toBeInTheDocument();
    expect(screen.getByText('1.9-2.1%')).toBeInTheDocument();
  });
});