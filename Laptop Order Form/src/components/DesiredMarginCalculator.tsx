import { useState } from 'react';
import { useForm } from 'react-hook-form@7.55.0';
import { Upload, FileCheck, ArrowLeft } from 'lucide-react';
import { DesiredMarginResults } from './DesiredMarginResults';
import * as XLSX from 'xlsx';
import logo from 'figma:asset/79a39c442bd831ff976c31cd6d8bae181881f38b.png';

interface FormData {
  mcc: string;
  feeStructure: 'percentage' | 'fixed' | 'percentage-fixed';
  fixedFee: string;
  minimumFee: string;
  desiredMargin: string;
}

interface ParsedData {
  merchantId: string;
  mcc: string;
  totalTransactions: number;
  totalAmount: number;
  averageTicket: number;
}

interface DesiredMarginCalculatorProps {
  onBackToLanding: () => void;
}

export function DesiredMarginCalculator({ onBackToLanding }: DesiredMarginCalculatorProps) {
  const [fileName, setFileName] = useState('');
  const [parsedData, setParsedData] = useState<ParsedData | null>(null);
  const [results, setResults] = useState<any>(null);
  const [showResults, setShowResults] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormData>();

  const feeStructure = watch('feeStructure');

  const onSubmit = (data: FormData) => {
    // Mock calculation results
    const mockResults = {
      suggestedRate: '2.35%',
      marginBps: '125 bps',
      estimatedProfit: '$1,250',
      quotableRange: {
        min: '2.15%',
        max: '2.55%',
      },
      expectedATS: '65%',
      atsMarginError: '2.5%',
      expectedVolume: '$125,000',
      volumeMarginError: '3.2%',
      parsedData,
    };
    setResults(mockResults);
    setShowResults(true);
  };

  const parseCSVFile = (file: File) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.split('\n').filter(line => line.trim());
      
      if (lines.length < 2) return;
      
      const dataRows = lines.slice(1).map(line => {
        const values = line.split(',').map(v => v.trim());
        return {
          date: values[0],
          merchantId: values[1],
          mcc: values[2],
          amount: parseFloat(values[3]) || 0
        };
      }).filter(row => row.mcc && row.amount);
      
      if (dataRows.length === 0) return;
      
      const mcc = dataRows[0].mcc;
      const merchantId = dataRows[0].merchantId;
      
      const totalTransactions = dataRows.length;
      const totalAmount = dataRows.reduce((sum, row) => sum + row.amount, 0);
      const averageTicket = totalAmount / totalTransactions;
      
      setValue('mcc', mcc);
      
      setParsedData({
        merchantId,
        mcc,
        totalTransactions,
        totalAmount,
        averageTicket
      });
    };
    
    reader.readAsText(file);
  };

  const parseExcelFile = (file: File) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const data = e.target?.result;
      const workbook = XLSX.read(data, { type: 'binary' });
      
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 }) as any[][];
      
      if (jsonData.length < 2) return;
      
      const dataRows = jsonData.slice(1).map(row => {
        return {
          date: row[0],
          merchantId: row[1],
          mcc: String(row[2]),
          amount: parseFloat(row[3]) || 0
        };
      }).filter(row => row.mcc && row.amount);
      
      if (dataRows.length === 0) return;
      
      const mcc = dataRows[0].mcc;
      const merchantId = dataRows[0].merchantId;
      
      const totalTransactions = dataRows.length;
      const totalAmount = dataRows.reduce((sum, row) => sum + row.amount, 0);
      const averageTicket = totalAmount / totalTransactions;
      
      setValue('mcc', mcc);
      
      setParsedData({
        merchantId,
        mcc,
        totalTransactions,
        totalAmount,
        averageTicket
      });
    };
    
    reader.readAsBinaryString(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      setFileName(file.name);
      
      const fileExtension = file.name.split('.').pop()?.toLowerCase();
      
      if (fileExtension === 'csv') {
        parseCSVFile(file);
      } else if (fileExtension === 'xlsx' || fileExtension === 'xls') {
        parseExcelFile(file);
      } else {
        alert('Unsupported file format. Please upload a CSV or Excel file.');
      }
    }
  };

  const handleNewCalculation = () => {
    setResults(null);
    setFileName('');
    setParsedData(null);
    reset();
    setShowResults(false);
  };

  // If results exist, show full-screen results panel
  if (showResults) {
    return <DesiredMarginResults results={results} onNewCalculation={handleNewCalculation} />;
  }

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
          <div className="lg:col-span-2 bg-gradient-to-br from-orange-500 to-amber-600 p-12 flex flex-col justify-between relative overflow-hidden">
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
                Receive data-driven pricing recommendations to maximise your revenue while staying competitive.
              </p>
            </div>

            {/* Image */}
            <div className="relative z-10 mt-8">
              <img 
                src="https://images.unsplash.com/photo-1748609160056-7b95f30041f0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBidXNpbmVzcyUyMGFuYWx5dGljc3xlbnwxfHx8fDE3Njg3MDgzNTZ8MA&ixlib=rb-4.1.0&q=80&w=1080"
                alt="Business Analytics"
                className="rounded-2xl shadow-xl opacity-90"
              />
            </div>
          </div>

          {/* Right Panel - Form */}
          <div className="lg:col-span-3 p-12">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Merchant Transaction Data
                </label>
                <div className="relative">
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload-margin"
                  />
                  <label
                    htmlFor="file-upload-margin"
                    className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-gray-300 rounded-2xl hover:border-orange-400 hover:bg-orange-50 transition-colors cursor-pointer"
                  >
                    <Upload className="w-5 h-5 text-gray-500" />
                    <span className="text-gray-600">
                      {fileName || 'Upload CSV or Excel file'}
                    </span>
                  </label>
                </div>
                
                {parsedData && (
                  <div className="mt-3 p-4 bg-green-50 border border-green-200 rounded-2xl">
                    <div className="flex items-start gap-2">
                      <FileCheck className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-green-900">File processed successfully</p>
                        <div className="mt-2 text-sm text-green-700 space-y-1">
                          <p>Merchant ID: <span className="font-medium">{parsedData.merchantId}</span></p>
                          <p>MCC: <span className="font-medium">{parsedData.mcc}</span></p>
                          <p>Total Transactions: <span className="font-medium">{parsedData.totalTransactions}</span></p>
                          <p>Total Amount: <span className="font-medium">${parsedData.totalAmount.toFixed(2)}</span></p>
                          <p>Average Ticket: <span className="font-medium">${parsedData.averageTicket.toFixed(2)}</span></p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* MCC Code */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Merchant Category Code (MCC)
                </label>
                <input
                  type="text"
                  {...register('mcc', { required: 'MCC is required' })}
                  className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  placeholder="Enter MCC code"
                />
                {errors.mcc && (
                  <p className="mt-1 text-sm text-red-600">{errors.mcc.message}</p>
                )}
              </div>

              {/* Fee Structure */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Preferred Fee Structure
                </label>
                <select
                  {...register('feeStructure', { required: 'Fee structure is required' })}
                  className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 appearance-none bg-white bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%228%22%20viewBox%3D%220%200%2012%208%22%3E%3Cpath%20fill%3D%22%23666%22%20d%3D%22M1.41%200L6%204.59%2010.59%200%2012%201.41l-6%206-6-6z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_1rem_center] bg-no-repeat pr-10"
                >
                  <option value="">Select structure</option>
                  <option value="percentage">Percentage</option>
                  <option value="fixed">Fixed Fee</option>
                  <option value="percentage-fixed">Percentage + Fixed Fee</option>
                </select>
                {errors.feeStructure && (
                  <p className="mt-1 text-sm text-red-600">{errors.feeStructure.message}</p>
                )}
              </div>

              {/* Fixed Fee (conditional) */}
              {(feeStructure === 'fixed' || feeStructure === 'percentage-fixed') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Fixed Fee
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      {...register('fixedFee', {
                        pattern: {
                          value: /^\d*\.?\d*$/,
                          message: 'Please enter a valid number'
                        }
                      })}
                      placeholder="Enter fixed fee ($)"
                      className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
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

              {/* Minimum per Transaction Fee */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Minimum per Transaction Fee <span className="text-gray-500">(Optional)</span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    {...register('minimumFee', {
                      pattern: {
                        value: /^\d*\.?\d*$/,
                        message: 'Please enter a valid number'
                      }
                    })}
                    placeholder="Enter minimum fee ($)"
                    className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
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

            {/* Desired Margin */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Desired Margin <span className="text-gray-500">(Optional)</span>
              </label>
              <div className="relative">
                <input
                  type="text"
                  {...register('desiredMargin')}
                  className="w-full px-4 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                  placeholder="Enter desired margin (bps)"
                  style={{ paddingRight: watch('desiredMargin') ? '3rem' : '1rem' }}
                  onInput={(e) => {
                    const input = e.target as HTMLInputElement;
                    const value = input.value;
                    if (!/^\d*\.?\d*$/.test(value)) {
                      input.value = value.slice(0, -1);
                    }
                  }}
                />
                {watch('desiredMargin') && (
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">bps</span>
                )}
              </div>
              {errors.desiredMargin && (
                <p className="mt-1 text-sm text-red-600">{errors.desiredMargin.message}</p>
              )}
            </div>


              {/* Submit Button */}
              <button
                type="submit"
                className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-medium py-3 px-6 rounded-2xl transition-all duration-200 shadow-md hover:shadow-lg"
              >
                Calculate Results
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}