import { DollarSign, TrendingUp, ChevronLeft, ChevronRight } from 'lucide-react';

interface SidebarProps {
  activeTab: 'current-rates' | 'desired-margin';
  onTabChange: (tab: 'current-rates' | 'desired-margin') => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({ activeTab, onTabChange, isCollapsed, onToggleCollapse }: SidebarProps) {
  return (
    <div className={`bg-gray-900 min-h-screen transition-all duration-300 relative ${
      isCollapsed ? 'w-20' : 'w-64'
    }`}>
      <div className="p-4 flex flex-col gap-2">
        {/* Current Rates Tab */}
        <button
          onClick={() => onTabChange('current-rates')}
          className={`relative flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-300 ${
            activeTab === 'current-rates'
              ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg'
              : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
          }`}
          title={isCollapsed ? 'Current Rates' : ''}
        >
          <div
            className={`flex items-center justify-center w-10 h-10 rounded-full transition-all duration-300 ${
              activeTab === 'current-rates'
                ? 'bg-white/20 scale-110'
                : 'bg-gray-800'
            }`}
          >
            <DollarSign className="w-5 h-5" />
          </div>
          {!isCollapsed && <span className="font-medium">Current Rates</span>}
          
          {/* Animated indicator */}
          {activeTab === 'current-rates' && (
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-white rounded-l-full" />
          )}
        </button>

        {/* Desired Margin Tab */}
        <button
          onClick={() => onTabChange('desired-margin')}
          className={`relative flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-300 ${
            activeTab === 'desired-margin'
              ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg'
              : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
          }`}
          title={isCollapsed ? 'Desired Margin' : ''}
        >
          <div
            className={`flex items-center justify-center w-10 h-10 rounded-full transition-all duration-300 ${
              activeTab === 'desired-margin'
                ? 'bg-white/20 scale-110'
                : 'bg-gray-800'
            }`}
          >
            <TrendingUp className="w-5 h-5" />
          </div>
          {!isCollapsed && <span className="font-medium">Desired Margin</span>}
          
          {/* Animated indicator */}
          {activeTab === 'desired-margin' && (
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-white rounded-l-full" />
          )}
        </button>
      </div>

      {/* Toggle Button */}
      <button
        onClick={onToggleCollapse}
        className="absolute -right-3 top-8 bg-gray-900 text-gray-400 hover:text-white border-2 border-gray-700 rounded-full p-1 transition-colors duration-200 shadow-lg"
        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {isCollapsed ? (
          <ChevronRight className="w-4 h-4" />
        ) : (
          <ChevronLeft className="w-4 h-4" />
        )}
      </button>
    </div>
  );
}