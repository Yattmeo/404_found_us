import { useState } from 'react';
import { QuotationForm } from './components/QuotationForm';
import { QuotationResult } from './components/QuotationResult';
import logoImage from './assets/logo.svg';
import illustrationImage from './assets/illustration.svg';

export interface BusinessData {
  businessName: string;
  industry: string;
  averageTransactionValue: string;
  monthlyTransactions: string;
  paymentMethods: string[];
  cardTypes: string[];
  ecommercePercentage: string;
  inPersonPercentage: string;
  phoneMailPercentage: string;
}

export interface QuoteResult {
  transactionFee: number;
  monthlyFee: number;
  setupFee: number;
  estimatedMonthlyCost: number;
  estimatedAnnualCost: number;
  effectiveRate: number;
}

export default function App() {
  const [step, setStep] = useState<'form' | 'result'>('form');
  const [businessData, setBusinessData] = useState<BusinessData | null>(null);
  const [quoteResult, setQuoteResult] = useState<QuoteResult | null>(null);

  const handleSubmit = (data: BusinessData) => {
    setBusinessData(data);
    const result = calculateQuote(data);
    setQuoteResult(result);
    setStep('result');
  };

  const handleStartOver = () => {
    setBusinessData(null);
    setQuoteResult(null);
    setStep('form');
  };

  const calculateQuote = (data: BusinessData): QuoteResult => {
    const monthlyTransactions = parseInt(data.monthlyTransactions) || 0;
    const avgTransactionValue = parseFloat(data.averageTransactionValue) || 0;
    const monthlyVolume = monthlyTransactions * avgTransactionValue;

    // Base transaction fees (percentage)
    let transactionFee = 2.5;

    // Adjust based on payment methods
    if (data.paymentMethods.includes('digital-wallets')) {
      transactionFee -= 0.1;
    }
    if (data.paymentMethods.includes('bank-transfer')) {
      transactionFee -= 0.2;
    }

    // Volume discounts
    if (monthlyVolume > 100000) {
      transactionFee -= 0.3;
    } else if (monthlyVolume > 50000) {
      transactionFee -= 0.2;
    } else if (monthlyVolume > 10000) {
      transactionFee -= 0.1;
    }

    // E-commerce vs in-person adjustment
    const ecommercePercent = parseFloat(data.ecommercePercentage) || 0;
    if (ecommercePercent > 70) {
      transactionFee += 0.2;
    }

    // Ensure minimum fee
    transactionFee = Math.max(transactionFee, 1.5);

    // Monthly fees
    let monthlyFee = 25;
    if (monthlyVolume > 50000) {
      monthlyFee = 50;
    }
    if (monthlyVolume > 100000) {
      monthlyFee = 75;
    }

    // Setup fee
    const setupFee = 0;

    // Calculate costs
    const transactionCosts = (monthlyVolume * transactionFee) / 100;
    const estimatedMonthlyCost = transactionCosts + monthlyFee;
    const estimatedAnnualCost = estimatedMonthlyCost * 12 + setupFee;
    const effectiveRate = monthlyVolume > 0 ? (estimatedMonthlyCost / monthlyVolume) * 100 : 0;

    return {
      transactionFee: parseFloat(transactionFee.toFixed(2)),
      monthlyFee,
      setupFee,
      estimatedMonthlyCost: parseFloat(estimatedMonthlyCost.toFixed(2)),
      estimatedAnnualCost: parseFloat(estimatedAnnualCost.toFixed(2)),
      effectiveRate: parseFloat(effectiveRate.toFixed(2)),
    };
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-orange-50 flex items-center justify-center p-8">
      {step === 'form' ? (
        <div className="flex relative bg-white shadow-2xl" style={{ width: '1122px', height: '793px' }}>
          {/* Left Panel - Illustration and Branding */}
          <div className="w-[52%] bg-gradient-to-br from-[#4A8FE7] via-[#5B9FED] to-[#6CAFF3] relative overflow-hidden rounded-l-lg">
            <div className="w-full h-full p-8 flex flex-col relative z-10">
              {/* Brand Logo */}
              <div className="mb-6">
                <img 
                  src={logoImage} 
                  alt="404 Found Us" 
                  className="h-12 object-contain"
                  style={{ 
                    filter: 'brightness(0) invert(1) drop-shadow(0 2px 4px rgba(0,0,0,0.1))'
                  }}
                />
              </div>

              {/* Main Content */}
              <div className="flex-1 flex flex-col h-full">
                {/* Text Content - Positioned at top */}
                <div className="pt-1 pb-2 flex-shrink-0">
                  <h1 className="text-white text-2xl font-bold mb-2 leading-tight drop-shadow-lg">
                    Merchant Quotation Tool
                  </h1>
                  <p className="text-white text-sm italic leading-relaxed max-w-sm drop-shadow-md">
                    Simply answer a few questions about your business and transaction volume and get a customised quote for your payment processing needs.
                  </p>
                </div>

                {/* Illustration - Takes up remaining space, showing full image */}
                <div className="flex-1 flex items-start justify-center overflow-hidden pb-2">
                  <img 
                    src={illustrationImage}
                    alt="Person with laptop illustration"
                    className="w-full h-full object-contain object-top"
                    style={{ maxHeight: '105%' }}
                  />
                </div>
              </div>
            </div>

            {/* Decorative Shapes */}
            <div className="absolute top-10 right-10 w-32 h-32 bg-white/10 rounded-full blur-2xl"></div>
            <div className="absolute bottom-10 left-10 w-48 h-48 bg-white/10 rounded-full blur-2xl"></div>
          </div>

          {/* Right Panel - Form with Curved Edge */}
          <div className="w-[52%] absolute right-0 top-0 bottom-0 flex items-center justify-center p-0 z-20">
            <div className="w-full h-full bg-white rounded-l-[3rem] shadow-2xl flex items-center justify-center px-12 py-10 overflow-hidden">
              <div className="w-full max-w-xl h-full overflow-y-auto" style={{ maxHeight: 'calc(100% - 2rem)' }}>
                <QuotationForm onSubmit={handleSubmit} />
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="container mx-auto px-4 py-8 md:py-12">
          <div className="max-w-4xl mx-auto">
            {businessData && quoteResult && (
              <QuotationResult
                businessData={businessData}
                quoteResult={quoteResult}
                onStartOver={handleStartOver}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}