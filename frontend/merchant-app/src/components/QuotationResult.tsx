import { Download, RotateCcw } from 'lucide-react';
import { BusinessData, QuoteResult } from '../App';

interface QuotationResultProps {
  businessData: BusinessData;
  quoteResult: QuoteResult;
  onStartOver: () => void;
}

export function QuotationResult({ businessData, quoteResult, onStartOver }: QuotationResultProps) {
  const handlePrint = () => {
    window.print();
  };

  // Calculate example costs for $100 purchase
  const exampleAmount = 100;
  const inPersonRate = quoteResult.transactionFee;
  const onlineRate = quoteResult.transactionFee + 0.3; // Online typically higher
  
  const inPersonCost = Math.round((exampleAmount * inPersonRate) / 100 * 100); // in cents
  const onlineCost = Math.round((exampleAmount * onlineRate) / 100 * 100); // in cents

  // Format cost display (cents vs dollars)
  const formatCost = (cents: number) => {
    if (cents > 100) {
      return `$${(cents / 100).toFixed(2)}`;
    }
    return `${cents} ¢`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h2 className="text-gray-900 mb-2">Your Payment Processing Quote</h2>
        <p className="text-gray-600">
          Quote prepared for <span className="font-semibold">{businessData.businessName}</span>
        </p>
      </div>

      {/* Main pricing table */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-gray-900 mb-1">Your rates</h3>
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
                <td className="py-3 px-4 text-sm text-gray-900">2.3-2.5%</td>
              </tr>
              <tr className="border-b border-gray-200">
                <td className="py-3 px-4 text-sm text-gray-900">Cards online or by phone</td>
                <td className="py-3 px-4 text-sm text-gray-900">2.4-2.6%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Other potential transaction charges */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-gray-900 mb-6">Other potential transaction charges</h3>
        
        <div className="grid md:grid-cols-2 gap-4">
          <div className="border border-gray-300 rounded p-4">
            <p className="text-sm text-gray-700 mb-1">Chargeback fee</p>
            <p className="text-2xl font-semibold text-gray-900">$25</p>
          </div>
        </div>
      </div>

      {/* Two column layout for monthly charges and other details */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Other monthly charges */}
        <div className="bg-white rounded-lg shadow p-6 md:p-8">
          <h3 className="text-gray-900 mb-6">Other monthly charges</h3>
          
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-gray-200">
              <p className="text-sm text-gray-700">Point-of-sale terminal (per terminal per month)</p>
              <p className="text-sm font-semibold text-gray-900">$25</p>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-gray-200">
              <p className="text-sm text-gray-700">Gateway charge</p>
              <p className="text-sm font-semibold text-gray-900">$16</p>
            </div>
          </div>
        </div>

        {/* Other details */}
        <div className="bg-white rounded-lg shadow p-6 md:p-8">
          <h3 className="text-gray-900 mb-6">Other details</h3>
          
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-500 mb-2">Payment brands accepted</p>
              <div className="flex flex-wrap gap-2">
                <span className="px-3 py-1 bg-orange-100 text-orange-800 text-xs font-medium rounded">Visa</span>
                <span className="px-3 py-1 bg-orange-100 text-orange-800 text-xs font-medium rounded">Mastercard</span>
                <span className="px-3 py-1 bg-orange-100 text-orange-800 text-xs font-medium rounded">American Express</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Business summary */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-gray-900 mb-6">Quote Summary</h3>
        
        <div className="grid md:grid-cols-2 gap-x-8 gap-y-4">
          <div>
            <p className="text-sm text-gray-500 mb-1">Business Name</p>
            <p className="text-gray-900 font-medium">{businessData.businessName}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Industry</p>
            <p className="text-gray-900 font-medium capitalize">{businessData.industry.replace('-', ' ')}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Average Transaction</p>
            <p className="text-gray-900 font-medium">${parseFloat(businessData.averageTransactionValue).toFixed(2)}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Monthly Transactions</p>
            <p className="text-gray-900 font-medium">{businessData.monthlyTransactions}</p>
          </div>

          <div>
            <p className="text-sm text-gray-500 mb-1">Quote Date</p>
            <p className="text-gray-900 font-medium">{new Date().toLocaleDateString('en-GB')}</p>
          </div>
        </div>
      </div>

      {/* Call to action */}
      <div className="bg-white rounded-lg shadow p-6 md:p-8">
        <h3 className="text-gray-900 mb-4">Next Steps</h3>
        <p className="text-gray-600 mb-6">
          Ready to get started? Our team can help you set up your payment processing solution and answer any questions you may have about this quote.
        </p>
        
        <div className="flex flex-col sm:flex-row gap-4">
          <button className="flex-1 px-6 py-3 bg-[#6CAFF3] text-white rounded-lg hover:bg-[#5B9FED] transition font-medium">
            Contact Sales Team
          </button>
          <button
            onClick={handlePrint}
            className="flex-1 px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition font-medium flex items-center justify-center"
          >
            <Download className="w-5 h-5 mr-2" />
            Download Quote
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