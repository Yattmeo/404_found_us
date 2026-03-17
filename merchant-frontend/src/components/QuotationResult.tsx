import { RotateCcw } from 'lucide-react';
import { BusinessData, QuoteResult } from '../App';

interface QuotationResultProps {
  businessData: BusinessData;
  quoteResult: QuoteResult;
  onStartOver: () => void;
  isPlaceholderQuote?: boolean;
  quoteError?: string | null;
}

export function QuotationResult({
  businessData,
  quoteResult,
  onStartOver,
  isPlaceholderQuote = false,
  quoteError = null,
}: QuotationResultProps) {
  const formatCurrency = (value: number) => {
    return `$${value.toFixed(2)}`;
  };
  const formatPct = (value: number) => `${value.toFixed(2)}%`;

  const acceptedBrands = quoteResult.quote_summary.payment_brands_accepted;
  const hasWaiverLine = quoteResult.other_monthly_charges.some((charge) => /waiver/i.test(charge.name));
  const monthlyChargesForDisplay = quoteResult.other_monthly_charges
    .filter((charge) => !/waiver/i.test(charge.name))
    .map((charge) => {
      const isGatewayCharge = /gateway charge/i.test(charge.name);
      const isWaived = Boolean(charge.waived) || (isGatewayCharge && hasWaiverLine);
      const displayValue = isWaived
        ? 'Waived'
        : charge.value < 0
          ? `-${formatCurrency(Math.abs(charge.value))}`
          : formatCurrency(charge.value);

      return {
        name: charge.name,
        displayValue,
      };
    });

  return (
    <div className="space-y-6">
      {quoteError && (
        <div role="alert" className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-900">
          {quoteError}
        </div>
      )}

      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-medium text-gray-900">Your Payment Processing Quote</h2>
        </div>
        <p className="text-gray-600">
          Quote prepared for <span className="font-semibold">{businessData.businessName}</span>
        </p>
      </div>

      {/* Main pricing table */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-lg font-medium text-gray-900 mb-1">Estimated rates</h3>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b-2 border-gray-300">
                <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Payment Type</th>
                <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">Rate</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-200">
                <td className="py-3 px-4 text-sm text-gray-900">Cards in person</td>
                <td className="py-3 px-4 text-sm text-gray-900">{quoteResult.in_person_rate_range}</td>
              </tr>
              <tr className="border-b border-gray-200">
                <td className="py-3 px-4 text-sm text-gray-900">Cards online or by phone</td>
                <td className="py-3 px-4 text-sm text-gray-900">{quoteResult.online_rate_range}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-6 text-gray-600">Reach out to our sales team for a more precise quote.</p>
      </div>

      {/* Other potential transaction charges */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-lg font-medium text-gray-900 mb-6">Other potential transaction charges</h3>
        
        <div className="grid md:grid-cols-2 gap-4">
          {quoteResult.other_potential_transaction_charges.map((charge) => (
            <div key={charge.name} className="border border-gray-300 rounded p-4">
              <p className="text-sm text-gray-700 mb-1">{charge.name}</p>
              <p className="text-2xl font-semibold text-gray-900">{formatCurrency(charge.value)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Two column layout for monthly charges and other details */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Other monthly charges */}
        <div className="bg-white rounded-lg shadow p-6 md:p-8">
          <h3 className="text-lg font-medium text-gray-900 mb-6">Other monthly charges</h3>
          
          <div className="space-y-4">
            {monthlyChargesForDisplay.map((charge) => (
              <div key={charge.name} className="flex justify-between items-center pb-3 border-b border-gray-200 last:border-b-0">
                <p className="text-sm text-gray-700">{charge.name}</p>
                <p className="text-sm font-semibold text-gray-900">{charge.displayValue}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Other details */}
        <div className="bg-white rounded-lg shadow p-6 md:p-8">
          <h3 className="text-lg font-medium text-gray-900 mb-6">Other details</h3>
          
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-500 mb-2">Payment brands accepted</p>
              <div className="flex flex-wrap gap-2">
                {acceptedBrands.map((brand) => (
                  <span key={brand} className="px-3 py-1 bg-orange-100 text-orange-800 text-xs font-medium rounded">{brand}</span>
                ))}
              </div>
            </div>

            {quoteResult.ml_insights && (
              <div>
                <p className="text-sm text-gray-500 mb-2">ML service insights</p>
                <div className="space-y-2 text-sm text-gray-700">
                  <p>Neighbors used: {quoteResult.ml_insights.knn_neighbor_count}</p>
                  <p>Reference month: {quoteResult.ml_insights.knn_end_month}</p>
                  {quoteResult.ml_insights.cost_forecast_week_1 && (
                    <p>
                      Cost forecast (week 1): {formatPct(quoteResult.ml_insights.cost_forecast_week_1.mid)}
                      {' '}
                      ({formatPct(quoteResult.ml_insights.cost_forecast_week_1.lower)} - {formatPct(quoteResult.ml_insights.cost_forecast_week_1.upper)})
                    </p>
                  )}
                  {quoteResult.ml_insights.volume_forecast_week_1 && (
                    <p>
                      Volume forecast (week 1): {formatCurrency(quoteResult.ml_insights.volume_forecast_week_1.mid)}
                      {' '}
                      ({formatCurrency(quoteResult.ml_insights.volume_forecast_week_1.lower)} - {formatCurrency(quoteResult.ml_insights.volume_forecast_week_1.upper)})
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Business summary */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-lg font-medium text-gray-900 mb-6">Quote Summary</h3>
        
        <div className="grid md:grid-cols-2 gap-x-8 gap-y-4">
          <div>
            <p className="text-sm text-gray-500 mb-1">Business Name</p>
            <p className="text-gray-900 font-medium">{quoteResult.quote_summary.business_name}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Industry</p>
            <p className="text-gray-900 font-medium">{quoteResult.quote_summary.industry}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Average Ticket Size</p>
            <p className="text-gray-900 font-medium">{formatCurrency(quoteResult.quote_summary.average_ticket_size)}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Monthly Transactions</p>
            <p className="text-gray-900 font-medium">{quoteResult.quote_summary.monthly_transactions}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Quote Date</p>
            <p className="text-gray-900 font-medium">{quoteResult.quote_summary.quote_date}</p>
          </div>
        </div>
      </div>

      {/* Call to action */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Next Steps</h3>
        <p className="text-gray-600 mb-6">
          Ready to get started? Our team can help you set up your payment processing solution and answer any questions you may have about this quote.
        </p>
        
        <div className="flex flex-col sm:flex-row gap-4">
          <button className="flex-1 px-6 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition font-medium">
            Contact Sales Team
          </button>
          <button
            onClick={onStartOver}
            className="flex-1 px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium flex items-center justify-center"
          >
            <RotateCcw className="w-5 h-5 mr-2" />
            Start Over
          </button>
        </div>
      </div>
    </div>
  );
}