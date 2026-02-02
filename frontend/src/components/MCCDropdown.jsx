import React, { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';

// Sample MCC codes
const MCC_CODES = [
  { code: '5812', description: 'Eating Places and Restaurants' },
  { code: '5411', description: 'Grocery Stores and Supermarkets' },
  { code: '5541', description: 'Service Stations' },
  { code: '5311', description: 'Department Stores' },
  { code: '5912', description: 'Drug Stores and Pharmacies' },
  { code: '5999', description: 'Miscellaneous Retail Stores' },
  { code: '7011', description: 'Hotels, Motels, Resorts' },
  { code: '5814', description: 'Fast Food Restaurants' },
  { code: '5941', description: 'Sporting Goods Stores' },
  { code: '5942', description: 'Book Stores' },
  { code: '5944', description: 'Jewelry Stores' },
  { code: '5945', description: 'Hobby, Toy, and Game Shops' },
  { code: '7230', description: 'Barber and Beauty Shops' },
  { code: '7298', description: 'Health and Beauty Spas' },
  { code: '7372', description: 'Computer Programming Services' },
  { code: '7512', description: 'Automobile Rental Agency' },
  { code: '7523', description: 'Parking Lots and Garages' },
  { code: '7832', description: 'Motion Picture Theaters' },
  { code: '7922', description: 'Theatrical Producers and Ticket Agencies' },
  { code: '7992', description: 'Golf Courses - Public' },
];

const MCCDropdown = ({ value, onChange, error }) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [customMode, setCustomMode] = useState(false);

  const filteredCodes = MCC_CODES.filter(mcc =>
    mcc.code.includes(search) || mcc.description.toLowerCase().includes(search.toLowerCase())
  );

  const selectedMCC = MCC_CODES.find(mcc => mcc.code === value);
  const isCustomValue = value && !selectedMCC;

  const handleCustomSubmit = () => {
    if (search.trim()) {
      onChange(search.trim());
      setOpen(false);
      setSearch('');
      setCustomMode(false);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between px-4 py-3 border rounded-2xl focus:ring-2 focus:ring-[#44D62C] focus:border-[#44D62C] bg-white text-left ${
          error ? 'border-red-500' : 'border-gray-300'
        }`}
      >
        <span className={value ? 'text-gray-900' : 'text-gray-400'}>
          {selectedMCC ? `${selectedMCC.code} - ${selectedMCC.description}` : isCustomValue ? value : 'Select or enter MCC...'}
        </span>
        <ChevronsUpDown className="w-4 h-4 text-gray-400" />
      </button>

      {open && (
        <div className="absolute z-50 w-full mt-2 bg-white border border-gray-200 rounded-2xl shadow-lg max-h-80 overflow-hidden">
          <div className="p-3 border-b border-gray-200">
            <input
              type="text"
              placeholder="Search or enter custom MCC code..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && customMode) {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#44D62C] focus:border-[#44D62C] text-sm"
            />
          </div>
          <div className="max-h-60 overflow-y-auto">
            {filteredCodes.length === 0 ? (
              <div className="p-4 space-y-2">
                <div className="text-center text-sm text-gray-500">
                  No matching MCC codes found
                </div>
                {search.trim() && (
                  <button
                    onClick={handleCustomSubmit}
                    className="w-full px-4 py-2 bg-[#44D62C] hover:bg-[#3BC424] text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    Use "{search.trim()}" as custom MCC
                  </button>
                )}
              </div>
            ) : (
              <>
                {filteredCodes.map((mcc) => (
                  <div
                    key={mcc.code}
                    onClick={() => {
                      onChange(mcc.code);
                      setOpen(false);
                      setSearch('');
                      setCustomMode(false);
                    }}
                    className={`px-4 py-3 cursor-pointer hover:bg-green-50 transition-colors flex items-center justify-between ${
                      value === mcc.code ? 'bg-green-50' : ''
                    }`}
                  >
                    <div>
                      <div className="font-medium text-sm text-gray-900">{mcc.code}</div>
                      <div className="text-xs text-gray-600">{mcc.description}</div>
                    </div>
                    {value === mcc.code && <Check className="w-4 h-4 text-[#44D62C]" />}
                  </div>
                ))}
                {search.trim() && (
                  <div className="border-t border-gray-200 p-3">
                    <button
                      onClick={handleCustomSubmit}
                      className="w-full px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors"
                    >
                      Use "{search.trim()}" as custom MCC
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {error && (
        <p className="mt-1 text-sm text-red-600">{error}</p>
      )}

      {/* Overlay to close dropdown when clicking outside */}
      {open && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setOpen(false)}
        />
      )}
    </div>
  );
};

export default MCCDropdown;
