import React from 'react';
import AIAnalystChat from './components/AIAnalystChat';

// A simple container to render the AIAnalystChat component for standalone use.
// In a real-world scenario, you would import and use AIAnalystChat directly in your dashboard.
const App: React.FC = () => {
  const apiKey = process.env.API_KEY;
  const googleApiKey = process.env.GOOGLE_API_KEY;
  const googleClientId = process.env.GOOGLE_CLIENT_ID;

  if (!apiKey || !googleApiKey || !googleClientId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-red-50 text-red-800 p-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">Configuration Error</h1>
          <p>One or more required API keys (API_KEY, GOOGLE_API_KEY, GOOGLE_CLIENT_ID) are missing.</p>
          <p>Please ensure they are correctly set up in your environment.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-gray-100 dark:bg-gray-900 font-sans">
       <AIAnalystChat 
        apiKey={apiKey}
        googleApiKey={googleApiKey}
        googleClientId={googleClientId}
       />
    </div>
  );
};

export default App;
