
import React, { useState, useCallback, useRef } from 'react';
import { UploadIcon } from './icons';

interface DataUploadProps {
  onUpload: (ticketFile: File, chatFile: File, ticketSample: string[][], chatSample: string[][]) => void;
  isLoading: boolean;
  error: string | null;
}

const parseCSV = (file: File): Promise<string[][]> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const rows = text.split('\n').map(row => row.split(','));
      resolve(rows);
    };
    reader.onerror = (error) => reject(error);
    reader.readAsText(file);
  });
};

const FileInput: React.FC<{ id: string; label: string; file: File | null; onFileChange: (file: File) => void; }> = ({ id, label, file, onFileChange }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  
  const handleDragOver = (e: React.DragEvent<HTMLLabelElement>) => e.preventDefault();
  const handleDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileChange(e.dataTransfer.files[0]);
    }
  };

  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</label>
      <label
        htmlFor={id}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`mt-1 flex justify-center w-full px-6 pt-5 pb-6 border-2 border-gray-300 dark:border-gray-600 border-dashed rounded-md cursor-pointer ${file ? 'border-indigo-500' : ''}`}
      >
        <div className="space-y-1 text-center">
          <UploadIcon className="mx-auto h-12 w-12 text-gray-400" />
          <div className="flex text-sm text-gray-600 dark:text-gray-400">
            <span className="relative rounded-md font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300">
              {file ? 'Replace file' : 'Upload a file'}
            </span>
            <input id={id} name={id} type="file" accept=".csv" className="sr-only" onChange={(e) => e.target.files && onFileChange(e.target.files[0])} ref={inputRef} />
            <p className="pl-1">or drag and drop</p>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-500">CSV up to 10MB</p>
          {file && <p className="text-xs text-green-600 dark:text-green-400 font-semibold mt-2">{file.name}</p>}
        </div>
      </label>
    </div>
  );
};


const DataUpload: React.FC<DataUploadProps> = ({ onUpload, isLoading, error }) => {
  const [ticketFile, setTicketFile] = useState<File | null>(null);
  const [chatFile, setChatFile] = useState<File | null>(null);
  
  const handleSubmit = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    if (ticketFile && chatFile) {
      try {
        const ticketSample = await parseCSV(ticketFile);
        const chatSample = await parseCSV(chatFile);
        onUpload(ticketFile, chatFile, ticketSample, chatSample);
      } catch (err) {
        console.error("Error parsing CSVs", err);
      }
    }
  }, [ticketFile, chatFile, onUpload]);

  return (
    <div className="max-w-xl mx-auto text-center animate-fade-in">
        <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">Upload Your Data</h2>
        <p className="text-gray-600 dark:text-gray-300 mb-8">
            Please provide both customer support ticket and live chat data in CSV format.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
            <FileInput id="ticket-file" label="Support Ticket Data" file={ticketFile} onFileChange={setTicketFile} />
            <FileInput id="chat-file" label="Live Chat Data" file={chatFile} onFileChange={setChatFile} />
            
            {error && <p className="text-red-500 text-sm">{error}</p>}
            
            <button
                type="submit"
                disabled={!ticketFile || !chatFile || isLoading}
                className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
                {isLoading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Analyzing Data...
                  </>
                ) : 'Analyze Data Structure'}
            </button>
        </form>
    </div>
  );
};

export default DataUpload;
