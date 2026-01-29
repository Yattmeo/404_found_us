import { useForm } from 'react-hook-form@7.55.0';
import { Laptop, Check } from 'lucide-react';
import { useState } from 'react';

interface LaptopFormData {
  brand: string;
  model: string;
  processor: string;
  ram: string;
  storage: string;
  storageType: string;
  screenSize: string;
  operatingSystem: string;
  graphicsCard: string;
  serialNumber: string;
  purchaseDate: string;
  price: string;
  condition: string;
  warranty: string;
  color: string;
  notes: string;
}

export function LaptopForm() {
  const [submitted, setSubmitted] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<LaptopFormData>();

  const onSubmit = (data: LaptopFormData) => {
    console.log('Form submitted:', data);
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      reset();
    }, 3000);
  };

  return (
    <div className="bg-white shadow-lg rounded-lg p-8">
      {submitted && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-800">
          <Check className="w-5 h-5" />
          <span>Laptop information submitted successfully!</span>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Basic Information */}
        <div className="border-b border-gray-200 pb-6">
          <div className="flex items-center gap-2 mb-4">
            <Laptop className="w-5 h-5 text-gray-700" />
            <h2 className="text-gray-900">Basic Information</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="brand" className="block text-sm font-medium text-gray-700 mb-2">
                Brand / Manufacturer *
              </label>
              <select
                id="brand"
                {...register('brand', { required: 'Brand is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select a brand</option>
                <option value="Apple">Apple</option>
                <option value="Dell">Dell</option>
                <option value="HP">HP</option>
                <option value="Lenovo">Lenovo</option>
                <option value="ASUS">ASUS</option>
                <option value="Acer">Acer</option>
                <option value="MSI">MSI</option>
                <option value="Samsung">Samsung</option>
                <option value="Microsoft">Microsoft</option>
                <option value="Other">Other</option>
              </select>
              {errors.brand && (
                <p className="mt-1 text-sm text-red-600">{errors.brand.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="model" className="block text-sm font-medium text-gray-700 mb-2">
                Model *
              </label>
              <input
                id="model"
                type="text"
                {...register('model', { required: 'Model is required' })}
                placeholder="e.g., MacBook Pro 14"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {errors.model && (
                <p className="mt-1 text-sm text-red-600">{errors.model.message}</p>
              )}
            </div>
          </div>
        </div>

        {/* Technical Specifications */}
        <div className="border-b border-gray-200 pb-6">
          <h2 className="text-gray-900 mb-4">Technical Specifications</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="processor" className="block text-sm font-medium text-gray-700 mb-2">
                Processor *
              </label>
              <input
                id="processor"
                type="text"
                {...register('processor', { required: 'Processor is required' })}
                placeholder="e.g., Intel Core i7-12700H"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {errors.processor && (
                <p className="mt-1 text-sm text-red-600">{errors.processor.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="ram" className="block text-sm font-medium text-gray-700 mb-2">
                RAM *
              </label>
              <select
                id="ram"
                {...register('ram', { required: 'RAM is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select RAM</option>
                <option value="4GB">4 GB</option>
                <option value="8GB">8 GB</option>
                <option value="16GB">16 GB</option>
                <option value="32GB">32 GB</option>
                <option value="64GB">64 GB</option>
                <option value="128GB">128 GB</option>
              </select>
              {errors.ram && (
                <p className="mt-1 text-sm text-red-600">{errors.ram.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="storage" className="block text-sm font-medium text-gray-700 mb-2">
                Storage Capacity *
              </label>
              <select
                id="storage"
                {...register('storage', { required: 'Storage is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select storage</option>
                <option value="256GB">256 GB</option>
                <option value="512GB">512 GB</option>
                <option value="1TB">1 TB</option>
                <option value="2TB">2 TB</option>
                <option value="4TB">4 TB</option>
              </select>
              {errors.storage && (
                <p className="mt-1 text-sm text-red-600">{errors.storage.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="storageType" className="block text-sm font-medium text-gray-700 mb-2">
                Storage Type *
              </label>
              <select
                id="storageType"
                {...register('storageType', { required: 'Storage type is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select type</option>
                <option value="SSD">SSD</option>
                <option value="NVMe">NVMe SSD</option>
                <option value="HDD">HDD</option>
                <option value="Hybrid">Hybrid (SSD + HDD)</option>
              </select>
              {errors.storageType && (
                <p className="mt-1 text-sm text-red-600">{errors.storageType.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="screenSize" className="block text-sm font-medium text-gray-700 mb-2">
                Screen Size *
              </label>
              <select
                id="screenSize"
                {...register('screenSize', { required: 'Screen size is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select size</option>
                <option value="11">11"</option>
                <option value="12">12"</option>
                <option value="13">13"</option>
                <option value="14">14"</option>
                <option value="15">15"</option>
                <option value="16">16"</option>
                <option value="17">17"</option>
              </select>
              {errors.screenSize && (
                <p className="mt-1 text-sm text-red-600">{errors.screenSize.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="operatingSystem" className="block text-sm font-medium text-gray-700 mb-2">
                Operating System *
              </label>
              <select
                id="operatingSystem"
                {...register('operatingSystem', { required: 'Operating system is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select OS</option>
                <option value="Windows 11">Windows 11</option>
                <option value="Windows 10">Windows 10</option>
                <option value="macOS">macOS</option>
                <option value="Linux">Linux</option>
                <option value="Chrome OS">Chrome OS</option>
              </select>
              {errors.operatingSystem && (
                <p className="mt-1 text-sm text-red-600">{errors.operatingSystem.message}</p>
              )}
            </div>

            <div className="md:col-span-2">
              <label htmlFor="graphicsCard" className="block text-sm font-medium text-gray-700 mb-2">
                Graphics Card
              </label>
              <input
                id="graphicsCard"
                type="text"
                {...register('graphicsCard')}
                placeholder="e.g., NVIDIA RTX 3060"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        </div>

        {/* Purchase & Warranty Information */}
        <div className="border-b border-gray-200 pb-6">
          <h2 className="text-gray-900 mb-4">Purchase & Warranty Information</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="serialNumber" className="block text-sm font-medium text-gray-700 mb-2">
                Serial Number
              </label>
              <input
                id="serialNumber"
                type="text"
                {...register('serialNumber')}
                placeholder="Enter serial number"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label htmlFor="purchaseDate" className="block text-sm font-medium text-gray-700 mb-2">
                Purchase Date
              </label>
              <input
                id="purchaseDate"
                type="date"
                {...register('purchaseDate')}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label htmlFor="price" className="block text-sm font-medium text-gray-700 mb-2">
                Price
              </label>
              <input
                id="price"
                type="number"
                step="0.01"
                {...register('price')}
                placeholder="0.00"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label htmlFor="warranty" className="block text-sm font-medium text-gray-700 mb-2">
                Warranty Period
              </label>
              <select
                id="warranty"
                {...register('warranty')}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select warranty</option>
                <option value="No Warranty">No Warranty</option>
                <option value="1 Year">1 Year</option>
                <option value="2 Years">2 Years</option>
                <option value="3 Years">3 Years</option>
                <option value="Extended">Extended Warranty</option>
              </select>
            </div>

            <div>
              <label htmlFor="condition" className="block text-sm font-medium text-gray-700 mb-2">
                Condition *
              </label>
              <select
                id="condition"
                {...register('condition', { required: 'Condition is required' })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select condition</option>
                <option value="New">New</option>
                <option value="Like New">Like New</option>
                <option value="Good">Good</option>
                <option value="Fair">Fair</option>
                <option value="Refurbished">Refurbished</option>
              </select>
              {errors.condition && (
                <p className="mt-1 text-sm text-red-600">{errors.condition.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="color" className="block text-sm font-medium text-gray-700 mb-2">
                Color
              </label>
              <input
                id="color"
                type="text"
                {...register('color')}
                placeholder="e.g., Space Gray"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        </div>

        {/* Additional Notes */}
        <div className="pb-6">
          <h2 className="text-gray-900 mb-4">Additional Notes</h2>
          
          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-2">
              Notes
            </label>
            <textarea
              id="notes"
              {...register('notes')}
              rows={4}
              placeholder="Any additional information about the laptop..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex gap-4">
          <button
            type="submit"
            className="flex-1 bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Submit Form
          </button>
          <button
            type="button"
            onClick={() => reset()}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  );
}
