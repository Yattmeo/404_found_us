import { useState, useEffect, useRef } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem } from './ui/command';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Button } from './ui/button';

// Sample MCC codes with descriptions
const MCC_CODES = [
  { code: '5812', description: 'Eating Places and Restaurants' },
  { code: '5411', description: 'Grocery Stores and Supermarkets' },
  { code: '5541', description: 'Service Stations (with or without ancillary services)' },
  { code: '5311', description: 'Department Stores' },
  { code: '5912', description: 'Drug Stores and Pharmacies' },
  { code: '5999', description: 'Miscellaneous and Specialty Retail Stores' },
  { code: '7011', description: 'Hotels, Motels, Resorts' },
  { code: '4111', description: 'Transportation - Suburban and Local Commuter Passenger' },
  { code: '5813', description: 'Drinking Places (Alcoholic Beverages) - Bars, Taverns, Nightclubs' },
  { code: '5814', description: 'Fast Food Restaurants' },
  { code: '5921', description: 'Package Stores - Beer, Wine, and Liquor' },
  { code: '5932', description: 'Antique Shops - Sales, Repairs, and Restoration Services' },
  { code: '5933', description: 'Pawn Shops' },
  { code: '5935', description: 'Wrecking and Salvage Yards' },
  { code: '5937', description: 'Antique Reproduction Stores' },
  { code: '5940', description: 'Bicycle Shops - Sales and Service' },
  { code: '5941', description: 'Sporting Goods Stores' },
  { code: '5942', description: 'Book Stores' },
  { code: '5943', description: 'Stationery Stores, Office and School Supply Stores' },
  { code: '5944', description: 'Jewelry Stores, Watches, Clocks, and Silverware Stores' },
  { code: '5945', description: 'Hobby, Toy, and Game Shops' },
  { code: '5946', description: 'Camera and Photographic Supply Stores' },
  { code: '5947', description: 'Card Shops, Gift, Novelty, and Souvenir Shops' },
  { code: '5948', description: 'Leather Goods and Luggage Stores' },
  { code: '5949', description: 'Sewing, Needlework, Fabric, and Piece Goods Stores' },
  { code: '5950', description: 'Glassware and Crystal Stores' },
  { code: '5971', description: 'Art Dealers and Galleries' },
  { code: '5972', description: 'Stamp and Coin Stores' },
  { code: '5973', description: 'Religious Goods Stores' },
  { code: '5975', description: 'Hearing Aids - Sales, Service, and Supply Stores' },
  { code: '5976', description: 'Orthopedic Goods and Prosthetic Devices' },
  { code: '5977', description: 'Cosmetic Stores' },
  { code: '5978', description: 'Typewriter Stores - Sales, Rentals, Service' },
  { code: '5983', description: 'Fuel Dealers - Fuel Oil, Wood, Coal, and Liquefied Petroleum' },
  { code: '5992', description: 'Florists' },
  { code: '5993', description: 'Cigar Stores and Stands' },
  { code: '5994', description: 'News Dealers and Newsstands' },
  { code: '5995', description: 'Pet Shops, Pet Food, and Supplies' },
  { code: '5996', description: 'Swimming Pools - Sales, Service, and Supplies' },
  { code: '5997', description: 'Electric Razor Stores - Sales and Service' },
  { code: '5998', description: 'Tent and Awning Shops' },
  { code: '7230', description: 'Barber and Beauty Shops' },
  { code: '7298', description: 'Health and Beauty Spas' },
  { code: '7311', description: 'Advertising Services' },
  { code: '7321', description: 'Consumer Credit Reporting Agencies' },
  { code: '7333', description: 'Commercial Photography, Art and Graphics' },
  { code: '7338', description: 'Quick Copy, Reproduction, and Blueprinting Services' },
  { code: '7339', description: 'Stenographic and Secretarial Support Services' },
  { code: '7342', description: 'Exterminating and Disinfecting Services' },
  { code: '7349', description: 'Cleaning, Maintenance, and Janitorial Services' },
  { code: '7361', description: 'Employment Agencies and Temporary Help Services' },
  { code: '7372', description: 'Computer Programming, Data Processing, and Integrated Systems Design Services' },
  { code: '7375', description: 'Information Retrieval Services' },
  { code: '7379', description: 'Computer Maintenance, Repair, and Services' },
  { code: '7392', description: 'Management, Consulting, and Public Relations Services' },
  { code: '7393', description: 'Detective Agencies, Protective Agencies, and Security Services' },
  { code: '7394', description: 'Equipment, Tool, Furniture, and Appliance Rentals and Leasing' },
  { code: '7395', description: 'Photofinishing Laboratories and Photo Developing' },
  { code: '7399', description: 'Business Services - Not Elsewhere Classified' },
  { code: '7512', description: 'Automobile Rental Agency' },
  { code: '7513', description: 'Truck and Utility Trailer Rentals' },
  { code: '7519', description: 'Motor Home and Recreational Vehicle Rentals' },
  { code: '7523', description: 'Parking Lots and Garages' },
  { code: '7531', description: 'Automotive Body Repair Shops' },
  { code: '7534', description: 'Tire Retreading and Repair Shops' },
  { code: '7535', description: 'Automotive Paint Shops' },
  { code: '7538', description: 'Automotive Service Shops (Non-dealer)' },
  { code: '7542', description: 'Car Washes' },
  { code: '7549', description: 'Towing Services' },
  { code: '7622', description: 'Electronics Repair Shops' },
  { code: '7623', description: 'Air Conditioning and Refrigeration Repair Shops' },
  { code: '7629', description: 'Electrical and Small Appliance Repair Shops' },
  { code: '7631', description: 'Watch, Clock, and Jewelry Repair Shops' },
  { code: '7641', description: 'Furniture - Reupholstery, Repair, and Refinishing' },
  { code: '7692', description: 'Welding Services' },
  { code: '7699', description: 'Miscellaneous Repair Shops and Related Services' },
  { code: '7800', description: 'Government-Owned Lotteries' },
  { code: '7801', description: 'Government-Licensed On-Line Casinos (Online Gambling)' },
  { code: '7802', description: 'Government-Licensed Horse/Dog Racing' },
  { code: '7829', description: 'Motion Picture and Video Tape Production and Distribution' },
  { code: '7832', description: 'Motion Picture Theaters' },
  { code: '7841', description: 'Video Tape Rental Stores' },
  { code: '7911', description: 'Dance Halls, Studios, and Schools' },
  { code: '7922', description: 'Theatrical Producers (Except Motion Pictures) and Ticket Agencies' },
  { code: '7929', description: 'Bands, Orchestras, and Miscellaneous Entertainers' },
  { code: '7932', description: 'Billiard and Pool Establishments' },
  { code: '7933', description: 'Bowling Alleys' },
  { code: '7941', description: 'Commercial Sports, Professional Sports Clubs, Athletic Fields, and Sports Promoters' },
  { code: '7991', description: 'Tourist Attractions and Exhibits' },
  { code: '7992', description: 'Golf Courses - Public' },
  { code: '7993', description: 'Video Amusement Game Supplies' },
  { code: '7994', description: 'Video Game Arcades and Establishments' },
  { code: '7995', description: 'Betting (including Lottery Tickets, Casino Gaming Chips, Off-track Betting, and Wagers)' },
  { code: '7996', description: 'Amusement Parks, Carnivals, Circuses, Fortune Tellers' },
  { code: '7997', description: 'Membership Clubs (Sports, Recreation, Athletic), Country Clubs, and Private Golf Courses' },
  { code: '7998', description: 'Aquariums, Seaquariums, and Dolphinariums' },
  { code: '7999', description: 'Recreation Services - Not Elsewhere Classified' },
  { code: '8011', description: 'Doctors and Physicians (Not Elsewhere Classified)' },
  { code: '8021', description: 'Dentists and Orthodontists' },
  { code: '8031', description: 'Osteopaths' },
  { code: '8041', description: 'Chiropractors' },
  { code: '8042', description: 'Optometrists and Ophthalmologists' },
  { code: '8043', description: 'Opticians, Optical Goods, and Eyeglasses' },
  { code: '8049', description: 'Podiatrists and Chiropodists' },
  { code: '8050', description: 'Nursing and Personal Care Facilities' },
  { code: '8062', description: 'Hospitals' },
  { code: '8071', description: 'Medical and Dental Laboratories' },
  { code: '8099', description: 'Medical Services and Health Practitioners (Not Elsewhere Classified)' },
];

