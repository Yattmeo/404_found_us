import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Upload, FileCheck, ArrowLeft } from 'lucide-react';
import DesiredMarginResults from './DesiredMarginResults';
import { Button } from './ui/Button';
import { Label } from './ui/Label';
import { Input } from './ui/Input';
import * as XLSX from 'xlsx';
import { desiredMarginAPI } from '../services/api';

const DesiredMarginCalculator = ({ onBackToLanding }) => {
  const [fileName, setFileName] = useState('');
  const [parsedData, setParsedData] = useState(null);
  const [results, setResults] = useState(null);
  const [showResults, setShowResults] = useState(false);
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
  const fixedFee = watch('fixedFee');
  const minimumFee = watch('minimumFee');

  const onSubmit = async (data) => {
    setIsLoading(true);
    try {
      // Prepare API payload
      const payload = {
        mcc: data.mcc,
        feeStructure: data.feeStructure,
        fixedFee: data.fixedFee ? parseFloat(data.fixedFee) : null,
        minimumFee: data.minimumFee ? parseFloat(data.minimumFee) : null,
        desiredMargin: parseFloat(data.desiredMargin),
        merchantData: parsedData,
      };

      // Call API
      const apiResults = await desiredMarginAPI.calculateDesiredMargin(payload);
      setResults(apiResults);
      setShowResults(true);
    } catch (error) {
      console.error('Calculation error:', error);
      // Fallback to mock data if API fails
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
    } finally {
      setIsLoading(false);
    }
  };

  const parseCSVFile = (file) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const text = e.target?.result;
      const lines = text.split('\\n').filter(line => line.trim());
      
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

  const parseExcelFile = (file) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const data = e.target?.result;
      const workbook = XLSX.read(data, { type: 'binary' });
      
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
      
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

  const handleFileChange = (e) => {
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
              {/* Title */}
              <h1 className="text-4xl font-bold text-white mb-4">
                Rates Quotation Tool
              </h1>
              <p className="text-orange-100 text-lg leading-relaxed">
                Analyse the merchant profile and recommend suitable pricing based on desired margin targets.
              </p>
            </div>

            {/* Image */}
            <div className="relative z-10 mt-8">
              <img 
                src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080"
                alt="Data Analysis"
                className="rounded-2xl shadow-xl opacity-90"
              />
            </div>
          </div>

          {/* Right Panel - Form */}
          <div className="lg:col-span-3 p-12">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              {/* File Upload */}
              <div>
                <h2 className="text-xl font-semibold text-gray-900 mb-1">
                  Merchant Data File
                </h2>
                <p className="text-sm text-gray-600 mb-4">
                  Upload merchant transaction history (CSV or Excel)
                </p>

                <div className="border-2 border-dashed border-gray-300 rounded-2xl p-6 text-center hover:border-amber-400 transition-colors">
                  <input
                    type="file"
                    id="file-upload"
                    className="hidden"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileChange}
                  />
                  
                  {fileName && parsedData ? (
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
                      <label htmlFor="file-upload" className="cursor-pointer">
                        <span className="text-amber-600 hover:text-amber-700 font-medium">Click to upload</span>
                        <span className="text-gray-600"> or drag and drop</span>
                      </label>
                      <p className="text-xs text-gray-500 mt-1">CSV or Excel files</p>
                    </>
                  )}
                </div>
              </div>

              {/* Form fields - shown after file upload */}
              {parsedData && (
                <>
                  {/* MCC Display (auto-populated) */}
                  <div>
                    <Label htmlFor="mcc">Merchant Category Code (MCC)</Label>
                    <Input
                      id="mcc"
                      type="text"
                      {...register('mcc', { required: 'MCC is required' })}
                      readOnly
                      className="bg-gray-50"
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
                      <option value="percentage-fixed">% + Fixed Fee</option>
                      <option value="fixed">Fixed Fee</option>
                    </select>
                    {errors.feeStructure && (
                      <p className="mt-1 text-sm text-red-600">{errors.feeStructure.message}</p>
                    )}
                  </div>

                  {/* Fixed Fee - Conditional */}
                  {(feeStructure === 'percentage-fixed' || feeStructure === 'fixed') && (
                    <div>
                      <Label htmlFor="fixedFee">Fixed Fee</Label>
                      <div className="relative">
                        <Input
                          id="fixedFee"
                          type="number"
                          step="0.01"
                          {...register('fixedFee')}
                          placeholder="Enter fixed fee"
                          className={fixedFee ? 'pl-8' : ''}
                        />
                        {fixedFee && (
                          <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">$</span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Minimum Fee */}
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

                  {/* Desired Margin */}
                  <div>
                    <Label htmlFor="desiredMargin">Desired Margin (%)</Label>
                    <Input
                      id="desiredMargin"
                      type="number"
                      step="0.01"
                      {...register('desiredMargin', { required: 'Desired margin is required' })}
                      placeholder="Enter desired margin percentage"
                    />
                    {errors.desiredMargin && (
                      <p className="mt-1 text-sm text-red-600">{errors.desiredMargin.message}</p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="w-full"
                  >
                    {isLoading ? 'Calculating...' : 'Calculate Quotation'}
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

export default DesiredMarginCalculator;
