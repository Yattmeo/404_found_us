import { useState } from 'react';
import { ChevronRight, ChevronLeft, ChevronDown } from 'lucide-react';
import { BusinessData } from '../App';

interface QuotationFormProps {
  onSubmit: (data: BusinessData) => void;
}

type FormErrors = {
  businessName?: string;
  industry?: string;
  averageTransactionValue?: string;
  monthlyTransactions?: string;
  cardTypes?: string;
};

const industryOptions = [
  { value: '5411 - General Grocery Stores', label: '5411 - General Grocery Stores' },
  { value: '5732 - Electronics Stores', label: '5732 - Electronics Stores' },
  { value: '5812 - Eating Places and Restaurants', label: '5812 - Eating Places and Restaurants' },
  { value: '5814 - Fast Food Restaurants', label: '5814 - Fast Food Restaurants' },
  { value: '5967 - Direct Marketing', label: '5967 - Direct Marketing' },
  { value: '7011 - Lodging and Hotels', label: '7011 - Lodging and Hotels' },
  { value: '7399 - Business Services', label: '7399 - Business Services' },
  { value: '7999 - Recreation Services', label: '7999 - Recreation Services' },
  { value: '8062 - Hospitals', label: '8062 - Hospitals' },
  { value: '8999 - Professional Services', label: '8999 - Professional Services' },
];

