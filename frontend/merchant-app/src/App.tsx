import { useState } from 'react';
import { QuotationForm } from './components/QuotationForm';
import { QuotationResult } from './components/QuotationResult';
import axios from 'axios';

export interface BusinessData {
  businessName: string;
  industry: string;
  averageTransactionValue: string;
  monthlyTransactions: string;
  cardTypes: string[];
  ecommercePercentage: string;
  inPersonPercentage: string;
  phoneMailPercentage: string;
}

export interface QuoteResult {
  in_person_rate_range: string;
  online_rate_range: string;
  other_potential_transaction_charges: Array<{ name: string; value: number }>;
  other_monthly_charges: Array<{ name: string; value: number }>;
  quote_summary: {
    payment_brands_accepted: string[];
    business_name: string;
    industry: string;
    average_ticket_size: number;
    monthly_transactions: number;
    quote_date: string;
  };
}

export default function App() {
  const [step, setStep] = useState<'form' | 'result'>('form');
  const [businessData, setBusinessData] = useState<BusinessData | null>(null);
  const [quoteResult, setQuoteResult] = useState<QuoteResult | null>(null);
  const [isLoadingQuote, setIsLoadingQuote] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [isPlaceholderQuote, setIsPlaceholderQuote] = useState(false);

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

  const paymentBrandMap: Record<string, string> = {
    visa: 'Visa',
    mastercard: 'Mastercard',
  };

  const buildPlaceholderQuote = (data: BusinessData): QuoteResult => {
    const avgTicket = Number(data.averageTransactionValue) || 0;
    const monthlyTransactions = Number(data.monthlyTransactions) || 0;
    const monthlyVolume = avgTicket * monthlyTransactions;

    let baseRate = 2.5;
    if (monthlyVolume > 100000) {
      baseRate -= 0.3;
    } else if (monthlyVolume > 50000) {
      baseRate -= 0.2;
    } else if (monthlyVolume > 10000) {
      baseRate -= 0.1;
    }

    baseRate = Math.max(baseRate, 1.5);
    const inPersonLower = Math.max(1.5, baseRate - 0.1);
    const inPersonUpper = baseRate + 0.1;
    const onlineLower = inPersonLower + 0.2;
    const onlineUpper = inPersonUpper + 0.2;

    const otherMonthlyCharges: Array<{ name: string; value: number }> = [
      { name: 'Point-of-sale terminal (per terminal)', value: 25 },
      { name: 'Gateway Charge', value: 16 },
    ];

    if (monthlyTransactions >= 1000) {
      otherMonthlyCharges.push({ name: 'Gateway Charge Waiver', value: -16 });
    }

    return {
      in_person_rate_range: `${inPersonLower.toFixed(1)}-${inPersonUpper.toFixed(1)}%`,
      online_rate_range: `${onlineLower.toFixed(1)}-${onlineUpper.toFixed(1)}%`,
      other_potential_transaction_charges: [
        { name: 'Chargeback Fee', value: 25 },
        { name: 'Refund Processing Fee', value: 0.5 },
      ],
      other_monthly_charges: otherMonthlyCharges,
      quote_summary: {
        payment_brands_accepted: data.cardTypes.map((brand) => paymentBrandMap[brand] || brand),
        business_name: data.businessName,
        industry: data.industry,
        average_ticket_size: Number(avgTicket.toFixed(2)),
        monthly_transactions: monthlyTransactions,
        quote_date: new Date().toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }),
      },
    };
  };

  const handleSubmit = async (data: BusinessData) => {
    setIsLoadingQuote(true);
    setQuoteError(null);

    setBusinessData(data);
    try {
      const payload = {
        business_name: data.businessName,
        industry: data.industry,
        average_transaction_value: Number(data.averageTransactionValue),
        monthly_transactions: Number(data.monthlyTransactions),
        payment_brands_accepted: data.cardTypes.map((brand) => paymentBrandMap[brand] || brand),
      };

      const response = await axios.post<QuoteResult>(`${apiBaseUrl}/merchant-quote`, payload);
      setQuoteResult(response.data);
      setIsPlaceholderQuote(false);
      setStep('result');
    } catch {
      const placeholderQuote = buildPlaceholderQuote(data);
      setQuoteResult(placeholderQuote);
      setIsPlaceholderQuote(true);
      setStep('result');
      setQuoteError('Backend unavailable. Showing placeholder quote values.');
    } finally {
      setIsLoadingQuote(false);
    }
  };

  const handleStartOver = () => {
    setBusinessData(null);
    setQuoteResult(null);
    setQuoteError(null);
    setIsPlaceholderQuote(false);
    setStep('form');
  };

  return (
    <div className="min-h-screen bg-[#E5EBE9]">
      <div className="container mx-auto px-4 merchant-page-shell">
        <div className="max-w-4xl mx-auto">
          <header className="text-center merchant-page-header">
            <h2 className="text-xl font-medium text-gray-800 mb-3">Online Quotation Tool</h2>
            <p className="text-base text-gray-600 max-w-2xl mx-auto leading-relaxed">
              Simply answer a few questions about your business and transaction volume and get a customised quote for your payment processing needs.
            </p>
          </header>

          {step === 'form' ? (
            <>
              <QuotationForm onSubmit={handleSubmit} />
              {isLoadingQuote && <p className="mt-3 text-sm text-gray-500">Generating quote from backend...</p>}
              {quoteError && <p className="mt-3 text-sm text-red-600">{quoteError}</p>}
            </>
          ) : (
            <>
              {quoteError && <p className="mb-4 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">{quoteError}</p>}
              {businessData && quoteResult && (
                <QuotationResult
                  businessData={businessData}
                  quoteResult={quoteResult}
                  onStartOver={handleStartOver}
                  isPlaceholderQuote={isPlaceholderQuote}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}