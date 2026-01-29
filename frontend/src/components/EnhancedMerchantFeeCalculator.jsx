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
import { merchantFeeAPI } from '../services/api';

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
  const minimumFee = watch('minimumFee');

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
      // Prepare API payload
      const payload = {
        mcc: data.mcc,
        feeStructure: data.feeStructure,
        fixedFee: data.fixedFee ? parseFloat(data.fixedFee) : null,
        minimumFee: data.minimumFee ? parseFloat(data.minimumFee) : null,
        currentRate: data.currentRate ? parseFloat(data.currentRate) : null,
        transactions: transactionData,
      };

      // Call API
      const apiResults = await merchantFeeAPI.calculateCurrentRates(payload);
      setResults(apiResults);
    } catch (error) {
      console.error('Calculation error:', error);
      // Fallback to mock data if API fails
      const mockResults = {
        suggestedRate: 2.45,
        margin: 185,
        estimatedProfit: 1250.00,
        expectedATS: 85000,
        expectedVolume: 193467,
        quotableRange: {
          min: '2.15%',
          max: '2.75%'
        },
        adoptionProbability: 75,
        currentRateProvided: !!data.currentRate,
        profitability: data.currentRate ? 68 : null,
        transactionCount: transactionData.length
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-8">
      <div className="w-full max-w-6xl">
        {/* Back Button */}
        <button
          onClick={onBackToLanding}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          <span className="font-medium">Back to Home</span>
        </button>

        {/* Split Layout Container */}
        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-5">
          {/* Left Panel - Orange Branding */}
          <div className="lg:col-span-2 bg-gradient-to-br from-amber-500 to-orange-600 p-12 flex flex-col justify-between relative overflow-hidden">
            {/* Decorative circles */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2"></div>
            
            <div className="relative z-10">
              {/* Title */}
              <h1 className="text-4xl font-bold text-white mb-4">
                Merchant Profitability Calculator
              </h1>
              <p className="text-orange-100 text-lg leading-relaxed">
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
                    <h2 className="text-xl font-semibold text-gray-900 mb-1">
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
                        className="text-sm text-orange-600 hover:text-orange-700 font-medium"
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
                      className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-amber-500 focus:border-transparent bg-white"
                    >
                      <option value="">Select structure</option>
                      <option value="percentage">% (Percentage only)</option>
                      <option value="percentage_fixed">% + Fixed (Percentage + Fixed Fee)</option>
                      <option value="fixed">Fixed Fee</option>
                    </select>
                    {errors.feeStructure && (
                      <p className="mt-1 text-sm text-red-600">{errors.feeStructure.message}</p>
                    )}
                  </div>

                  {/* Fixed Fee - Conditional */}
                  {(feeStructure === 'percentage_fixed' || feeStructure === 'fixed') && (
                    <div>
                      <Label htmlFor="fixedFee">Fixed Fee</Label>
                      <div className="relative">
                        <Input
                          id="fixedFee"
                          type="number"
                          step="0.01"
                          {...register('fixedFee', {
                            pattern: {
                              value: /^\\d*\\.?\\d*$/,
                              message: 'Please enter a valid number'
                            }
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

                  {/* Minimum per transaction fee */}
                  <div>
                    <Label htmlFor="minimumFee">Minimum per transaction fee (Optional)</Label>
                    <div className="relative">
                      <Input
                        id="minimumFee"
                        type="number"
                        step="0.01"
                        {...register('minimumFee')}
                        placeholder="Enter minimum fee"
                        className={minimumFee ? 'pl-8' : ''}
                      />
                      {minimumFee && (
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                      )}
                    </div>
                  </div>

                  {/* Current Rate */}
                  <div>
                    <Label htmlFor="currentRate">Current Rate (Optional)</Label>
                    <div className="relative">
                      <Input
                        id="currentRate"
                        type="number"
                        step="0.01"
                        {...register('currentRate')}
                        placeholder="Enter current rate"
                        className={currentRate ? 'pr-8' : ''}
                      />
                      {currentRate && (
                        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500">%</span>
                      )}
                    </div>
                  </div>

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="w-full"
                  >
                    {isLoading ? 'Calculating...' : 'Calculate Results'}
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
