import React, { useState, useEffect } from 'react';
import PredictionCard from './components/PredictionCard';
import ModelTransparencyPanel from './components/ModelTransparencyPanel';
import SystemHealthPanel from './components/SystemHealthPanel';
import StressTestPanel from './components/StressTestPanel';

const Navigation = ({ theme, setTheme, currency, setCurrency }) => {
  return (
    <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 sticky top-0 z-50 shadow-sm transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center space-x-4">
            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-700 tracking-tight">
              iFly AI Pricing Intelligence
            </span>
            <span className="hidden sm:flex items-center gap-1.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 px-2 py-1 rounded-full border border-emerald-100 dark:border-emerald-800 uppercase tracking-widest">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Pipeline Active
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrency(currency === 'EUR' ? 'INR' : 'EUR')}
              className="px-4 py-2 rounded-xl text-xs font-bold border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
            >
              {currency === 'EUR' ? '€ EUR → ₹ INR' : '₹ INR → € EUR'}
            </button>
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="px-4 py-2 rounded-xl text-xs font-bold border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
            >
              {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [currency, setCurrency] = useState(localStorage.getItem('currency') || 'EUR');

  useEffect(() => {
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem('currency', currency);
  }, [currency]);

  return (
    <div className="min-h-screen overflow-x-hidden bg-gray-50 dark:bg-gray-950 text-slate-900 dark:text-gray-100 font-sans transition-colors">
      <Navigation theme={theme} setTheme={setTheme} currency={currency} setCurrency={setCurrency} />

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Top 3 cards — fixed height containers */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="h-[620px]">
            <PredictionCard currency={currency} />
          </div>
          <div className="h-[620px]">
            <ModelTransparencyPanel currency={currency} />
          </div>
          <div className="h-[620px]">
            <SystemHealthPanel />
          </div>
        </div>

        {/* Full-width Stress Test Engine — fixed height */}
        <div className="mt-8">
          <StressTestPanel />
        </div>
      </main>
    </div>
  );
}

export default App;
