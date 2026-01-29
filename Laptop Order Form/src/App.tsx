import { EnhancedMerchantFeeCalculator } from './components/EnhancedMerchantFeeCalculator';
import { DesiredMarginCalculator } from './components/DesiredMarginCalculator';
import { LandingPage } from './components/LandingPage';
import { useState } from 'react';
import logo from 'figma:asset/79a39c442bd831ff976c31cd6d8bae181881f38b.png';

export default function App() {
  const [currentView, setCurrentView] = useState<'landing' | 'current-rates' | 'desired-margin'>('landing');

  const handleNavigate = (page: 'current-rates' | 'desired-margin') => {
    setCurrentView(page);
  };

  const handleBackToLanding = () => {
    setCurrentView('landing');
  };

  // Show landing page
  if (currentView === 'landing') {
    return <LandingPage onNavigate={handleNavigate} />;
  }

  // Show calculator pages
  return (
    <div className="min-h-screen bg-gray-50">
      {currentView === 'current-rates' && <EnhancedMerchantFeeCalculator onBackToLanding={handleBackToLanding} />}
      {currentView === 'desired-margin' && <DesiredMarginCalculator onBackToLanding={handleBackToLanding} />}
    </div>
  );
}