interface MCCDropdownProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

export function MCCDropdown({ value, onChange, error }: MCCDropdownProps) {
  const [open, setOpen] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  const selectedMCC = MCC_CODES.find(mcc => mcc.code === value);

  return (
    <div className="space-y-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className={`w-full justify-between h-auto py-3 px-4 rounded-2xl ${
              error ? 'border-red-500' : 'border-gray-300'
            } hover:border-orange-400 focus:ring-2 focus:ring-orange-500 focus:border-transparent`}
          >
            <div className="text-left flex-1">
              {selectedMCC ? (
                <div>
                  <span className="font-medium">{selectedMCC.code}</span>
                  <span className="text-gray-500 ml-2">- {selectedMCC.description}</span>
                </div>
              ) : (
                <span className="text-gray-500">Search MCC code or description...</span>
              )}
            </div>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[600px] p-0" align="start">
          <Command>
            <CommandInput 
              placeholder="Type to search MCC code or description..." 
              value={searchValue}
              onValueChange={setSearchValue}
            />
            <CommandEmpty>No MCC code found.</CommandEmpty>
            <CommandGroup className="max-h-[300px] overflow-auto">
              {MCC_CODES.filter(mcc => 
                mcc.code.includes(searchValue) || 
                mcc.description.toLowerCase().includes(searchValue.toLowerCase())
              ).map((mcc) => (
                <CommandItem
                  key={mcc.code}
                  value={mcc.code}
                  onSelect={(currentValue) => {
                    onChange(currentValue === value ? '' : currentValue);
                    setOpen(false);
                    setSearchValue('');
                  }}
                  className="cursor-pointer"
                >
                  <Check
                    className={`mr-2 h-4 w-4 ${
                      value === mcc.code ? 'opacity-100' : 'opacity-0'
                    }`}
                  />
                  <div className="flex-1">
                    <span className="font-medium">{mcc.code}</span>
                    <span className="text-gray-600 ml-2">- {mcc.description}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </Command>
        </PopoverContent>
      </Popover>
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
