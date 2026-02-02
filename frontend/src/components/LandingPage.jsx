import React from 'react';
import { Calculator, TrendingUp, ArrowRight } from 'lucide-react';

const LandingPage = ({ onNavigate }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50 flex items-center justify-center p-8">
      <div className="max-w-5xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-[#313131] mb-4">
            Merchant Fee Calculator
          </h1>
          <p className="text-xl text-[#313131] opacity-70 max-w-2xl mx-auto">
            Get started with your pricing analysis
          </p>
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Current Rates Card */}
          <div 
            className="bg-white rounded-3xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden group cursor-pointer" 
            onClick={() => onNavigate('current-rates')}
          >
            {/* Image with overlay */}
            <div className="relative h-40 sm:h-48 md:h-56 overflow-hidden">
              <img 
                src="https://images.unsplash.com/photo-1709715357441-da1ec3d0bd4a?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMHBlb3BsZSUyMHdvcmtpbmd8ZW58MXx8fHwxNzY4Njc5NjAyfDA&ixlib=rb-4.1.0&q=80&w=1080"
                alt="Business Analytics"
                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent"></div>
              
              {/* Icon on image */}
              <div className="absolute bottom-3 left-3 sm:bottom-4 sm:left-4 w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 rounded-2xl bg-[#44D62C] hover:bg-[#3BC424] flex items-center justify-center group-hover:scale-110 transition-all duration-300 shadow-lg">
                <Calculator className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-white" />
              </div>
            </div>

            <div className="p-4 sm:p-6 md:p-8 text-center">
              {/* Content */}
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2 sm:mb-3">
                Merchant Profitability Calculator
              </h2>
              <p className="text-sm sm:text-base text-gray-600 mb-4 sm:mb-6">
                Assess profitability based on current merchant rates and transaction data
              </p>

              {/* Arrow Button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigate('current-rates');
                }}
                className="inline-flex items-center justify-center gap-2 px-6 py-3 sm:px-8 sm:py-4 bg-[#44D62C] hover:bg-[#3BC424] text-white text-sm sm:text-base font-semibold rounded-xl group-hover:scale-105 transition-all duration-300 shadow-lg hover:shadow-xl"
              >
                <span>Get Started</span>
                <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5" />
              </button>
            </div>
          </div>

          {/* Desired Margin Card */}
          <div 
            className="bg-white rounded-3xl shadow-lg hover:shadow-2xl transition-all duration-300 overflow-hidden group cursor-pointer" 
            onClick={() => onNavigate('desired-margin')}
          >
            {/* Image with overlay */}
            <div className="relative h-40 sm:h-48 md:h-56 overflow-hidden">
              <img 
                src="https://images.unsplash.com/photo-1739298061740-5ed03045b280?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx0ZWFtJTIwY29sbGFib3JhdGlvbiUyMG9mZmljZXxlbnwxfHx8fDE3Njg2NDQ5OTF8MA&ixlib=rb-4.1.0&q=80&w=1080"
                alt="Team Collaboration"
                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent"></div>
              
              {/* Icon on image */}
              <div className="absolute bottom-3 left-3 sm:bottom-4 sm:left-4 w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 rounded-2xl bg-[#44D62C] hover:bg-[#3BC424] flex items-center justify-center group-hover:scale-110 transition-all duration-300 shadow-lg">
                <TrendingUp className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-white" />
              </div>
            </div>

            <div className="p-4 sm:p-6 md:p-8 text-center">
              {/* Content */}
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2 sm:mb-3">
                Rates Quotation Tool
              </h2>
              <p className="text-sm sm:text-base text-gray-600 mb-4 sm:mb-6">
                Analyse the merchant profile and recommend suitable pricing
              </p>

              {/* Arrow Button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigate('desired-margin');
                }}
                className="inline-flex items-center justify-center gap-2 px-6 py-3 sm:px-8 sm:py-4 bg-[#44D62C] hover:bg-[#3BC424] text-white text-sm sm:text-base font-semibold rounded-xl group-hover:scale-105 transition-all duration-300 shadow-lg hover:shadow-xl"
              >
                <span>Get Started</span>
                <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
