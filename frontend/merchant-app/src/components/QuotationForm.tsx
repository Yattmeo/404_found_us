import { useState } from 'react';
import { ChevronRight, ChevronLeft } from 'lucide-react';
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

const industryOptionLabels = new Set(industryOptions.map((option) => option.label.toLowerCase()));

export function QuotationForm({ onSubmit }: QuotationFormProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 3;
  const [processingType, setProcessingType] = useState<'both' | 'online' | 'offline'>('both');

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
    const industryValue = formData.industry.trim();
    if (!industryValue) {
      return 'Industry is required.';
    }

    if (!industryOptionLabels.has(industryValue.toLowerCase())) {
      return 'Select a valid industry from the dropdown list.';
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
      return 'Select at least one payment channel.';
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

    const normalizedAverageTransactionValue = Number(formData.averageTransactionValue || 0).toFixed(2);
    const normalizedMonthlyTransactions = String(parseInt(formData.monthlyTransactions || '0', 10));
    const matchedIndustry = industryOptions.find(
      (option) => option.label.toLowerCase() === formData.industry.trim().toLowerCase(),
    );

    onSubmit({
      ...formData,
      industry: matchedIndustry?.label ?? formData.industry.trim(),
      averageTransactionValue: normalizedAverageTransactionValue,
      monthlyTransactions: normalizedMonthlyTransactions,
    });
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
    <div className="merchant-form-shell">
      <div className="mb-8">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-gray-600">Step {currentStep} of {totalSteps}</span>
          <span className="text-sm text-gray-600">{Math.round((currentStep / totalSteps) * 100)}%</span>
        </div>
        <div className="merchant-progress-track">
          <div className="merchant-progress-fill" style={{ width: `${(currentStep / totalSteps) * 100}%` }} />
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {currentStep === 1 && (
          <div className="space-y-6">
            <div>
              <h3 className="text-gray-900 mb-6">Business Information</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-700 mb-2">Business Name *</label>
                  <input
                    type="text"
                    value={formData.businessName}
                    onChange={(e) => {
                      updateField('businessName', e.target.value);
                      if (errors.businessName) setErrors((prev) => ({ ...prev, businessName: undefined }));
                    }}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition"
                    placeholder="Enter your business name"
                    required
                  />
                  {errors.businessName && <p className="mt-1 text-xs text-red-600">{errors.businessName}</p>}
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-2">Industry *</label>
                  <input
                    type="text"
                    list="industry-options"
                    value={formData.industry}
                    onChange={(e) => {
                      updateField('industry', e.target.value);
                      if (errors.industry) setErrors((prev) => ({ ...prev, industry: undefined }));
                    }}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition"
                    placeholder="Type or select MCC industry"
                    required
                  />
                  <datalist id="industry-options">
                    {industryOptions.map((industry) => (
                      <option key={industry.value} value={industry.label} />
                    ))}
                  </datalist>
                  {errors.industry && <p className="mt-1 text-xs text-red-600">{errors.industry}</p>}
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === 2 && (
          <div className="space-y-6">
            <div>
              <h3 className="text-gray-900 mb-6">Transaction Details</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-700 mb-2">Average Transaction Value ($) *</label>
                  <input
                    type="number"
                    value={formData.averageTransactionValue}
                    onKeyDown={preventNegativeNumericInput}
                    onChange={(e) => {
                      const newValue = e.target.value;
                      if (/^\d*(\.\d{0,2})?$/.test(newValue)) {
                        updateField('averageTransactionValue', newValue);
                        if (errors.averageTransactionValue) setErrors((prev) => ({ ...prev, averageTransactionValue: undefined }));
                      }
                    }}
                    onBlur={() => {
                      const value = formData.averageTransactionValue.trim();
                      if (value !== '' && /^\d+(\.\d{1,2})?$/.test(value)) {
                        updateField('averageTransactionValue', Number(value).toFixed(2));
                      }
                    }}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition"
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                    required
                  />
                  {errors.averageTransactionValue && <p className="mt-1 text-xs text-red-600">{errors.averageTransactionValue}</p>}
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-2">Monthly Transactions *</label>
                  <input
                    type="number"
                    value={formData.monthlyTransactions}
                    onKeyDown={preventNegativeNumericInput}
                    onChange={(e) => {
                      const newValue = e.target.value;
                      if (/^\d*$/.test(newValue)) {
                        updateField('monthlyTransactions', newValue);
                        if (errors.monthlyTransactions) setErrors((prev) => ({ ...prev, monthlyTransactions: undefined }));
                      }
                    }}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition"
                    placeholder="0"
                    min="0"
                    required
                  />
                  {errors.monthlyTransactions && <p className="mt-1 text-xs text-red-600">{errors.monthlyTransactions}</p>}
                </div>

                <div className="bg-green-50 p-4 rounded-lg border border-green-100">
                  <p className="text-sm text-gray-700">
                    <span className="font-semibold">Estimated Monthly Volume: </span>
                    ${((parseFloat(formData.averageTransactionValue) || 0) * (parseInt(formData.monthlyTransactions) || 0)).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="space-y-6">
            <div>
              <h3 className="text-gray-900 mb-6">Card Types &amp; Payment Processing</h3>
              <div className="space-y-6">
                <div>
                  <label className="block text-sm text-gray-700 mb-4">Which card types do you need? *</label>
                  <div className="space-y-3">
                    {[
                      { value: 'visa', label: 'Visa' },
                      { value: 'mastercard', label: 'Mastercard' },
                    ].map((card) => (
                      <label
                        key={card.value}
                        className="flex items-center gap-4 p-4 border border-gray-300 rounded-lg cursor-pointer hover:bg-green-50 hover:border-green-300 transition"
                      >
                        <input
                          type="checkbox"
                          checked={formData.cardTypes.includes(card.value)}
                          onChange={() => toggleArrayValue('cardTypes', card.value)}
                          className="w-5 h-5 text-green-500 rounded focus:ring-2 focus:ring-green-500"
                        />
                        <span className="text-gray-700">{card.label}</span>
                      </label>
                    ))}
                  </div>
                  {errors.cardTypes && <p className="mt-1 text-xs text-red-600">{errors.cardTypes}</p>}
                </div>

                <div>
                  <label className="block text-sm text-gray-700 mb-2">How would you like to accept payments? *</label>
                  <select
                    value={processingType}
                    onChange={(e) => setProcessingType(e.target.value as 'both' | 'online' | 'offline')}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition"
                    required
                  >
                    <option value="both">Both Online and Offline</option>
                    <option value="online">Online Only</option>
                    <option value="offline">Offline Only (In-person)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="merchant-form-nav">
          <button
            type="button"
            onClick={prevStep}
            disabled={currentStep === 1}
            className="merchant-nav-btn flex items-center px-6 py-3 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <ChevronLeft className="w-5 h-5 mr-2" />
            Previous
          </button>

          {currentStep < totalSteps ? (
            <button
              type="button"
              onClick={nextStep}
              disabled={!isStepValid()}
              className="merchant-nav-btn flex items-center px-6 py-3 text-white bg-green-500 rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              Next
              <ChevronRight className="w-5 h-5 ml-2" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!isStepValid()}
              className="merchant-nav-btn flex items-center px-6 py-3 text-white bg-green-500 rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              Get My Quote
              <ChevronRight className="w-5 h-5 ml-2" />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}