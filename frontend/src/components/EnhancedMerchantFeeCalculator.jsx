import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { ArrowLeft } from 'lucide-react';
import ResultsPanel from './ResultsPanel';
import DataUploadValidator from './DataUploadValidator';
import ManualTransactionEntry from './ManualTransactionEntry';
import MCCDropdown from './MCCDropdown';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/Tabs';
import { Button } from './ui/Button';
import { Label } from './ui/Label';
import { Input } from './ui/Input';
import { merchantFeeAPI, desiredMarginAPI } from '../services/api';

const EnhancedMerchantFeeCalculator = ({ onBackToLanding }) => {
  const [results, setResults] = useState(null);
  const [dataValidated, setDataValidated] = useState(false);
  const [transactionData, setTransactionData] = useState([]);
  const [activeTab, setActiveTab] = useState('upload');
  const [isLoading, setIsLoading] = useState(false);
  
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm();

  const feeStructure = watch('feeStructure');
  const currentRate = watch('currentRate');
  const mccValue = watch('mcc');
  const fixedFee = watch('fixedFee');

  const clampProfitabilityPct = (value) => {
    if (!Number.isFinite(value)) return null;
    return Number(Math.max(-100, Math.min(100, value)).toFixed(2));
  };

  const normalizeCurrentRateResults = (apiPayload, formData, txCount, avgTicket, totalAmount) => {
    const envelope = apiPayload || {};
    const data = envelope?.data || {};
    const suggestedRate = typeof data?.applied_rate === 'number' ? data.applied_rate * 100 : null;
    const marginBps = typeof data?.margin_bps === 'number' ? data.margin_bps : null;

    const transactionCountForProfit =
      typeof data?.transaction_count === 'number' ? data.transaction_count : txCount;
    const fixedFeePerTxn =
      typeof data?.fixed_fee === 'number'
        ? data.fixed_fee
        : (formData.fixedFee !== '' && formData.fixedFee !== undefined ? Number(formData.fixedFee) : 0.30);

    const variableProfit =
      typeof data?.margin_rate === 'number' && typeof data?.total_volume === 'number'
        ? data.total_volume * data.margin_rate
        : null;
    const fixedFeeContribution =
      typeof transactionCountForProfit === 'number' && Number.isFinite(fixedFeePerTxn)
        ? transactionCountForProfit * fixedFeePerTxn
        : 0;

    // Include both rate margin and fixed-fee contribution so profit mapping matches user inputs.
    const estimatedProfit =
      typeof variableProfit === 'number' ? variableProfit + fixedFeeContribution : null;
    const estimatedProfitMin = typeof estimatedProfit === 'number' ? estimatedProfit * 0.9 : null;
    const estimatedProfitMax = typeof estimatedProfit === 'number' ? estimatedProfit * 1.1 : null;

    const transactionSummary = {
      transaction_count: typeof data?.transaction_count === 'number' ? data.transaction_count : txCount,
      total_volume: typeof data?.total_volume === 'number' ? data.total_volume : totalAmount,
      average_ticket: typeof data?.average_ticket === 'number' ? data.average_ticket : avgTicket,
    };

    const processingVolume =
      typeof transactionSummary.monthly_volume === 'number' && transactionSummary.monthly_volume > 0
        ? transactionSummary.monthly_volume
        : typeof transactionSummary.total_volume === 'number'
        ? transactionSummary.total_volume
        : (typeof data?.calculation?.total_volume === 'number' ? data.calculation.total_volume : totalAmount);

    let profitabilityPct = null;
    const totalFees = typeof data?.total_fees === 'number' ? data.total_fees : null;
    if (
      typeof estimatedProfitMin === 'number' &&
      typeof estimatedProfitMax === 'number' &&
      typeof totalFees === 'number' &&
      totalFees > 0
    ) {
      const midpointProfit = (estimatedProfitMin + estimatedProfitMax) / 2;
      profitabilityPct = clampProfitabilityPct((midpointProfit / totalFees) * 100);
    }

    const averageTransactionSize =
      typeof transactionSummary.average_ticket === 'number'
        ? transactionSummary.average_ticket
        : (typeof data?.calculation?.average_ticket === 'number' ? data.calculation.average_ticket : avgTicket);

    const transactionCount =
      typeof transactionSummary.transaction_count === 'number'
        ? transactionSummary.transaction_count
        : (typeof data?.calculation?.transaction_count === 'number' ? data.calculation.transaction_count : txCount);

    return {
      suggestedRate,
      margin: marginBps,
      estimatedProfit,
      estimatedProfitMin,
      estimatedProfitMax,
      expectedATS: averageTransactionSize,
      expectedVolume: processingVolume,
      adoptionProbability: null,
      profitability: profitabilityPct,
      targetMarginMet: null,
      quotableRange: {
        min: suggestedRate !== null ? Math.max(0, Number((suggestedRate - 0.1).toFixed(2))) : null,
        max: suggestedRate !== null ? Number((suggestedRate + 0.1).toFixed(2)) : null,
      },
      processingVolume,
      averageTransactionSize,
      transactionCount,
      currentRateProvided: !!formData.currentRate,
      costForecast: [],
      volumeForecast: [],
      profitabilityCurve: [],
      mlContext: null,
      transactionSummary,
      calculation: data,
    };
  };

  const normalizeRangeResults = (apiPayload, formData, txCount, avgTicket, totalAmount) => {
    const envelope = apiPayload || {};
    const data = envelope?.data || {};
    const summary = data?.summary || {};
    const calculation = data?.calculation || {};
    const transactionSummary = data?.transaction_summary || {};
    const profitabilityCurve = Array.isArray(data?.profitability_curve) ? data.profitability_curve : [];
    const volumeForecast = Array.isArray(data?.volume_forecast) ? data.volume_forecast : [];

    let suggestedRate = typeof summary.suggested_rate_pct === 'number' ? summary.suggested_rate_pct : null;
    if (suggestedRate === null && typeof calculation?.recommended_rate === 'number') {
      suggestedRate = calculation.recommended_rate * 100;
    }

    let marginBps = typeof summary.margin_bps === 'number' ? summary.margin_bps : null;
    if (
      marginBps === null &&
      typeof calculation?.recommended_rate === 'number' &&
      typeof calculation?.base_cost_rate === 'number'
    ) {
      marginBps = Math.round((calculation.recommended_rate - calculation.base_cost_rate) * 10000);
    }

    let estimatedProfitMin = typeof summary.estimated_profit_min === 'number' ? summary.estimated_profit_min : null;
    let estimatedProfitMax = typeof summary.estimated_profit_max === 'number' ? summary.estimated_profit_max : null;
    if (
      (estimatedProfitMin === null || estimatedProfitMax === null) &&
      typeof calculation?.estimated_total_fees === 'number'
    ) {
      estimatedProfitMin = calculation.estimated_total_fees * 0.9;
      estimatedProfitMax = calculation.estimated_total_fees * 1.1;
    }

    // Prefer TPV forecast average monthly volume for display ("Expected Annual Volume").
    // total_volume is the sum of ALL historical transactions which can span many years
    // and would wildly overstate monthly volume when multiplied by 12.
    const forecastMonthlyAvg = volumeForecast.length > 0
      ? volumeForecast.reduce((s, p) => {
          const mid = Number(p?.mid);
          return Number.isFinite(mid) && mid > 0 ? s + mid : s;
        }, 0) / volumeForecast.length
      : 0;

    const processingVolume = forecastMonthlyAvg > 0
      ? forecastMonthlyAvg
      : typeof transactionSummary.monthly_volume === 'number' && transactionSummary.monthly_volume > 0
        ? transactionSummary.monthly_volume
        : typeof transactionSummary.total_volume === 'number'
        ? transactionSummary.total_volume
        : (typeof data?.calculation?.total_volume === 'number' ? data.calculation.total_volume : totalAmount);

    const forecastHorizonVolume = volumeForecast.reduce((sum, point) => {
      const mid = Number(point?.mid);
      return Number.isFinite(mid) && mid > 0 ? sum + mid : sum;
    }, 0);

    const profitabilityDenominator = forecastHorizonVolume > 0 ? forecastHorizonVolume : processingVolume;

    let profitabilityPct = null;
    if (typeof summary?.profitability_pct === 'number') {
      profitabilityPct = clampProfitabilityPct(summary.profitability_pct);
    } else if (
      typeof estimatedProfitMin === 'number' &&
      typeof estimatedProfitMax === 'number' &&
      typeof profitabilityDenominator === 'number' &&
      profitabilityDenominator > 0
    ) {
      const midpointProfit = (estimatedProfitMin + estimatedProfitMax) / 2;
      profitabilityPct = clampProfitabilityPct((midpointProfit / profitabilityDenominator) * 100);
    }

    const averageTransactionSize =
      typeof transactionSummary.average_ticket === 'number'
        ? transactionSummary.average_ticket
        : (typeof data?.calculation?.average_ticket === 'number' ? data.calculation.average_ticket : avgTicket);

    const transactionCount =
      typeof transactionSummary.transaction_count === 'number'
        ? transactionSummary.transaction_count
        : (typeof data?.calculation?.transaction_count === 'number' ? data.calculation.transaction_count : txCount);

    return {
      suggestedRate,
      margin: marginBps,
      estimatedProfit: estimatedProfitMin,
      estimatedProfitMin,
      estimatedProfitMax,
      expectedATS: averageTransactionSize,
      expectedVolume: processingVolume,
      adoptionProbability: null,
      profitability: profitabilityPct,
      targetMarginMet: summary.target_margin_met ?? null,
      quotableRange: {
        min: suggestedRate !== null ? Math.max(0, Number((suggestedRate - 0.1).toFixed(2))) : null,
        max: suggestedRate !== null ? Number((suggestedRate + 0.1).toFixed(2)) : null,
      },
      processingVolume,
      averageTransactionSize,
      transactionCount,
      currentRateProvided: !!formData.currentRate,
      costForecast: Array.isArray(data?.cost_forecast) ? data.cost_forecast : [],
      volumeForecast,
      profitabilityCurve,
      mlContext: data?.ml_context || null,
      transactionSummary,
      calculation,
    };
  };

  const computeTransactionMetrics = (input) => {
    if (Array.isArray(input)) {
      const txCount = input.length;
      const totalAmount = input.reduce((sum, t) => sum + parseFloat(t.amount || 0), 0);
      const avgTicket = txCount > 0 ? totalAmount / txCount : 0;

      // Estimate monthly tx count from the date range so the backend
      // receives a realistic per-month figure, not the raw CSV row count.
      let monthlyTxCount = txCount;
      if (txCount >= 2) {
        const firstDateStr = input[0]?.transaction_date || input[0]?.date;
        const lastDateStr = input[txCount - 1]?.transaction_date || input[txCount - 1]?.date;
        if (firstDateStr && lastDateStr) {
          const d0 = new Date(firstDateStr);
          const d1 = new Date(lastDateStr);
          if (!isNaN(d0) && !isNaN(d1)) {
            const spanMonths = Math.max(1, Math.abs(d1 - d0) / (30.44 * 24 * 60 * 60 * 1000));
            monthlyTxCount = Math.round(txCount / spanMonths);
          }
        }
      }

      const monthlyVolume = monthlyTxCount * avgTicket;
      return { txCount: monthlyTxCount, totalAmount: monthlyVolume, avgTicket };
    }

    const txCount = Number(input?.totalTransactions || 0);
    const totalAmount = Number(input?.totalAmount || 0);
    const avgTicket = Number(input?.averageTicket || (txCount > 0 ? totalAmount / txCount : 0));
    return { txCount, totalAmount, avgTicket };
  };

  const handleDataValidated = (data, mcc) => {
    setTransactionData(data);
    setDataValidated(true);
    if (mcc) {
      setValue('mcc', mcc);
    }
  };

  const onSubmit = async (data) => {
    setIsLoading(true);
    try {
      const { txCount, totalAmount, avgTicket } = computeTransactionMetrics(transactionData);

      const hasCurrentRate = data.currentRate !== '' && data.currentRate !== undefined;

      // Send raw transaction rows so the ML service sees real variance
      const rawTransactions = Array.isArray(transactionData) ? transactionData : [];

      const fixedFeeValue = data.fixedFee === '' || data.fixedFee === undefined || data.fixedFee === null
        ? 0.0
        : parseFloat(data.fixedFee);
      const currentRateValue = hasCurrentRate ? parseFloat(data.currentRate) / 100 : null;

      // Always use the desired-margin-details endpoint so that ML
      // forecasting (M9 cost forecast + SARIMA volume forecast) is
      // available for both the profitability calculator and quotation tool.
      const quotePayload = {
        mcc: data.mcc,
        fixed_fee: Number.isFinite(fixedFeeValue) ? fixedFeeValue : 0.0,
        desired_margin: 0.015,
        transactions: rawTransactions,
      };

      if (hasCurrentRate) {
        // Pass through the current rate so the backend uses it as the
        // recommended rate instead of computing one from desired_margin.
        quotePayload.current_rate = currentRateValue;
      }

      const apiResults = await desiredMarginAPI.getDesiredMarginDetails(quotePayload);
      setResults(normalizeRangeResults(apiResults, data, txCount, avgTicket, totalAmount));
    } catch (error) {
      console.error('Calculation error:', error);
      const { txCount, totalAmount, avgTicket } = computeTransactionMetrics(transactionData);

      if (!(data.currentRate !== '' && data.currentRate !== undefined)) {
        try {
          const fixedFeeFallback =
            data.fixedFee === '' || data.fixedFee === undefined || data.fixedFee === null
              ? 0.0
              : parseFloat(data.fixedFee);

          const fallbackPayload = {
            mcc: data.mcc,
            fixed_fee: Number.isFinite(fixedFeeFallback) ? fixedFeeFallback : 0.0,
            current_rate: null,
            transactions: Array.isArray(transactionData) ? transactionData : [],
          };

          const fallbackApiResults = await merchantFeeAPI.calculateCurrentRates(fallbackPayload);
          setResults(normalizeCurrentRateResults(fallbackApiResults, data, txCount, avgTicket, totalAmount));
          return;
        } catch (fallbackError) {
          console.error('Fallback current-rate calculation error:', fallbackError);
        }
      }

      // Last-resort UI fallback with transaction-derived values only.
      
      const mockResults = {
        suggestedRate: null, // Backend should calculate based on MCC, volume, and desired margin
        margin: null, // Backend should calculate margin in bps
        estimatedProfit: null, // Backend should calculate based on rate and volume
        expectedATS: null, // Backend should predict based on transaction patterns
        expectedVolume: null, // Backend should predict based on historical data
        quotableRange: {
          min: null, // Backend should calculate lower bound
          max: null // Backend should calculate upper bound
        },
        adoptionProbability: null, // Backend ML model should predict
        profitability: data.currentRate ? null : null, // Backend should calculate if current rate provided
        
        // Dynamic values from actual transaction data
        processingVolume: totalAmount,
        averageTransactionSize: avgTicket,
        transactionCount: txCount,
        currentRateProvided: !!data.currentRate,
        
        // Backend should provide profitDistribution array for chart
        // profitDistribution: [{ value: number, label: string }, ...]
      };
      setResults(mockResults);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewCalculation = () => {
    setResults(null);
    setDataValidated(false);
    setTransactionData([]);
    reset();
  };

  // Show results page if results exist
  if (results) {
    return <ResultsPanel results={results} hasCurrentRate={!!currentRate} currentRateInput={currentRate} onNewCalculation={handleNewCalculation} />;
  }

  // Show form page
  return (
    <div className="min-h-screen bg-[#E8F5F0] flex items-center justify-center p-8">
      <div className="w-full max-w-6xl">
        {/* Back Button */}
        <button
          onClick={onBackToLanding}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-800 transition-colors mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          <span className="font-medium">Back to Home</span>
        </button>

        {/* Split Layout Container */}
        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-5">
          {/* Left Panel - Green Branding */}
          <div className="lg:col-span-2 bg-gradient-to-br from-[#22C55E] to-[#16A34A] p-12 flex flex-col justify-between relative overflow-hidden">
            {/* Decorative circles */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2"></div>
            
            <div className="relative z-10">
              {/* Title */}
              <h1 className="text-4xl font-bold text-white mb-4">
                Merchant Profitability Calculator
              </h1>
              <p className="text-green-50 text-lg leading-relaxed">
                Assess profitability based on current merchant rates and transaction data. Upload your data or enter it manually to get started.
              </p>
            </div>

            {/* Image */}
            <div className="relative z-10 mt-8">
              <img 
                src="https://images.unsplash.com/photo-1762319007311-31597c44aad8?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxmaW5hbmNpYWwlMjBjYWxjdWxhdG9yJTIwYnVzaW5lc3N8ZW58MXx8fHwxNzY4NzA4MzU1fDA&ixlib=rb-4.1.0&q=80&w=1080"
                alt="Financial Calculator"
                className="rounded-2xl shadow-xl opacity-90"
              />
            </div>
          </div>

          {/* Right Panel - Form */}
          <div className="lg:col-span-3 p-12">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              {/* Step 1: Data Input */}
              {!dataValidated && (
                <div className="space-y-4">
                  <div>
                    <h2 className="text-xl font-semibold text-gray-800 mb-1">
                      Step 1: Transaction Data
                    </h2>
                    <p className="text-sm text-gray-600">
                      Upload a CSV file or enter transactions manually
                    </p>
                  </div>

                  <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList>
                      <TabsTrigger value="upload">Upload CSV</TabsTrigger>
                      <TabsTrigger value="manual">Manual Entry</TabsTrigger>
                    </TabsList>
                    
                    <TabsContent value="upload">
                      <DataUploadValidator 
                        onValidDataConfirmed={handleDataValidated}
                        onMCCExtracted={(mcc) => setValue('mcc', mcc)}
                      />
                    </TabsContent>
                    
                    <TabsContent value="manual">
                      <ManualTransactionEntry 
                        onValidDataConfirmed={(data) => handleDataValidated(data)}
                      />
                    </TabsContent>
                  </Tabs>
                </div>
              )}

              {/* Step 2: Fee Configuration */}
              {dataValidated && (
                <>
                  <div className="pb-4 border-b border-gray-200">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-xl font-semibold text-gray-900 mb-1">
                          Step 2: Fee Configuration
                        </h2>
                        <p className="text-sm text-gray-600">
                          {transactionData.length} transaction(s) validated
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setDataValidated(false)}
                        className="text-sm text-[#22C55E] hover:text-[#16A34A] font-medium"
                      >
                        Edit Data
                      </button>
                    </div>
                  </div>

                  {/* Merchant Category Code */}
                  <div>
                    <Label htmlFor="mcc">Merchant Category Code (MCC)</Label>
                    <MCCDropdown
                      value={mccValue}
                      onChange={(value) => setValue('mcc', value)}
                      error={errors.mcc?.message}
                    />
                    <input
                      type="hidden"
                      {...register('mcc', { required: 'MCC is required' })}
                    />
                  </div>

                  {/* Preferred Fee Structure */}
                  <div>
                    <Label htmlFor="feeStructure">Preferred Fee Structure</Label>
                    <select
                      id="feeStructure"
                      {...register('feeStructure', { required: 'Please select a fee structure' })}
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[#22C55E] focus:border-[#22C55E] bg-white"
                    >
                      <option value="">Select structure</option>
                      <option value="percentage">% (Percentage only)</option>
                      <option value="percentage-fixed">% + Fixed Fee</option>
                      <option value="fixed">Fixed Fee</option>
                    </select>
                    {errors.feeStructure && (
                      <p className="mt-1 text-sm text-red-600">{errors.feeStructure.message}</p>
                    )}
                  </div>

                  {/* Fixed Fee - Conditional: Only for % + Fixed Fee */}
                  {feeStructure === 'percentage-fixed' && (
                    <div>
                      <Label htmlFor="fixedFee">Fixed Fee <span className="text-gray-500 font-normal">(Optional)</span></Label>
                      <div className="relative">
                        <Input
                          id="fixedFee"
                          type="number"
                          step="0.01"
                          min="0"
                          {...register('fixedFee', {
                            min: { value: 0, message: 'Fixed fee cannot be negative' }
                          })}
                          placeholder="Enter fixed fee"
                          className={fixedFee ? 'pl-8' : ''}
                        />
                        {fixedFee && (
                          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                        )}
                      </div>
                      {errors.fixedFee && (
                        <p className="mt-1 text-sm text-red-600">{errors.fixedFee.message}</p>
                      )}
                    </div>
                  )}

                  {/* Current Rate */}
                  <div>
                    <Label htmlFor="currentRate">Current Rate <span className="text-gray-500 font-normal">(Optional)</span></Label>
                    <div className="relative">
                      <Input
                        id="currentRate"
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        {...register('currentRate', {
                          min: { value: 0, message: 'Rate cannot be negative' },
                          max: { value: 100, message: 'Rate cannot exceed 100%' },
                          validate: (value) => !value || (parseFloat(value) >= 0 && parseFloat(value) <= 100) || 'Rate must be between 0 and 100'
                        })}
                        placeholder="Enter current rate"
                        className={currentRate ? 'pr-8' : ''}
                      />
                      {currentRate && (
                        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500">%</span>
                      )}
                    </div>
                    {errors.currentRate && (
                      <p className="mt-1 text-sm text-red-600">{errors.currentRate.message}</p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="w-full"
                  >
                    {isLoading ? 'Calculating...' : 'Proceed to Projection'}
                  </Button>
                </>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnhancedMerchantFeeCalculator;