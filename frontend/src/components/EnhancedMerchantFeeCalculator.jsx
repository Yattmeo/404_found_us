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

  const normalizeCurrentRateResults = (apiPayload, formData, txCount, avgTicket, totalAmount) => {
    const envelope = apiPayload || {};
    const data = envelope?.data || {};
    const suggestedRate = typeof data?.applied_rate === 'number' ? data.applied_rate * 100 : null;
    const marginBps = typeof data?.margin_bps === 'number' ? data.margin_bps : null;

    const estimatedProfit =
      typeof data?.margin_rate === 'number' && typeof data?.total_volume === 'number'
        ? data.total_volume * data.margin_rate
        : null;
    const estimatedProfitMin = typeof estimatedProfit === 'number' ? estimatedProfit * 0.9 : null;
    const estimatedProfitMax = typeof estimatedProfit === 'number' ? estimatedProfit * 1.1 : null;

    const transactionSummary = {
      transaction_count: typeof data?.transaction_count === 'number' ? data.transaction_count : txCount,
      total_volume: typeof data?.total_volume === 'number' ? data.total_volume : totalAmount,
      average_ticket: typeof data?.average_ticket === 'number' ? data.average_ticket : avgTicket,
    };

    const processingVolume =
      typeof transactionSummary.total_volume === 'number'
        ? transactionSummary.total_volume
        : (typeof data?.calculation?.total_volume === 'number' ? data.calculation.total_volume : totalAmount);

    let profitabilityPct = null;
    if (
      typeof estimatedProfitMin === 'number' &&
      typeof estimatedProfitMax === 'number' &&
      typeof processingVolume === 'number' &&
      processingVolume > 0
    ) {
      const midpointProfit = (estimatedProfitMin + estimatedProfitMax) / 2;
      profitabilityPct = Number(((midpointProfit / processingVolume) * 100).toFixed(2));
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
    const transactionSummary = data?.transaction_summary || {};
    const profitabilityCurve = Array.isArray(data?.profitability_curve) ? data.profitability_curve : [];

    const suggestedRate = typeof summary.suggested_rate_pct === 'number' ? summary.suggested_rate_pct : null;
    const marginBps = typeof summary.margin_bps === 'number' ? summary.margin_bps : null;
    const estimatedProfitMin = typeof summary.estimated_profit_min === 'number' ? summary.estimated_profit_min : null;
    const estimatedProfitMax = typeof summary.estimated_profit_max === 'number' ? summary.estimated_profit_max : null;

    const processingVolume =
      typeof transactionSummary.total_volume === 'number'
        ? transactionSummary.total_volume
        : (typeof data?.calculation?.total_volume === 'number' ? data.calculation.total_volume : totalAmount);

    let profitabilityPct = null;
    if (
      typeof estimatedProfitMin === 'number' &&
      typeof estimatedProfitMax === 'number' &&
      typeof processingVolume === 'number' &&
      processingVolume > 0
    ) {
      const midpointProfit = (estimatedProfitMin + estimatedProfitMax) / 2;
      profitabilityPct = Number(((midpointProfit / processingVolume) * 100).toFixed(2));
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
      quotableRange: {
        min: suggestedRate !== null ? Math.max(0, Number((suggestedRate - 0.1).toFixed(2))) : null,
        max: suggestedRate !== null ? Number((suggestedRate + 0.1).toFixed(2)) : null,
      },
      processingVolume,
      averageTransactionSize,
      transactionCount,
      currentRateProvided: !!formData.currentRate,
      costForecast: Array.isArray(data?.cost_forecast) ? data.cost_forecast : [],
      volumeForecast: Array.isArray(data?.volume_forecast) ? data.volume_forecast : [],
      profitabilityCurve,
      mlContext: data?.ml_context || null,
      transactionSummary,
      calculation: data?.calculation || null,
    };
  };

  const computeTransactionMetrics = (input) => {
    if (Array.isArray(input)) {
      const txCount = input.length;
      const totalAmount = input.reduce((sum, t) => sum + parseFloat(t.amount || 0), 0);
      const avgTicket = txCount > 0 ? totalAmount / txCount : 0;
      return { txCount, totalAmount, avgTicket };
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

      // Prepare compact payload to avoid sending raw transactions.
      const payload = {
        mcc: data.mcc,
        average_transaction_value: avgTicket,
        monthly_transactions: txCount,
        fixedFee: data.fixedFee === '' || data.fixedFee === undefined ? null : parseFloat(data.fixedFee),
        currentRate: data.currentRate === '' || data.currentRate === undefined ? null : parseFloat(data.currentRate),
        transactions: [],
      };

      // Align payload keys with backend contract.
      payload.fixed_fee = payload.fixedFee ?? 0.30;
      payload.current_rate = payload.currentRate !== null && payload.currentRate !== undefined
        ? payload.currentRate / 100
        : null;
      delete payload.fixedFee;
      delete payload.currentRate;

      if (hasCurrentRate) {
        // Mode 1: evaluate metrics for an explicitly provided current rate.
        const apiResults = await merchantFeeAPI.calculateCurrentRates(payload);
        setResults(normalizeCurrentRateResults(apiResults, data, txCount, avgTicket, totalAmount));
      } else {
        // Mode 2: no current rate provided, fetch rate-range profitability guidance.
        const quotePayload = {
          mcc: data.mcc,
          average_transaction_value: avgTicket,
          monthly_transactions: txCount,
          fixed_fee: payload.fixed_fee,
          desired_margin: 0.015,
          transactions: [],
        };
        const apiResults = await desiredMarginAPI.getDesiredMarginDetails(quotePayload);
        setResults(normalizeRangeResults(apiResults, data, txCount, avgTicket, totalAmount));
      }
    } catch (error) {
      console.error('Calculation error:', error);
      // TODO: Remove this fallback once backend API is fully implemented
      // Calculate what we can from available transaction summary
      const { txCount, totalAmount, avgTicket } = computeTransactionMetrics(transactionData);
      
      const mockResults = {
        // TEMPORARY: These should come from backend cost engine model
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
    return <ResultsPanel results={results} hasCurrentRate={!!currentRate} onNewCalculation={handleNewCalculation} />;
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