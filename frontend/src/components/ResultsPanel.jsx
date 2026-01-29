import React, { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button } from './ui/Button';

const ResultsPanel = ({ results, hasCurrentRate, onNewCalculation }) => {
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
            <h1 className="text-2xl font-semibold text-gray-900 flex-1 text-center">
              {hasCurrentRate ? 'Current Rates Results' : 'Quotation Results'}
            </h1>
            <div className="w-[140px]"></div>
          </div>
        )}

        {hasCurrentRate ? (
          // Layout when current rate is entered
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
                    ${results.estimatedProfit?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </div>

            {/* Expected ATS */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Expected ATS:</p>
              <p className="text-3xl font-bold text-gray-900">
                ${results.expectedATS?.toLocaleString('en-US')}
              </p>
            </div>

            {/* More Details Button */}
            <Button
              onClick={() => setShowMoreDetails(!showMoreDetails)}
              className="w-full"
            >
              {showMoreDetails ? 'Show Less' : 'More Details'}
            </Button>

            {/* Additional Details Section */}
            {showMoreDetails && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Additional Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Total Transactions</p>
                    <p className="text-xl font-semibold text-gray-900">{results.transactionCount || 0}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Expected Volume</p>
                    <p className="text-xl font-semibold text-gray-900">${results.expectedVolume?.toLocaleString('en-US')}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Suggested Rate</p>
                    <p className="text-xl font-semibold text-gray-900">{results.suggestedRate}%</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Quotable Range</p>
                    <p className="text-xl font-semibold text-gray-900">
                      {results.quotableRange?.min} - {results.quotableRange?.max}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          // Layout when no current rate (showing quotation results)
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column */}
            <div className="space-y-6">
              {/* Suggested Rate */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Suggested Rate:</p>
                <p className="text-4xl font-bold text-gray-900">{results.suggestedRate}%</p>
              </div>

              {/* Margin */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Margin (in bps):</p>
                <p className="text-4xl font-bold text-gray-900">{results.margin}</p>
              </div>

              {/* Estimated Profit */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <p className="text-sm font-medium text-gray-700 mb-2">Estimated Profit:</p>
                <p className="text-4xl font-bold text-gray-900">
                  ${results.estimatedProfit?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              {/* Range of Quotable Rates */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Range of Quotable Rates</h3>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Lower Bound:</span>
                    <span className="text-lg font-semibold text-gray-900">{results.quotableRange?.min}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Upper Bound:</span>
                    <span className="text-lg font-semibold text-gray-900">{results.quotableRange?.max}</span>
                  </div>
                </div>
              </div>

              {/* Expected Metrics */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Expected Metrics</h3>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-gray-600">Expected ATS</p>
                    <p className="text-xl font-semibold text-gray-900">${results.expectedATS?.toLocaleString('en-US')}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Expected Volume</p>
                    <p className="text-xl font-semibold text-gray-900">${results.expectedVolume?.toLocaleString('en-US')}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Adoption Probability</p>
                    <p className="text-xl font-semibold text-gray-900">{results.adoptionProbability}%</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResultsPanel;
