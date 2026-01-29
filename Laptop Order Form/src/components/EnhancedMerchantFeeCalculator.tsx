import { useState } from 'react';
import { useForm } from 'react-hook-form@7.55.0';
import { ArrowLeft } from 'lucide-react';
import { ResultsPanel } from './ResultsPanel';
import { DataUploadValidator } from './DataUploadValidator';
import { ManualTransactionEntry } from './ManualTransactionEntry';
import { MCCDropdown } from './MCCDropdown';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import logo from 'figma:asset/79a39c442bd831ff976c31cd6d8bae181881f38b.png';

interface FormData {
  mcc: string;
  feeStructure: string;
  fixedFee: string;
  minimumFee: string;
  currentRate: string;
}

interface TransactionRow {
  transaction_id: string;
  transaction_date: string;
  merchant_id: string;
  amount: string;
  transaction_type: string;
  card_type: string;
}

interface EnhancedMerchantFeeCalculatorProps {
  onBackToLanding: () => void;
}

export function EnhancedMerchantFeeCalculator({ onBackToLanding }: EnhancedMerchantFeeCalculatorProps) {
  const [results, setResults] = useState<any>(null);
  const [dataValidated, setDataValidated] = useState(false);
  const [transactionData, setTransactionData] = useState<TransactionRow[]>([]);
  const [activeTab, setActiveTab] = useState<'upload' | 'manual'>('upload');
  
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormData>();

  const feeStructure = watch('feeStructure');
  const currentRate = watch('currentRate');
  const mccValue = watch('mcc');

  const handleDataValidated = (data: TransactionRow[], mcc?: string) => {
    setTransactionData(data);
    setDataValidated(true);
    if (mcc) {
      setValue('mcc', mcc);
    }
  };

  const onSubmit = (data: FormData) => {
    // Mock calculation - in real app, this would process the transaction data
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
      rangeOfQuotableRates: {
        lower: 2.15,
        upper: 2.75
      },
      adoptionProbability: 75,
      currentRateProvided: !!data.currentRate && data.currentRate !== '',
      profitability: (data.currentRate && data.currentRate !== '') ? 68 : null,
      transactionVolume: [
        { month: 'Jan', ats: 72000 },
        { month: 'Feb', ats: 78000 },
        { month: 'Mar', ats: 85000 },
        { month: 'Apr', ats: 82000 },
      ],
      transactionCount: transactionData.length
    };
    
    setResults(mockResults);
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
              {/* Logo */}
              <img src={logo} alt="Logo" className="h-16 mb-8 brightness-0 invert" />
              
              {/* Title */}
              <h1 className="text-4xl font-bold text-white mb-4">
                Rates Quotation Tool
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

                  <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'upload' | 'manual')}>
                    <TabsList className="grid w-full grid-cols-2">
                      <TabsTrigger value="upload">Upload CSV</TabsTrigger>
                      <TabsTrigger value="manual">Manual Entry</TabsTrigger>
                    </TabsList>
                    
                    <TabsContent value="upload" className="mt-4">
                      <DataUploadValidator 
                        onValidDataConfirmed={handleDataValidated}
                        onMCCExtracted={(mcc) => setValue('mcc', mcc)}
                      />
                    </TabsContent>
                    
                    <TabsContent value="manual" className="mt-4">
                      <ManualTransactionEntry 
                        onValidDataConfirmed={(data) => handleDataValidated(data)}
                      />
                    </TabsContent>
                  </Tabs>
                </div>
              )}

              {/* Step 2: Fee Configuration (shown after data validated) */}
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
                    <label htmlFor="mcc" className="block text-sm font-medium text-gray-700 mb-2">
                      Merchant Category Code (MCC)
                    </label>
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
                    <label htmlFor="feeStructure" className="block text-sm font-medium text-gray-700 mb-2">
                      Preferred Fee Structure
                    </label>
                    <select
                      id="feeStructure"
                      {...register('feeStructure', { required: 'Please select a fee structure' })}
                      className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-amber-500 focus:border-transparent appearance-none bg-white bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%228%22%20viewBox%3D%220%200%2012%208%22%3E%3Cpath%20fill%3D%22%23666%22%20d%3D%22M1.41%200L6%204.59%2010.59%200%2012%201.41l-6%206-6-6z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_1rem_center] bg-no-repeat pr-10"
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
                      <label htmlFor="fixedFee" className="block text-sm font-medium text-gray-700 mb-2">
                        Fixed Fee
                      </label>
                      <div className="relative">
                        <input
                          id="fixedFee"
                          type="text"
                          {...register('fixedFee', {
                            pattern: {
                              value: /^\d*\.?\d*$/,
                              message: 'Please enter a valid number'
                            }
                          })}
                          placeholder="Enter fixed fee ($)"
                          className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                          style={{ paddingLeft: watch('fixedFee') ? '2rem' : '1rem' }}
                          onInput={(e) => {
                            const input = e.target as HTMLInputElement;
                            const value = input.value;
                            if (!/^\d*\.?\d*$/.test(value)) {
                              input.value = value.slice(0, -1);
                            }
                          }}
                        />
                        {watch('fixedFee') && (
                          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">$</span>
                        )}
                      </div>
                      {errors.fixedFee && (
                        <p className="mt-1 text-sm text-red-600">{errors.fixedFee.message}</p>
                      )}
                    </div>
                  )}

                  {/* Minimum per transaction fee */}
                  <div>
                    <label htmlFor="minimumFee" className="block text-sm font-medium text-gray-700 mb-2">
                      Minimum per transaction fee (Optional)
                    </label>
                    <div className="relative">
                      <input
                        id="minimumFee"
                        type="text"
                        {...register('minimumFee', {
                          pattern: {
                            value: /^\d*\.?\d*$/,
                            message: 'Please enter a valid number'
                          }
                        })}
                        placeholder="Enter minimum fee ($)"
                        className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                        style={{ paddingLeft: watch('minimumFee') ? '2rem' : '1rem' }}
                        onInput={(e) => {
                          const input = e.target as HTMLInputElement;
                          const value = input.value;
                          if (!/^\d*\.?\d*$/.test(value)) {
                            input.value = value.slice(0, -1);
                          }
                        }}
                      />
                      {watch('minimumFee') && (
                        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">$</span>
                      )}
                    </div>
                    {errors.minimumFee && (
                      <p className="mt-1 text-sm text-red-600">{errors.minimumFee.message}</p>
                    )}
                  </div>

                  {/* Current Rate */}
                  <div>
                    <label htmlFor="currentRate" className="block text-sm font-medium text-gray-700 mb-2">
                      Current Rate (Optional)
                    </label>
                    <div className="relative">
                      <input
                        id="currentRate"
                        type="text"
                        {...register('currentRate')}
                        placeholder="Enter current rate (%)"
                        className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                        style={{ paddingRight: watch('currentRate') ? '2rem' : '1rem' }}
                        onInput={(e) => {
                          const input = e.target as HTMLInputElement;
                          const value = input.value;
                          if (!/^\d*\.?\d*$/.test(value)) {
                            input.value = value.slice(0, -1);
                          }
                        }}
                      />
                      {watch('currentRate') && (
                        <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">%</span>
                      )}
                    </div>
                    {errors.currentRate && (
                      <p className="mt-1 text-sm text-red-600">{errors.currentRate.message}</p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-medium py-3 px-6 rounded-2xl transition-all duration-200 shadow-md hover:shadow-lg"
                  >
                    Calculate Results
                  </button>
                </>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
