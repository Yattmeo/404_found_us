import React from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button } from './ui/Button';

const DesiredMarginResults = ({ results, onNewCalculation }) => {
  if (!results) {
    return null;
  }

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
          <div className="w-[140px]"></div>
        </div>

        {/* Results Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Suggested Rate */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Suggested Rate:</p>
              <p className="text-4xl font-bold text-gray-900">{results.suggestedRate}</p>
            </div>

            {/* Margin */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Margin:</p>
              <p className="text-4xl font-bold text-gray-900">{results.marginBps}</p>
            </div>

            {/* Estimated Profit */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Estimated Profit:</p>
              <p className="text-4xl font-bold text-gray-900">{results.estimatedProfit}</p>
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Range of Quotable Rates */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Range of Quotable Rates</h3>
              <div className="space-y-3">
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
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-sm text-gray-600">Expected ATS:</span>
                    <span className="text-lg font-semibold text-gray-900">{results.expectedATS}</span>
                  </div>
                  <div className="text-xs text-gray-500 text-right">
                    Margin of Error: ±{results.atsMarginError}
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-sm text-gray-600">Expected Volume:</span>
                    <span className="text-lg font-semibold text-gray-900">{results.expectedVolume}</span>
                  </div>
                  <div className="text-xs text-gray-500 text-right">
                    Margin of Error: ±{results.volumeMarginError}
                  </div>
                </div>
              </div>
            </div>

            {/* Merchant Data Summary */}
            {results.parsedData && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Merchant Data Summary</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Merchant ID:</span>
                    <span className="font-medium text-gray-900">{results.parsedData.merchantId}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">MCC:</span>
                    <span className="font-medium text-gray-900">{results.parsedData.mcc}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Transactions:</span>
                    <span className="font-medium text-gray-900">{results.parsedData.totalTransactions}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Amount:</span>
                    <span className="font-medium text-gray-900">
                      ${results.parsedData.totalAmount?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Average Ticket:</span>
                    <span className="font-medium text-gray-900">
                      ${results.parsedData.averageTicket?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DesiredMarginResults;
