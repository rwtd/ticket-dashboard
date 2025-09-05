import React, { useState, useCallback, useEffect } from 'react';
import { ChatMessage, AppStep } from '../types';
import { getGeminiSchemaSuggestion, getGeminiChatResponse } from '../services/geminiService';
import { pickAndLoadSheets } from '../services/googleSheetsService';
import { getAccessToken, init as initGoogleAuth } from '../services/googleAuthService';
import { createLogDoc, appendToDoc } from '../services/googleLogService';
import DataSourceSelector from './DataSourceSelector';
import DataUpload from './DataUpload';
import ChatInterface from './ChatInterface';
import { LogoIcon } from './icons';
import StepIndicator from './StepIndicator';

interface AIAnalystChatProps {
    apiKey: string;
    googleApiKey: string;
    googleClientId: string;
    initialTicketData?: string[][];
    initialChatData?: string[][];
    containerClassName?: string;
}

const AIAnalystChat: React.FC<AIAnalystChatProps> = ({
    apiKey,
    googleApiKey,
    googleClientId,
    initialTicketData,
    initialChatData,
    containerClassName = "w-full max-w-4xl mx-auto"
}) => {
  const [step, setStep] = useState<AppStep>(AppStep.SelectDataSource);
  const [ticketFile, setTicketFile] = useState<File | null>(null);
  const [chatFile, setChatFile] = useState<File | null>(null);
  const [ticketData, setTicketData] = useState<string[][] | null>(null);
  const [chatData, setChatData] = useState<string[][] | null>(null);
  const [suggestedSchema, setSuggestedSchema] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  
  const [logDocumentId, setLogDocumentId] = useState<string | null>(null);
  const [googleAccessToken, setGoogleAccessToken] = useState<string | null>(null);

  // Effect to handle pre-loaded initial data
  useEffect(() => {
    if (initialTicketData && initialChatData) {
      setTicketData(initialTicketData);
      setChatData(initialChatData);
      // Skip to schema confirmation
      setIsLoading(true);
      setError(null);
      getGeminiSchemaSuggestion(apiKey, initialTicketData, initialChatData)
        .then(schema => {
          setSuggestedSchema(schema);
          setStep(AppStep.ConfirmSchema);
        })
        .catch(err => {
          if (err instanceof Error) {
            setError(err.message);
          } else {
            setError('An unknown error occurred while analyzing the initial data.');
          }
          // If schema fails, go back to start
          setStep(AppStep.SelectDataSource);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [initialTicketData, initialChatData, apiKey]);


  const handleDataSourceSelect = async (source: 'google-sheets' | 'csv') => {
    setError(null);
    if (source === 'csv') {
      setStep(AppStep.UploadData);
    } else {
      setIsLoading(true);
      try {
        const { ticketData: newTicketData, chatData: newChatData, accessToken } = await pickAndLoadSheets(googleApiKey, googleClientId);
        
        if (!newTicketData || newTicketData.length === 0 || !newChatData || newChatData.length === 0) {
          throw new Error("Selected Google Sheets are empty or could not be read. Please ensure they contain data and you selected two files.");
        }
        
        setTicketData(newTicketData);
        setChatData(newChatData);
        setTicketFile(null);
        setChatFile(null);
        setGoogleAccessToken(accessToken); // Save token for logging

        const schema = await getGeminiSchemaSuggestion(apiKey, newTicketData, newChatData);
        setSuggestedSchema(schema);
        setStep(AppStep.ConfirmSchema);

      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('An unknown error occurred while connecting to Google Sheets.');
        }
        console.error(err);
        setStep(AppStep.SelectDataSource);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleDataUpload = async (tickets: File, chats: File, ticketSample: string[][], chatSample: string[][]) => {
    setTicketFile(tickets);
    setChatFile(chats);
    setTicketData(ticketSample);
    setChatData(chatSample);
    setIsLoading(true);
    setError(null);

    try {
      const schema = await getGeminiSchemaSuggestion(apiKey, ticketSample, chatSample);
      setSuggestedSchema(schema);
      setStep(AppStep.ConfirmSchema);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unknown error occurred while analyzing the data. Please try again.');
      }
      console.error(err);
      setStep(AppStep.UploadData);
    } finally {
      setIsLoading(false);
    }
  };

  const initializeLogging = async () => {
    try {
        await initGoogleAuth(googleApiKey, googleClientId);
        let token = googleAccessToken;
        if (!token) {
            const newAccessToken = await getAccessToken(['https://www.googleapis.com/auth/documents']);
            setGoogleAccessToken(newAccessToken);
            token = newAccessToken;
        }

        if (token) {
            const docId = await createLogDoc(token, `AI Analyst Session Log - ${new Date().toLocaleString()}`);
            setLogDocumentId(docId);
            const initialLogContent = `Session Started: ${new Date().toISOString()}\nData Sources:\n  - Tickets: ${ticketFile?.name || 'Google Sheet' || 'Pre-loaded Data'}\n  - Chats: ${chatFile?.name || 'Google Sheet' || 'Pre-loaded Data'}\n\n---\n\n`;
            await appendToDoc(token, docId, initialLogContent);
        }
    } catch (logError) {
        console.warn("Could not initialize logging to Google Docs.", logError);
    }
  };

  const handleConfirmSchema = async () => {
    await initializeLogging();
    setStep(AppStep.Chat);
    setMessages([
      {
        sender: 'ai',
        text: "Data loaded successfully! I've analyzed the structure of your ticket and chat data. You can now ask questions or upload files for analysis. How can I help you?",
      },
    ]);
  };

  const logMessage = async (message: ChatMessage) => {
    if (logDocumentId && googleAccessToken) {
        try {
            const prefix = message.sender === 'user' ? 'User' : 'AI';
            let logText = `[${new Date().toLocaleTimeString()}] ${prefix}: ${message.text}\n`;
            if (message.file) {
                logText += `  (Attached file: ${message.file.name})\n`;
            }
            await appendToDoc(googleAccessToken, logDocumentId, logText);
        } catch (error) {
            console.warn("Failed to log message:", error);
        }
    }
};

  const handleSendMessage = useCallback(async (message: string, file?: File | null) => {
    if (!ticketData || !chatData) return;

    const userMessage: ChatMessage = { sender: 'user', text: message };
    if (file) {
      userMessage.file = { name: file.name, type: file.type };
    }

    setMessages(prev => [...prev, userMessage]);
    await logMessage(userMessage);
    setIsLoading(true);

    try {
      const aiResponse = await getGeminiChatResponse(apiKey, message, ticketData, chatData, messages, file);
      const aiMessage: ChatMessage = { sender: 'ai', text: aiResponse };
      setMessages(prev => [...prev, aiMessage]);
      await logMessage(aiMessage);
    } catch (err) {
      console.error(err);
      let errorText = 'Sorry, I encountered an error. Please try again.';
      if (err instanceof Error) {
        errorText = err.message;
      }
      const errorMessage: ChatMessage = {
        sender: 'ai',
        text: errorText,
      };
      setMessages(prev => [...prev, errorMessage]);
      await logMessage(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [apiKey, ticketData, chatData, messages, googleAccessToken, logDocumentId]);

  const resetState = () => {
    // If initial data was provided, reset to that state, otherwise full reset.
    if (initialTicketData && initialChatData) {
        setTicketData(initialTicketData);
        setChatData(initialChatData);
        setStep(AppStep.ConfirmSchema);
        // Re-run schema suggestion
        handleDataUpload(new File([], "preloaded"), new File([], "preloaded"), initialTicketData, initialChatData);
    } else {
        setStep(AppStep.SelectDataSource);
        setTicketFile(null);
        setChatFile(null);
        setTicketData(null);
        setChatData(null);
    }
    setSuggestedSchema(null);
    setIsLoading(false);
    setError(null);
    setMessages([]);
    setLogDocumentId(null);
    setGoogleAccessToken(null);
  };

  const renderContent = () => {
    switch (step) {
      case AppStep.SelectDataSource:
        return <DataSourceSelector onSelect={handleDataSourceSelect} isLoading={isLoading} error={error} />;
      case AppStep.UploadData:
        return <DataUpload onUpload={handleDataUpload} isLoading={isLoading} error={error} />;
      case AppStep.ConfirmSchema: {
        let isSchemaValid = false;
        if (suggestedSchema) {
          try {
            JSON.parse(suggestedSchema);
            isSchemaValid = true;
          } catch (e) { isSchemaValid = false; }
        }
        return (
          <div className="text-center p-8 bg-white dark:bg-gray-800 rounded-lg shadow-lg animate-fade-in">
            <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-4">Confirm Data Schema</h2>
            {isSchemaValid ? (
              <>
                <p className="text-gray-600 dark:text-gray-300 mb-6">
                  Based on your data, I've inferred the following structure. This will help me understand your data better.
                </p>
                <div className="text-left bg-gray-50 dark:bg-gray-700 p-4 rounded-md max-h-96 overflow-y-auto border border-gray-200 dark:border-gray-600">
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-200">
                    <code>{suggestedSchema}</code>
                  </pre>
                </div>
              </>
            ) : (
              <>
                <p className="text-red-500 dark:text-red-400 mb-6">
                  I had trouble generating a valid schema from the data provided. Please review the AI's raw response below.
                </p>
                <div className="text-left bg-red-50 dark:bg-red-900/20 p-4 rounded-md max-h-96 overflow-y-auto border border-red-200 dark:border-red-700">
                  <pre className="whitespace-pre-wrap text-sm text-red-700 dark:text-red-300">
                    <code>{suggestedSchema || 'No response was generated from the AI.'}</code>
                  </pre>
                </div>
              </>
            )}
            <div className="mt-8 flex justify-center gap-4">
              <button
                onClick={() => setStep(ticketFile || chatFile ? AppStep.UploadData : AppStep.SelectDataSource)}
                className="px-6 py-2 border border-gray-300 dark:border-gray-500 text-gray-700 dark:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                Go Back
              </button>
              {isSchemaValid && (
                <button
                  onClick={handleConfirmSchema}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
                >
                  Looks Good, Proceed to Chat
                </button>
              )}
            </div>
          </div>
        );
      }
      case AppStep.Chat:
        return <ChatInterface messages={messages} onSendMessage={handleSendMessage} isLoading={isLoading} />;
      default:
        return <p>Something went wrong.</p>;
    }
  };

  return (
    <div className={containerClassName}>
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <LogoIcon className="h-10 w-10 text-indigo-600"/>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
            Customer Support AI Analyst
          </h1>
        </div>
        {step > AppStep.SelectDataSource && (
            <button
              onClick={resetState}
              className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              Start Over
            </button>
        )}
      </header>
      <main className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-2 sm:p-4 border border-gray-200 dark:border-gray-700">
          { step < AppStep.Chat && (
            <div className="p-4 sm:p-6">
                <StepIndicator currentStep={step} />
            </div>
          )}
          <div className={`p-4 sm:p-6 flex flex-col justify-center ${step < AppStep.Chat ? 'min-h-[60vh]' : ''}`}>
            {renderContent()}
          </div>
      </main>
      <footer className="text-center mt-6 text-sm text-gray-500 dark:text-gray-400">
        <p>Powered by Google Gemini</p>
      </footer>
    </div>
  );
};

export default AIAnalystChat;
