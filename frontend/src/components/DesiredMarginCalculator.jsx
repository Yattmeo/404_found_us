import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Upload, FileCheck, ArrowLeft, Download, AlertCircle, TrendingUp } from 'lucide-react';
import DesiredMarginResults from './DesiredMarginResults';
import ManualTransactionEntry from './ManualTransactionEntry';
import MCCDropdown from './MCCDropdown';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/Tabs';
import { Button } from './ui/Button';
import { Label } from './ui/Label';
import { Input } from './ui/Input';
import * as XLSX from 'xlsx';
import { desiredMarginAPI } from '../services/api';

/**
 * RATES QUOTATION TOOL (Epic 1, Story 1.2)
 * * PURPOSE:
 * - Help sales team quickly generate merchant rate quotations
 * - Recommend optimal pricing based on merchant profile and desired margin
 * - Provide quotable rate ranges with confidence intervals
 */

const DesiredMarginCalculator = ({ onBackToLanding }) => {
  const [fileName, setFileName] = useState('');
  const [parsedData, setParsedData] = useState(null);
  const [results, setResults] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [fileError, setFileError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [activeTab, setActiveTab] = useState('upload');

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm({
    defaultValues: {
      mcc: '',
      feeStructure: '',
      fixedFee: '',
      minimumFee: '',
      desiredMargin: ''
    }
  });

  const feeStructure = watch('feeStructure');
  const mcc = watch('mcc');

  const handleDownloadTemplate = () => {
    const headers = 'transaction_date,merchant_id,mcc,amount';
    const csvContent = headers;
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', 'merchant-transaction-template.csv');
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      handleFileProcessing(file);
    }
  };

  const handleFileChange = (e) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileProcessing(files[0]);
    }
  };

  const handleFileProcessing = (file) => {
    setFileName(file.name);
    setFileError('');
    setParsedData(null);
    
    const fileExtension = file.name.split('.').pop()?.toLowerCase();
    
    if (fileExtension === 'csv') {
      parseCSVFile(file);
    } else if (fileExtension === 'xlsx' || fileExtension === 'xls') {
      parseExcelFile(file);
    } else {
      setFileError('Unsupported file format. Please upload a CSV or Excel file.');
      setFileName('');
    }
  };

  // Handler for Manual Data Entry
  const handleManualDataConfirmed = (data) => {
    if (!data || data.length === 0) return;

    try {
      // Aggregate statistics from manual entries
      const totalTransactions = data.length;
      const totalAmount = data.reduce((sum, row) => sum + (parseFloat(row.amount) || 0), 0);
      const averageTicket = totalTransactions > 0 ? totalAmount / totalTransactions : 0;
      
      // Extract merchant ID from first row if available, otherwise generic
      const merchantId = data[0].merchant_id || 'MANUAL_ENTRY';

      // Note: Manual entry does not capture MCC per row in the UI, 
      // so user must select it manually in the dropdown.
      
      setParsedData({
        merchantId,
        mcc: null, // User must select this manually
        totalTransactions,
        totalAmount,
        averageTicket,
        source: 'manual'
      });
      
      setFileName('Manual Entry Data');
      setFileError('');
    } catch (err) {
      console.error(err);
      setFileError('Error processing manual data');
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
        desiredMargin: data.desiredMargin ? parseFloat(data.desiredMargin) : null,
        merchantData: parsedData,
      };

      // Call API
      const apiResults = await desiredMarginAPI.calculateDesiredMargin(payload);
      
      setResults(apiResults);
      setShowResults(true);
    } catch (error) {
      console.error('Calculation error:', error);
      
      // Fallback to null values when backend is not available
      const fallbackResults = {
        suggestedRate: null,
        marginBps: null,
        estimatedProfit: null,
        quotableRange: {
          min: null,
          max: null,
        },
        expectedATS: null,
        atsMarginError: null,
        expectedVolume: null,
        volumeMarginError: null,
        parsedData,
      };
      
      setResults(fallbackResults);
      setShowResults(true);
    } finally {
      setIsLoading(false);
    }
  };

  const parseCSVFile = (file) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      try {
        const text = e.target?.result;
        const lines = text.split('\n').filter(line => line.trim());
        
        if (lines.length < 2) {
          setFileError('File must contain at least a header row and one data row');
          return;
        }
        
        // Validate headers
        const headers = lines[0].toLowerCase().split(',').map(h => h.trim());
        const requiredHeaders = ['transaction_date', 'merchant_id', 'mcc', 'amount'];
        const missingHeaders = requiredHeaders.filter(h => !headers.includes(h));
        
        if (missingHeaders.length > 0) {
          setFileError(`Missing required columns: ${missingHeaders.join(', ')}`);
          return;
        }
        
        const dataRows = lines.slice(1).map((line, idx) => {
          const values = line.split(',').map(v => v.trim());
          const row = {
            date: values[headers.indexOf('transaction_date')],
            merchantId: values[headers.indexOf('merchant_id')],
            mcc: values[headers.indexOf('mcc')],
            amount: parseFloat(values[headers.indexOf('amount')]) || 0
          };
          
          if (!row.date || !row.merchantId || !row.mcc || !row.amount) {
            throw new Error(`Invalid data at row ${idx + 2}: Missing required fields`);
          }
          
          if (isNaN(row.amount) || row.amount <= 0) {
            throw new Error(`Invalid data at row ${idx + 2}: Amount must be a positive number`);
          }
          
          return row;
        });
        
        if (dataRows.length === 0) {
          setFileError('No valid transaction data found in file');
          return;
        }
        
        const mcc = dataRows[0].mcc;
        const merchantId = dataRows[0].merchantId;
        
        const totalTransactions = dataRows.length;
        const totalAmount = dataRows.reduce((sum, row) => sum + row.amount, 0);
        const averageTicket = totalAmount / totalTransactions;
        
        setValue('mcc', mcc);
        setFileError('');
        
        setParsedData({
          merchantId,
          mcc,
          totalTransactions,
          totalAmount,
          averageTicket,
          source: 'file'
        });
      } catch (error) {
        setFileError(error.message || 'Error parsing CSV file');
        setParsedData(null);
      }
    };
    
    reader.readAsText(file);
  };

  const parseExcelFile = (file) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      try {
        const data = e.target?.result;
        const workbook = XLSX.read(data, { type: 'binary' });
        
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
        
        if (jsonData.length < 2) {
          setFileError('File must contain at least a header row and one data row');
          return;
        }
        
        const headers = jsonData[0].map(h => String(h).toLowerCase().trim());
        const requiredHeaders = ['transaction_date', 'merchant_id', 'mcc', 'amount'];
        const missingHeaders = requiredHeaders.filter(h => !headers.includes(h));
        
        if (missingHeaders.length > 0) {
          setFileError(`Missing required columns: ${missingHeaders.join(', ')}`);
          return;
        }
        
        const dataRows = jsonData.slice(1).map((row, idx) => {
          const rowData = {
            date: row[headers.indexOf('transaction_date')],
            merchantId: row[headers.indexOf('merchant_id')],
            mcc: String(row[headers.indexOf('mcc')]),
            amount: parseFloat(row[headers.indexOf('amount')]) || 0
          };
          
          if (!rowData.date || !rowData.merchantId || !rowData.mcc || !rowData.amount) {
            throw new Error(`Invalid data at row ${idx + 2}: Missing required fields`);
          }
          
          if (isNaN(rowData.amount) || rowData.amount <= 0) {
            throw new Error(`Invalid data at row ${idx + 2}: Amount must be a positive number`);
          }
          
          return rowData;
        });
        
        if (dataRows.length === 0) {
          setFileError('No valid transaction data found in file');
          return;
        }
        
        const mcc = dataRows[0].mcc;
        const merchantId = dataRows[0].merchantId;
        
        const totalTransactions = dataRows.length;
        const totalAmount = dataRows.reduce((sum, row) => sum + row.amount, 0);
        const averageTicket = totalAmount / totalTransactions;
        
        setValue('mcc', mcc);
        setFileError('');
        
        setParsedData({
          merchantId,
          mcc,
          totalTransactions,
          totalAmount,
          averageTicket,
          source: 'file'
        });
      } catch (error) {
        setFileError(error.message || 'Error parsing Excel file');
        setParsedData(null);
      }
    };
    
    reader.readAsBinaryString(file);
  };

  const handleTabChange = (value) => {
    setActiveTab(value);
    // Reset data when switching tabs to avoid confusion
    setParsedData(null);
    setFileName('');
    setFileError('');
    if (value === 'manual') {
      setValue('mcc', ''); // Clear MCC if switching to manual since it requires selection
    }
  };

  const handleNewCalculation = () => {
    setResults(null);
    setFileName('');
    setParsedData(null);
    reset();
    setShowResults(false);
    setActiveTab('upload');
  };

  // If results exist, show full-screen results panel
  if (showResults) {
    return <DesiredMarginResults results={results} onNewCalculation={handleNewCalculation} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50 flex items-center justify-center p-8">
      <div className="w-full max-w-6xl">
        {/* Back Button */}
        <button
          onClick={onBackToLanding}
          className="flex items-center gap-2 text-gray-600 hover:text-[#44D62C] transition-colors mb-6 font-medium"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Home</span>
        </button>

        {/* Split Layout Container */}
        <div className="bg-white rounded-3xl shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-5">
          {/* Left Panel */}
          <div className="lg:col-span-2 bg-gradient-to-br from-[#44D62C] to-[#2FA51F] p-12 flex flex-col justify-between relative overflow-hidden">
            <div className="absolute top-0 right-0 w-full h-full">
              <svg className="absolute -right-1 top-0 h-full w-20" viewBox="0 0 100 800" preserveAspectRatio="none">
                <path d="M0,0 Q50,400 0,800 L100,800 L100,0 Z" fill="white" opacity="0.05"/>
              </svg>
            </div>
            
            <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2"></div>
            
            <div className="relative z-10">
              <h1 className="text-4xl font-bold text-[#FFFFFF] mb-4">
                Desired Margin Calculator
              </h1>
              <p className="text-[#FFFFFF] opacity-90 text-lg leading-relaxed">
                Calculate the optimal rates to quote your merchants. Upload transaction data or enter it manually to get personalized rate recommendations.
              </p>
            </div>

            <div className="relative z-10 mt-8">
              <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-8 border border-white/20">
                <div className="flex items-center justify-center h-48">
                  <TrendingUp className="w-24 h-24 text-white/60" />
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel - Form */}
          <div className="lg:col-span-3 p-12">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
              
              {/* Merchant Transaction Data Section */}
              <div>
                <h2 className="text-2xl font-bold text-[#313131] mb-6">
                  Merchant Transaction Data
                </h2>

                <Tabs value={activeTab} onValueChange={handleTabChange}>
                  <TabsList className="mb-4">
                    <TabsTrigger value="upload">Upload CSV/Excel</TabsTrigger>
                    <TabsTrigger value="manual">Manual Entry</TabsTrigger>
                  </TabsList>

                  <TabsContent value="upload">
                    <div 
                      className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                        fileError ? 'border-red-300 bg-red-50' : 
                        dragActive ? 'border-[#44D62C] bg-green-50' : 
                        'border-gray-300 bg-gray-50 hover:border-[#44D62C]'
                      }`}
                      onDragEnter={handleDrag}
                      onDragLeave={handleDrag}
                      onDragOver={handleDrag}
                      onDrop={handleDrop}
                    >
                      <input
                        type="file"
                        id="file-upload"
                        className="hidden"
                        accept=".csv,.xlsx,.xls"
                        onChange={handleFileChange}
                      />
                      
                      {fileError ? (
                        <div className="flex flex-col items-center gap-3">
                          <AlertCircle className="w-12 h-12 text-red-500" />
                          <div>
                            <p className="text-sm font-medium text-red-900">{fileName}</p>
                            <p className="text-sm text-red-600 mt-1">{fileError}</p>
                          </div>
                          <label htmlFor="file-upload" className="cursor-pointer">
                            <span className="text-[#44D62C] hover:text-[#3BC424] font-medium text-sm">Try another file</span>
                          </label>
                        </div>
                      ) : fileName && parsedData && parsedData.source === 'file' ? (
                        <div className="flex flex-col items-center gap-2">
                          <FileCheck className="w-12 h-12 text-green-500" />
                          <p className="text-sm font-medium text-gray-900">{fileName}</p>
                          <p className="text-sm text-green-600">
                            {parsedData.totalTransactions} transactions parsed
                          </p>
                        </div>
                      ) : (
                        <>
                          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                          <label htmlFor="file-upload" className="cursor-pointer block">
                            <span className="text-[#44D62C] hover:text-[#3BC424] font-medium">Upload CSV or Excel file</span>
                          </label>
                        </>
                      )}
                    </div>
                    
                    <div className="mt-4">
                      <Button
                        type="button"
                        onClick={handleDownloadTemplate}
                        className="w-full bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium py-2"
                      >
                        <Download className="w-4 h-4 mr-2" />
                        Download CSV Template
                      </Button>
                    </div>
                  </TabsContent>

                  <TabsContent value="manual">
                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                       <ManualTransactionEntry 
                          onValidDataConfirmed={handleManualDataConfirmed} 
                       />
                       {parsedData && parsedData.source === 'manual' && (
                         <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2">
                            <FileCheck className="w-5 h-5 text-green-600" />
                            <span className="text-sm text-green-800 font-medium">
                               Manual data confirmed: {parsedData.totalTransactions} transactions
                            </span>
                         </div>
                       )}
                    </div>
                  </TabsContent>
                </Tabs>
              </div>

              {/* MCC Code */}
              <div>
                <Label htmlFor="mcc" className="text-lg font-semibold text-gray-900 mb-2">
                  Merchant Category Code (MCC)
                </Label>
                <MCCDropdown
                  value={mcc || ''}
                  onChange={(value) => setValue('mcc', value)}
                  error={errors.mcc}
                />
                {errors.mcc && <p className="mt-1 text-sm text-red-600">{errors.mcc.message}</p>}
              </div>

              {/* Preferred Fee Structure */}
              <div>
                <Label htmlFor="feeStructure" className="text-lg font-semibold text-gray-900 mb-2">
                  Preferred Fee Structure
                </Label>
                <select
                  id="feeStructure"
                  {...register('feeStructure', {
                    required: 'Fee structure is required'
                  })}
                  className="mt-2 w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[#44D62C] focus:border-[#44D62C] bg-white text-gray-700"
                >
                  <option value="">Select structure</option>
                  <option value="percentage">% (Percentage only)</option>
                  <option value="percentage-fixed">% + Fixed Fee</option>
                  <option value="fixed">Fixed Fee</option>
                </select>
                {errors.feeStructure && <p className="mt-1 text-sm text-red-600">{errors.feeStructure.message}</p>}
              </div>

              {/* Fixed Fee - Show when percentage-fixed is selected */}
              {feeStructure === 'percentage-fixed' && (
                <div>
                  <Label htmlFor="fixedFee" className="text-lg font-semibold text-gray-900 mb-2">
                    Fixed Fee <span className="text-gray-500 font-normal">(Optional)</span>
                  </Label>
                  <Input
                    id="fixedFee"
                    type="number"
                    step="0.01"
                    min="0"
                    {...register('fixedFee', {
                      min: { value: 0, message: 'Fixed fee cannot be negative' }
                    })}
                    placeholder="Enter fixed fee ($)"
                    className="mt-2"
                  />
                  {errors.fixedFee && <p className="mt-1 text-sm text-red-600">{errors.fixedFee.message}</p>}
                </div>
              )}

              {/* Minimum per Transaction Fee */}
              <div>
                <Label htmlFor="minimumFee" className="text-lg font-semibold text-gray-900 mb-2">
                  Minimum per Transaction Fee <span className="text-gray-500 font-normal">(Optional)</span>
                </Label>
                <Input
                  id="minimumFee"
                  type="number"
                  step="0.01"
                  min="0"
                  {...register('minimumFee', {
                    min: { value: 0, message: 'Minimum fee cannot be negative' },
                    validate: (value) => !value || parseFloat(value) >= 0 || 'Minimum fee must be a positive number'
                  })}
                  placeholder="Enter minimum fee ($)"
                  className="mt-2"
                />
                {errors.minimumFee && <p className="mt-1 text-sm text-red-600">{errors.minimumFee.message}</p>}
              </div>

              {/* Desired Margin */}
              <div>
                <Label htmlFor="desiredMargin" className="text-lg font-semibold text-gray-900 mb-2">
                  Desired Margin <span className="text-gray-500 font-normal">(Optional)</span>
                </Label>
                <Input
                  id="desiredMargin"
                  type="number"
                  step="1"
                  min="0"
                  {...register('desiredMargin', {
                    min: { value: 0, message: 'Desired margin cannot be negative' },
                    validate: (value) => !value || parseFloat(value) >= 0 || 'Desired margin must be a positive number'
                  })}
                  placeholder="Enter desired margin (bps)"
                  className="mt-2"
                />
                {errors.desiredMargin && <p className="mt-1 text-sm text-red-600">{errors.desiredMargin.message}</p>}
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                disabled={isLoading || !parsedData || !mcc || !feeStructure}
                className="w-full bg-[#44D62C] hover:bg-[#3BC424] text-white font-semibold py-4 text-lg rounded-xl disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Calculating...' : 'Calculate Results'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DesiredMarginCalculator;