export function QuotationForm({ onSubmit }: QuotationFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 3;

  const [formData, setFormData] = useState<BusinessData>({
    businessName: '',
    industry: '',
    averageTransactionValue: '',
    monthlyTransactions: '',
    cardTypes: [],
    ecommercePercentage: '0',
    inPersonPercentage: '100',
    phoneMailPercentage: '0',
  });

  const [showDollarSign, setShowDollarSign] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const preventNegativeNumericInput = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (['-', '+', 'e', 'E'].includes(event.key)) {
      event.preventDefault();
    }
  };

  const updateField = (field: keyof BusinessData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const toggleArrayValue = (field: 'cardTypes', value: string) => {
    setFormData((prev) => {
      const currentArray = prev[field];
      const newArray = currentArray.includes(value)
        ? currentArray.filter((item) => item !== value)
        : [...currentArray, value];
      return { ...prev, [field]: newArray };
    });

    setErrors((prev) => ({ ...prev, cardTypes: undefined }));
  };

  const validateBusinessName = () => {
    const value = formData.businessName.trim();
    if (!value) {
      return 'Business Name is required.';
    }
    return undefined;
  };

  const validateIndustry = () => {
    if (!formData.industry) {
      return 'Industry is required.';
    }
    return undefined;
  };

  const validateAverageTransactionValue = () => {
    const rawValue = formData.averageTransactionValue.trim();
    if (!rawValue) {
      return 'Average Transaction Value is required.';
    }

    if (!/^\d+(\.\d{1,2})?$/.test(rawValue)) {
      return 'Use a valid amount with up to 2 decimal places.';
    }

    const parsedValue = Number(rawValue);
    if (Number.isNaN(parsedValue) || parsedValue < 0) {
      return 'Average Transaction Value must be 0 or more.';
    }

    return undefined;
  };

  const validateMonthlyTransactions = () => {
    const rawValue = formData.monthlyTransactions.trim();
    if (!rawValue) {
      return 'Monthly Transactions is required.';
    }

    if (!/^\d+$/.test(rawValue)) {
      return 'Monthly Transactions must be a whole number.';
    }

    if (parseInt(rawValue, 10) < 0) {
      return 'Monthly Transactions must be 0 or more.';
    }

    return undefined;
  };

  const validateCardTypes = () => {
    if (formData.cardTypes.length === 0) {
      return 'Select at least one payment brand.';
    }
    return undefined;
  };

  const validateStep = (step: number) => {
    const stepErrors: FormErrors = {};

    if (step === 1) {
      stepErrors.businessName = validateBusinessName();
      stepErrors.industry = validateIndustry();
    }

    if (step === 2) {
      stepErrors.averageTransactionValue = validateAverageTransactionValue();
      stepErrors.monthlyTransactions = validateMonthlyTransactions();
    }

    if (step === 3) {
      stepErrors.cardTypes = validateCardTypes();
    }

    setErrors((prev) => ({ ...prev, ...stepErrors }));
    return Object.values(stepErrors).every((error) => !error);
  };

  const handlePercentageChange = (field: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    
    if (field === 'ecommercePercentage') {
      const remaining = 100 - numValue;
      const currentInPerson = parseFloat(formData.inPersonPercentage) || 0;
      const currentPhoneMail = parseFloat(formData.phoneMailPercentage) || 0;
      const total = currentInPerson + currentPhoneMail;
      
      if (total > 0) {
        const ratio = remaining / total;
        updateField('ecommercePercentage', numValue.toString());
        updateField('inPersonPercentage', (currentInPerson * ratio).toFixed(0));
        updateField('phoneMailPercentage', (currentPhoneMail * ratio).toFixed(0));
      } else {
        updateField('ecommercePercentage', numValue.toString());
        updateField('inPersonPercentage', remaining.toString());
        updateField('phoneMailPercentage', '0');
      }
    } else if (field === 'inPersonPercentage') {
      const remaining = 100 - numValue;
      const currentEcommerce = parseFloat(formData.ecommercePercentage) || 0;
      const currentPhoneMail = parseFloat(formData.phoneMailPercentage) || 0;
      const total = currentEcommerce + currentPhoneMail;
      
      if (total > 0) {
        const ratio = remaining / total;
        updateField('inPersonPercentage', numValue.toString());
        updateField('ecommercePercentage', (currentEcommerce * ratio).toFixed(0));
        updateField('phoneMailPercentage', (currentPhoneMail * ratio).toFixed(0));
      } else {
        updateField('inPersonPercentage', numValue.toString());
        updateField('ecommercePercentage', remaining.toString());
        updateField('phoneMailPercentage', '0');
      }
    } else {
      const remaining = 100 - numValue;
      const currentEcommerce = parseFloat(formData.ecommercePercentage) || 0;
      const currentInPerson = parseFloat(formData.inPersonPercentage) || 0;
      const total = currentEcommerce + currentInPerson;
      
      if (total > 0) {
        const ratio = remaining / total;
        updateField('phoneMailPercentage', numValue.toString());
        updateField('ecommercePercentage', (currentEcommerce * ratio).toFixed(0));
        updateField('inPersonPercentage', (currentInPerson * ratio).toFixed(0));
      } else {
        updateField('phoneMailPercentage', numValue.toString());
        updateField('ecommercePercentage', remaining.toString());
        updateField('inPersonPercentage', '0');
      }
    }
  };

  const nextStep = () => {
    if (currentStep < totalSteps && validateStep(currentStep)) {
      setCurrentStep(currentStep + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep(3)) {
      return;
    }
    onSubmit(formData);
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return !!formData.businessName.trim() && !!formData.industry;
      case 2:
        return !!formData.averageTransactionValue.trim() && !!formData.monthlyTransactions.trim();
      case 3:
        return formData.cardTypes.length > 0;
      default:
        return false;
    }
  };

  return (
    <div className="w-full h-full min-h-full flex flex-col justify-center">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-600">Step {currentStep} of {totalSteps}</span>
          <span className="text-xs text-gray-600">{Math.round((currentStep / totalSteps) * 100)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-1.5">
          <div
            className="bg-gradient-to-r from-blue-400 to-[#FF8C00] h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${(currentStep / totalSteps) * 100}%` }}
          />
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col flex-1">
        {/* Step 1: Business Information */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-gray-900 mb-5 text-xl">Business Information</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-gray-700 mb-1.5">
                    Business Name *
                  </label>
                  <input
                    type="text"
                    value={formData.businessName}
                    onChange={(e) => {
                      updateField('businessName', e.target.value);
                      if (errors.businessName) {
                        setErrors((prev) => ({ ...prev, businessName: undefined }));
                      }
                    }}
                    className="merchant-focus-field w-full px-3 py-2.5 border border-gray-300 rounded-lg transition bg-gray-50 text-sm"
                    placeholder="Enter your business name"
                    required
                  />
                  {errors.businessName && <p className="mt-1 text-xs text-red-600">{errors.businessName}</p>}
                </div>

                <div>
                  <label className="block text-xs text-gray-700 mb-1.5">
                    Industry *
                  </label>
                  <div className="relative">
                    <ChevronDown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none z-10" />
                    <select
                      value={formData.industry}
                      onChange={(e) => {
                        updateField('industry', e.target.value);
                        if (errors.industry) {
                          setErrors((prev) => ({ ...prev, industry: undefined }));
                        }
                      }}
                      className="merchant-focus-field w-full pl-9 pr-3 py-2.5 border border-gray-300 rounded-lg transition bg-gray-50 appearance-none text-sm"
                      required
                    >
                      <option value="">Select MCC industry</option>
                      {industryOptions.map((industry) => (
                        <option key={industry.value} value={industry.value}>
                          {industry.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  {errors.industry && <p className="mt-1 text-xs text-red-600">{errors.industry}</p>}
                </div>
              </div>
            </div>
            
            {/* Navigation buttons for step 1 */}
            <div className="flex justify-between mt-8 pt-5 border-t border-gray-200">
              <button
                type="button"
                onClick={prevStep}
                disabled={currentStep === 1}
                className="flex items-center px-5 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium text-sm"
              >
                <ChevronLeft className="w-4 h-4 mr-1.5" />
                Previous
              </button>

              <button
                type="button"
                onClick={nextStep}
                disabled={!isStepValid()}
                className="flex items-center px-5 py-2.5 text-white bg-[#6CAFF3] rounded-lg hover:bg-[#5B9FED] disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg font-medium text-sm"
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1.5" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Transaction Details */}
        {currentStep === 2 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-gray-900 mb-5 text-xl">Transaction Details</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-gray-700 mb-1.5">
                    Average Transaction Value ($) *
                  </label>
                  <div className="relative">
                    {showDollarSign && formData.averageTransactionValue && (
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 z-10 text-sm">$</span>
                    )}
                    <input
                      type="number"
                      value={formData.averageTransactionValue}
                      onKeyDown={preventNegativeNumericInput}
                      onChange={(e) => {
                        const newValue = e.target.value;
                        if (/^\d*(\.\d{0,2})?$/.test(newValue)) {
                          updateField('averageTransactionValue', newValue);
                          if (errors.averageTransactionValue) {
                            setErrors((prev) => ({ ...prev, averageTransactionValue: undefined }));
                          }
                        }
                      }}
                      onFocus={() => setShowDollarSign(true)}
                      onBlur={() => {
                        setShowDollarSign(false);
                        const value = formData.averageTransactionValue.trim();
                        if (value !== '' && /^\d+(\.\d{1,2})?$/.test(value)) {
                          updateField('averageTransactionValue', Number(value).toFixed(2));
                        }
                      }}
                      className={`merchant-focus-field w-full ${showDollarSign && formData.averageTransactionValue ? 'pl-7' : 'pl-3'} pr-3 py-2.5 border border-gray-300 rounded-lg transition bg-gray-50 text-sm`}
                      placeholder="0.00"
                      step="0.01"
                      min="0"
                      required
                    />
                  </div>
                  {errors.averageTransactionValue && <p className="mt-1 text-xs text-red-600">{errors.averageTransactionValue}</p>}
                </div>

                <div>
                  <label className="block text-xs text-gray-700 mb-1.5">
                    Monthly Transactions *
                  </label>
                  <input
                    type="number"
                    value={formData.monthlyTransactions}
                    onKeyDown={preventNegativeNumericInput}
                    onChange={(e) => {
                      const newValue = e.target.value;
                      if (/^\d*$/.test(newValue)) {
                        updateField('monthlyTransactions', newValue);
                        if (errors.monthlyTransactions) {
                          setErrors((prev) => ({ ...prev, monthlyTransactions: undefined }));
                        }
                      }
                    }}
                    className="merchant-focus-field w-full px-3 py-2.5 border border-gray-300 rounded-lg transition bg-gray-50 text-sm"
                    placeholder="0"
                    min="0"
                    required
                  />
                  {errors.monthlyTransactions && <p className="mt-1 text-xs text-red-600">{errors.monthlyTransactions}</p>}
                </div>

                <div className="bg-gradient-to-r from-blue-50 to-orange-50 p-3 rounded-lg border border-blue-100">
                  <p className="text-xs text-gray-700">
                    <span className="font-semibold">Estimated Monthly Volume: </span>
                    ${((parseFloat(formData.averageTransactionValue) || 0) * (parseInt(formData.monthlyTransactions) || 0)).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </div>
            
            {/* Navigation buttons for step 2 */}
            <div className="flex justify-between mt-8 pt-5 border-t border-gray-200">
              <button
                type="button"
                onClick={prevStep}
                disabled={currentStep === 1}
                className="flex items-center px-5 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium text-sm"
              >
                <ChevronLeft className="w-4 h-4 mr-1.5" />
                Previous
              </button>

              <button
                type="button"
                onClick={nextStep}
                disabled={!isStepValid()}
                className="flex items-center px-5 py-2.5 text-white bg-[#6CAFF3] rounded-lg hover:bg-[#5B9FED] disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg font-medium text-sm"
              >
                Next
                <ChevronRight className="w-4 h-4 ml-1.5" />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Payment Methods */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-gray-900 mb-5 text-xl">Card Types</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-gray-700 mb-3">
                    Payment Brands Accepted *
                  </label>
                  <div className="space-y-3 mb-1">
                    {[
                      { value: 'visa', label: 'Visa' },
                      { value: 'mastercard', label: 'Mastercard' },
                      { value: 'amex', label: 'American Express' },
                    ].map((card) => (
                      <label
                        key={card.value}
                        className="flex items-center p-3 border border-gray-300 rounded-lg cursor-pointer hover:bg-gradient-to-r hover:from-blue-50 hover:to-orange-50 hover:border-blue-300 transition"
                      >
                        <input
                          type="checkbox"
                          checked={formData.cardTypes.includes(card.value)}
                          onChange={() => toggleArrayValue('cardTypes', card.value)}
                          className="w-4 h-4 text-blue-500 rounded focus:ring-2 focus:ring-blue-400"
                        />
                        <span className="ml-2 text-gray-700 text-sm">{card.label}</span>
                      </label>
                    ))}
                  </div>
                  {errors.cardTypes && <p className="mt-1 text-xs text-red-600">{errors.cardTypes}</p>}
                </div>
              </div>
            </div>
            
            {/* Navigation buttons for step 3 */}
            <div className="flex justify-between mt-8 pt-5 border-t border-gray-200">
              <button
                type="button"
                onClick={prevStep}
                disabled={currentStep === 1}
                className="flex items-center px-5 py-2.5 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium text-sm"
              >
                <ChevronLeft className="w-4 h-4 mr-1.5" />
                Previous
              </button>

              <button
                type="submit"
                disabled={!isStepValid()}
                className="flex items-center px-5 py-2.5 text-white bg-[#6CAFF3] rounded-lg hover:bg-[#5B9FED] disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg font-medium text-sm"
              >
                Get My Quote
                <ChevronRight className="w-4 h-4 ml-1.5" />
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}