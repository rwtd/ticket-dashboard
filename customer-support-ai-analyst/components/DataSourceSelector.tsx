import React from 'react';
import { GoogleDriveIcon, CsvIcon } from './icons';

interface DataSourceSelectorProps {
  onSelect: (source: 'google-sheets' | 'csv') => void;
  isLoading: boolean;
  error: string | null;
}

const DataSourceSelector: React.FC<DataSourceSelectorProps> = ({ onSelect, isLoading, error }) => {
  return (
    <div className="text-center animate-fade-in">
      <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">Connect Your Data</h2>
      <p className="text-gray-600 dark:text-gray-300 mb-8">
        Choose your data source to begin the analysis. Connect with Google Drive for live data and session logging.
      </p>
      {isLoading && (
          <div className="my-4">
              <p className="text-indigo-600 dark:text-indigo-400 animate-pulse">Connecting to Google... Please follow the prompts.</p>
          </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl mx-auto">
        <button
          onClick={() => onSelect('google-sheets')}
          disabled={isLoading}
          className="p-8 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg hover:border-indigo-500 dark:hover:border-indigo-500 hover:bg-indigo-50 dark:hover:bg-gray-700/50 transition-all duration-300 transform hover:scale-105 disabled:opacity-50 disabled:cursor-wait"
        >
          <GoogleDriveIcon className="h-16 w-16 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white">Google Drive</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Use live Sheets data and log sessions to Docs.</p>
        </button>
        <button
          onClick={() => onSelect('csv')}
          disabled={isLoading}
          className="p-8 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:border-indigo-500 dark:hover:border-indigo-500 hover:bg-indigo-50 dark:hover:bg-gray-700/50 transition-all duration-300 transform hover:scale-105 disabled:opacity-50 disabled:cursor-wait"
        >
          <CsvIcon className="h-16 w-16 mx-auto mb-4 text-green-600 dark:text-green-500" />
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white">Upload CSV Files</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Upload your ticket and chat data exports.</p>
        </button>
      </div>
       {error && <p className="text-red-500 text-sm mt-4">{error}</p>}
    </div>
  );
};

export default DataSourceSelector;