import React, { useState } from 'react';
import LandingPage from './components/LandingPage';
import EnhancedMerchantFeeCalculator from './components/EnhancedMerchantFeeCalculator';
import DesiredMarginCalculator from './components/DesiredMarginCalculator';
import './App.css';

function App() {
  const [currentView, setCurrentView] = useState('landing');

  const handleNavigate = (page) => {
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
      {currentView === 'current-rates' && (
        <EnhancedMerchantFeeCalculator onBackToLanding={handleBackToLanding} />
      )}
      {currentView === 'desired-margin' && (
        <DesiredMarginCalculator onBackToLanding={handleBackToLanding} />
      )}
    </div>
  );
}

export default App;

