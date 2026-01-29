import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';

interface ResultsPanelProps {
  results: any;
  hasCurrentRate: boolean;
  onNewCalculation?: () => void;
}

export function ResultsPanel({ results, hasCurrentRate, onNewCalculation }: ResultsPanelProps) {
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  if (!results) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-center h-full min-h-[400px] text-gray-400">
          <p>Submit the form to see results</p>
        </div>
      </div>
    );
  }

  // Mock data for the distribution charts
  const profitDistribution = [
    { value: 0, frequency: 2 },
    { value: 5, frequency: 8 },
    { value: 10, frequency: 15 },
    { value: 15, frequency: 25 },
    { value: 20, frequency: 35 },
    { value: 25, frequency: 45 },
    { value: 30, frequency: 38 },
    { value: 35, frequency: 28 },
    { value: 40, frequency: 18 },
    { value: 45, frequency: 10 },
    { value: 50, frequency: 5 },
  ];

  const volumeDistribution = [
    { value: 1.5, frequency: 84 },
    { value: 1.75, frequency: 88 },
    { value: 2.0, frequency: 90 },
    { value: 2.25, frequency: 92 },
    { value: 2.5, frequency: 93.5 },
    { value: 2.75, frequency: 94 },
    { value: 3.0, frequency: 94.5 },
    { value: 3.25, frequency: 95 },
    { value: 3.5, frequency: 98 },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header with New Calculation Button */}
        {onNewCalculation && (
          <div className="mb-8 flex items-center justify-between">
            <button 
              onClick={onNewCalculation}
              className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="font-medium">New Calculation</span>
            </button>
            <h1 className="text-2xl font-semibold text-gray-900 flex-1 text-center">Current Rates Results</h1>
            <div className="w-[140px]"></div> {/* Spacer for centering */}
          </div>
        )}

        {/* Layout depends on whether current rate was provided */}
        {hasCurrentRate ? (
          // LAYOUT WHEN CURRENT RATE IS ENTERED (Image 1 - Right Side)
          <div className="space-y-6">
            {/* Blue box with profitability metrics */}
            <div className="bg-blue-50 rounded-2xl p-6 border border-blue-100 shadow-sm">
              <div className="space-y-3">
                <div>
                  <p className="text-sm font-medium text-gray-700">% of profitability:</p>
                  <p className="text-2xl font-bold text-gray-900">{results.profitability}%</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Margin (in bps):</p>
                  <p className="text-2xl font-bold text-gray-900">{results.margin}</p>
                </div>
                
                <div>
                  <p className="text-sm font-medium text-gray-700">Estimated Profit:</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ${results.estimatedProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </div>

            {/* Expected ATS */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Expected ATS:</p>
              <p className="text-3xl font-bold text-gray-900">
                ${results.expectedATS.toLocaleString('en-US')}
              </p>
            </div>

            {/* Distribution Chart */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Profit Distribution</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={profitDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="value" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="frequency" fill="#f97316" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* More Details Button */}
            <button
              onClick={() => setShowMoreDetails(!showMoreDetails)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white rounded-2xl transition-all duration-200 shadow-md hover:shadow-lg font-medium"
            >
              {showMoreDetails ? 'Show Less' : 'More Details'}
            </button>

            {/* Additional Details Section */}
            {showMoreDetails && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Additional Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Total Transactions</p>
                    <p className="text-xl font-semibold text-gray-900">1,234</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Average Transaction Size</p>
                    <p className="text-xl font-semibold text-gray-900">$156.78</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Processing Volume</p>
                    <p className="text-xl font-semibold text-gray-900">$193,467</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Suggested Rate</p>
                    <p className="text-xl font-semibold text-gray-900">2.65%</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          // LAYOUT WHEN NO CURRENT RATE (Image 2 - Left Side)
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-6">
              {/* Suggested Rate */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Suggested Rate </h3>
                <p className="text-3xl font-bold text-orange-600">{results.suggestedRate}%</p>
              </div>

              {/* Margin in bps */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Margin (in bps):</h3>
                <p className="text-3xl font-bold text-gray-900">{results.margin}</p>
              </div>

              {/* Estimated Profit */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Estimated Profit:</h3>
                <p className="text-3xl font-bold text-green-600">${results.estimatedProfit}</p>
              </div>

              {/* Range of Quotable Rates */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-3">Range of Quotable Rates:</h3>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Minimum</p>
                    <p className="text-xl font-bold text-gray-900">1.5%</p>
                  </div>
                  <div className="flex-1 mx-4 h-2 bg-gradient-to-r from-orange-200 via-orange-400 to-orange-600 rounded-full"></div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Maximum</p>
                    <p className="text-xl font-bold text-gray-900">3.5%</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Expected ATS */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-sm font-medium text-gray-600 mb-2">Expected ATS:</h3>
                <p className="text-3xl font-bold text-gray-900">${results.expectedATS}</p>
              </div>

              {/* Volume Distribution Chart */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Probability of Profitability</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={volumeDistribution}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis 
                      dataKey="value" 
                      label={{ value: 'Rate (%)', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis 
                      label={{ value: 'Probability of profitability ($)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip />
                    <Line 
                      type="monotone" 
                      dataKey="frequency" 
                      stroke="#f97316" 
                      strokeWidth={3}
                      dot={{ fill: '#f97316', r: 4 }}
                      activeDot={{ r: 6 }}
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