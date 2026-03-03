import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AlertCircle, Calculator } from 'lucide-react';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Label } from './ui/Label';

const ManualTransactionEntry = ({
  onValidDataConfirmed,
  showProceedButton = true,
  autoConfirm = false,
}) => {
  const [averageTicketSize, setAverageTicketSize] = useState('');
  const [monthlyTransactions, setMonthlyTransactions] = useState('');
  const [errors, setErrors] = useState({ averageTicketSize: '', monthlyTransactions: '' });
  const [estimatedVolume, setEstimatedVolume] = useState(0);
  const lastAutoConfirmedRef = useRef('');

  // Update estimated volume whenever inputs change
  useEffect(() => {
    const avg = parseFloat(averageTicketSize) || 0;
    const count = parseFloat(monthlyTransactions) || 0;
    setEstimatedVolume(avg * count);
  }, [averageTicketSize, monthlyTransactions]);

  // Updated formatter: keeps the $ sign but removes explicit currency code setting
  const formatCurrency = (value) => {
    return '$' + new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value);
  };

  const validateFields = () => {
    const newErrors = { averageTicketSize: '', monthlyTransactions: '' };
    let isValid = true;

    // Validate Average Ticket Size
    if (!averageTicketSize.trim()) {
      newErrors.averageTicketSize = 'Average ticket size is required';
      isValid = false;
    } else if (isNaN(parseFloat(averageTicketSize)) || parseFloat(averageTicketSize) <= 0) {
      newErrors.averageTicketSize = 'Please enter a valid positive number';
      isValid = false;
    }

    // Validate Monthly Transactions
    if (!monthlyTransactions.trim()) {
      newErrors.monthlyTransactions = 'Number of monthly transactions is required';
      isValid = false;
    } else if (isNaN(parseFloat(monthlyTransactions)) || parseFloat(monthlyTransactions) <= 0) {
      newErrors.monthlyTransactions = 'Please enter a valid positive number';
      isValid = false;
    } else if (!Number.isInteger(parseFloat(monthlyTransactions))) {
      newErrors.monthlyTransactions = 'Please enter a whole number';
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  const buildGeneratedData = useCallback(() => {
    const avgTicket = parseFloat(averageTicketSize);
    const numTransactions = parseInt(monthlyTransactions, 10);
    const today = new Date().toISOString().split('T')[0];

    return Array.from({ length: numTransactions }, (_, i) => ({
      transaction_id: `MANUAL_${String(i + 1).padStart(6, '0')}`,
      transaction_date: today,
      merchant_id: 'MANUAL_ENTRY',
      amount: avgTicket,
      transaction_type: 'Sale',
      card_type: 'Unknown'
    }));
  }, [averageTicketSize, monthlyTransactions]);

  const handleProceed = () => {
    if (validateFields()) {
      onValidDataConfirmed(buildGeneratedData());
    }
  };

  useEffect(() => {
    if (!autoConfirm) {
      return;
    }

    const avg = parseFloat(averageTicketSize);
    const count = parseFloat(monthlyTransactions);
    const countInt = parseInt(monthlyTransactions, 10);

    const isValid =
      averageTicketSize.trim() !== '' &&
      monthlyTransactions.trim() !== '' &&
      !isNaN(avg) &&
      avg > 0 &&
      !isNaN(count) &&
      count > 0 &&
      Number.isInteger(count) &&
      countInt > 0;

    if (!isValid) {
      return;
    }

    const signature = `${averageTicketSize}|${monthlyTransactions}`;
    if (lastAutoConfirmedRef.current === signature) {
      return;
    }

    lastAutoConfirmedRef.current = signature;
    onValidDataConfirmed(buildGeneratedData());
  }, [averageTicketSize, monthlyTransactions, autoConfirm, onValidDataConfirmed, buildGeneratedData]);

  const handleAverageTicketSizeChange = (e) => {
    const value = e.target.value;
    // Allow only numbers and decimal point
    if (value === '' || /^\d*\.?\d*$/.test(value)) {
      setAverageTicketSize(value);
      if (errors.averageTicketSize) {
        setErrors({ ...errors, averageTicketSize: '' });
      }
    }
  };

  const handleMonthlyTransactionsChange = (e) => {
    const value = e.target.value;
    // Allow only whole numbers
    if (value === '' || /^\d+$/.test(value)) {
      setMonthlyTransactions(value);
      if (errors.monthlyTransactions) {
        setErrors({ ...errors, monthlyTransactions: '' });
      }
    }
  };

  const hasValidData = averageTicketSize.trim() !== '' && monthlyTransactions.trim() !== '';

  return (
    <div className="space-y-6 max-w-xl mx-auto py-4">
      <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="bg-green-100 p-2 rounded-lg">
            <Calculator className="w-6 h-6 text-[#22C55E]" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Merchant Profile Estimation</h3>
            <p className="text-sm text-gray-500">Enter average values to simulate transaction data</p>
          </div>
        </div>

        <div className="space-y-6">
          {/* Average Transaction Value */}
          <div>
            <Label htmlFor="averageTicketSize" className="text-base font-medium text-gray-700 mb-2">
              Average Transaction Value <span className="text-red-500">*</span>
            </Label>
            <div className="relative mt-1">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">$</span>
              <Input
                id="averageTicketSize"
                type="text"
                value={averageTicketSize}
                onChange={handleAverageTicketSizeChange}
                placeholder="100.00"
                className={`pl-8 py-3 text-lg ${
                  errors.averageTicketSize ? 'border-red-300 focus:ring-red-200' : ''
                }`}
              />
            </div>
            {errors.averageTicketSize && (
              <p className="mt-1 text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {errors.averageTicketSize}
              </p>
            )}
          </div>

          {/* Monthly Transactions */}
          <div>
            <Label htmlFor="monthlyTransactions" className="text-base font-medium text-gray-700 mb-2">
              Monthly Transactions (Count) <span className="text-red-500">*</span>
            </Label>
            <Input
              id="monthlyTransactions"
              type="text"
              value={monthlyTransactions}
              onChange={handleMonthlyTransactionsChange}
              placeholder="e.g. 500"
              className={`py-3 text-lg ${
                errors.monthlyTransactions ? 'border-red-300 focus:ring-red-200' : ''
              }`}
            />
            {errors.monthlyTransactions && (
              <p className="mt-1 text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {errors.monthlyTransactions}
              </p>
            )}
          </div>
        </div>

        {/* Estimated Monthly Volume Display */}
        {hasValidData && (
          <div className="mt-8 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-100 rounded-xl p-6">
            <p className="text-sm font-medium text-green-800 uppercase tracking-wide mb-1">
              Estimated Monthly Volume
            </p>
            <p className="text-3xl font-bold text-[#22C55E]">
              {formatCurrency(estimatedVolume)}
            </p>
            <p className="text-xs text-green-700 mt-2">
              Based on {parseInt(monthlyTransactions).toLocaleString()} transactions at {formatCurrency(parseFloat(averageTicketSize))} avg.
            </p>
          </div>
        )}

        {/* Proceed Button */}
        {showProceedButton && (
          <div className="mt-8">
            <Button
              type="button"
              onClick={handleProceed}
              disabled={!hasValidData}
              className="w-full h-12 text-lg font-medium shadow-md transition-all hover:shadow-lg disabled:opacity-50 disabled:shadow-none"
            >
              Generate & Proceed
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ManualTransactionEntry;