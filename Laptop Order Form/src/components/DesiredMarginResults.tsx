import { ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, AreaChart, Area } from 'recharts';
import { useState } from 'react';

interface DesiredMarginResultsProps {
  results: {
    suggestedRate: string;
    marginBps: string;
    estimatedProfit: string;
    quotableRange: {
      min: string;
      max: string;
    };
    expectedATS: string;
    atsMarginError: string;
    expectedVolume: string;
    volumeMarginError: string;
    parsedData: {
      merchantId: string;
      mcc: string;
      totalTransactions: number;
      totalAmount: number;
      averageTicket: number;
    } | null;
  };
  onNewCalculation: () => void;
}

export function DesiredMarginResults({ results, onNewCalculation }: DesiredMarginResultsProps) {
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  // Mock data for volume distribution by ticket size - FIXED: starts at (0, 0) with no negatives
  const volumeDistributionData = [
    { ticketSize: 0, volume: 0 },
    { ticketSize: 10, volume: 0.50 },
    { ticketSize: 25, volume: 1.30 },
    { ticketSize: 50, volume: 2.20 },
    { ticketSize: 75, volume: 2.95 },
    { ticketSize: 100, volume: 3.75 },
    { ticketSize: 150, volume: 5.30 },
    { ticketSize: 200, volume: 6.70 },
    { ticketSize: 250, volume: 8.00 },
    { ticketSize: 300, volume: 9.25 },
    { ticketSize: 400, volume: 11.60 },
    { ticketSize: 500, volume: 13.75 },
  ];

  // Mock data for trend chart - UNCHANGED: should NOT start at (0, 0)
  const trendData = [
    { month: 'Jan', value: 58 },
    { month: 'Feb', value: 62 },
    { month: 'Mar', value: 61 },
    { month: 'Apr', value: 65 },
    { month: 'May', value: 64 },
    { month: 'Jun', value: 67 },
  ];

  // Mock data for profit distribution - FIXED: starts at (0, 0)
  const profitDistributionData = [
    { ticketSize: 0, volume: 0 },
    { ticketSize: 10, volume: 0.15 },
    { ticketSize: 25, volume: 0.40 },
    { ticketSize: 50, volume: 0.85 },
    { ticketSize: 75, volume: 1.35 },
    { ticketSize: 100, volume: 1.90 },
    { ticketSize: 150, volume: 3.10 },
    { ticketSize: 200, volume: 4.40 },
    { ticketSize: 250, volume: 5.75 },
    { ticketSize: 300, volume: 7.15 },
    { ticketSize: 400, volume: 10.00 },
    { ticketSize: 500, volume: 12.80 },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <button
            onClick={onNewCalculation}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium">New Calculation</span>
          </button>
          <h1 className="text-2xl font-semibold text-gray-900 flex-1 text-center">Desired Margin Results</h1>
          <div className="w-[140px]"></div> {/* Spacer for centering */}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Main Results */}
          <div className="space-y-6">
            {/* Suggested Rate */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-600 mb-2">Suggested Rate:</h3>
              <p className="text-3xl font-bold text-orange-600">{results.suggestedRate}</p>
            </div>

            {/* Margin in bps */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-600 mb-2">Margin (in bps):</h3>
              <p className="text-3xl font-bold text-gray-900">{results.marginBps}</p>
            </div>

            {/* Estimated Profit */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-600 mb-2">Estimated Profit:</h3>
              <p className="text-3xl font-bold text-green-600">{results.estimatedProfit}</p>
            </div>

            {/* Range of Quotable Rates */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-600 mb-3">Range of Quotable Rates:</h3>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Minimum</p>
                  <p className="text-xl font-bold text-gray-900">{results.quotableRange.min}</p>
                </div>
                <div className="flex-1 mx-4 h-2 bg-gradient-to-r from-orange-200 via-orange-400 to-orange-600 rounded-full"></div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Maximum</p>
                  <p className="text-xl font-bold text-gray-900">{results.quotableRange.max}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Distribution Chart */}
          <div className="space-y-6">
            {/* Distribution Chart - Increased Height */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-sm font-medium text-gray-900 mb-4">Volume Distribution</h3>
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={volumeDistributionData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis 
                    dataKey="ticketSize" 
                    label={{ value: 'Ticket Size ($)', position: 'insideBottom', offset: -5 }}
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis 
                    label={{ value: 'Volume of Transaction ($)', angle: -90, position: 'insideLeft' }}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip />
                  <Area 
                    type="monotone" 
                    dataKey="volume" 
                    stroke="#f97316" 
                    fill="#fed7aa"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* More Details Button - Full Width Below Grid */}
        <button
          onClick={() => setShowMoreDetails(!showMoreDetails)}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-2xl transition-all duration-200 shadow-md hover:shadow-lg font-medium mt-6"
        >
          <span>{showMoreDetails ? 'Show Less' : 'More Details'}</span>
          {showMoreDetails ? (
            <ChevronUp className="w-5 h-5" />
          ) : (
            <ChevronDown className="w-5 h-5" />
          )}
        </button>

        {/* Expandable More Details Section - Full Width */}
        {showMoreDetails && (
          <div className="mt-6 space-y-6 animate-fadeIn">
            {/* Expected ATS and Expected Volume - At the top of More Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Expected ATS:</h3>
                <p className="text-3xl font-bold text-gray-900 mb-2">{results.expectedATS}</p>
                <p className="text-sm text-gray-600">
                  Margin of error % for ATS: <span className="font-medium">{results.atsMarginError}</span>
                </p>
              </div>
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Expected Volume:</h3>
                <p className="text-3xl font-bold text-gray-900 mb-2">{results.expectedVolume}</p>
                <p className="text-sm text-gray-600">
                  Margin of error % for volume: <span className="font-medium">{results.volumeMarginError}</span>
                </p>
              </div>
            </div>

            {/* Transaction Summary */}
            {results.parsedData && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Transaction Summary</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Merchant ID</p>
                    <p className="text-lg font-semibold text-gray-900">{results.parsedData.merchantId}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">MCC Code</p>
                    <p className="text-lg font-semibold text-gray-900">{results.parsedData.mcc}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Total Transactions</p>
                    <p className="text-lg font-semibold text-gray-900">{results.parsedData.totalTransactions}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Average Ticket</p>
                    <p className="text-lg font-semibold text-gray-900">${results.parsedData.averageTicket.toFixed(2)}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Trend Chart - Full Width */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Volume Trend</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip />
                  <Line 
                    type="monotone" 
                    dataKey="value" 
                    stroke="#f97316" 
                    strokeWidth={3}
                    dot={{ fill: '#f97316', r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Additional Charts Grid - Full Width */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 md:col-span-2">
                <h3 className="text-sm font-medium text-gray-900 mb-4">Profit Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={profitDistributionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis 
                      dataKey="ticketSize" 
                      label={{ value: 'Average Ticket Size ($)', position: 'insideBottom', offset: -5 }}
                      tick={{ fontSize: 11 }}
                    />
                    <YAxis 
                      label={{ value: 'Profit per Transaction ($)', angle: -90, position: 'insideLeft' }}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip />
                    <Line 
                      type="monotone" 
                      dataKey="volume" 
                      stroke="#3b82f6" 
                      strokeWidth={2}
                      dot={{ fill: '#3b82f6', r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
