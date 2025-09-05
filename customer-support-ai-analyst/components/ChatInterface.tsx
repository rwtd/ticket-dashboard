import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage } from '../types';
import { SendIcon, UserIcon, AiIcon, PaperclipIcon, CsvIcon } from './icons';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  onSendMessage: (message: string, file?: File | null) => void;
  isLoading: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onSendMessage, isLoading }) => {
  const [input, setInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setFile(event.target.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((input.trim() || file) && !isLoading) {
      onSendMessage(input.trim(), file);
      setInput('');
      setFile(null);
      if(fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="flex flex-col h-[70vh] w-full max-w-3xl mx-auto bg-white dark:bg-gray-800 rounded-lg shadow-inner animate-fade-in">
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="space-y-6">
          {messages.map((msg, index) => (
            <div key={index} className={`flex items-start gap-4 ${msg.sender === 'user' ? 'justify-end' : ''}`}>
              {msg.sender === 'ai' && <AiIcon className="h-8 w-8 text-indigo-500" />}
              <div className={`flex flex-col gap-2`}>
                <div className={`max-w-md p-4 rounded-xl ${msg.sender === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-none'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-none'
                  }`}>
                  <p className="text-sm leading-relaxed">{msg.text}</p>
                </div>
                {msg.file && msg.sender === 'user' && (
                  <div className="flex justify-end">
                    <div className="max-w-md p-2 rounded-lg bg-indigo-500 text-white text-xs flex items-center gap-2">
                      <PaperclipIcon className="h-4 w-4" />
                      <span>{msg.file.name}</span>
                    </div>
                  </div>
                )}
              </div>
              {msg.sender === 'user' && <UserIcon className="h-8 w-8 text-gray-500" />}
            </div>
          ))}
          {isLoading && messages[messages.length - 1]?.sender === 'user' && (
             <div className="flex items-start gap-4">
                <AiIcon className="h-8 w-8 text-indigo-500" />
                <div className="max-w-md p-4 rounded-xl bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-none">
                    <div className="flex items-center justify-center space-x-2">
                        <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse"></div>
                        <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2 h-2 rounded-full bg-gray-500 animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                    </div>
                </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          {file && (
              <div className="flex items-center justify-between text-sm bg-gray-100 dark:bg-gray-700 p-2 rounded-md">
                  <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300">
                    <PaperclipIcon className="h-5 w-5" />
                    <span className="font-medium">{file.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setFile(null); if(fileInputRef.current) fileInputRef.current.value = ''; }}
                    className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                    aria-label="Remove file"
                  >
                    &times;
                  </button>
              </div>
          )}
          <div className="flex items-center gap-4">
            <input
                id="file-upload"
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                className="sr-only"
                accept=".csv, .txt, .md, image/png, image/jpeg, image/webp"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-3 text-gray-500 dark:text-gray-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Attach file"
              disabled={isLoading}
            >
              <PaperclipIcon className="h-6 w-6" />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your data, or attach a file..."
              className="flex-1 p-3 bg-gray-100 dark:bg-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || (!input.trim() && !file)}
              className="p-3 bg-indigo-600 text-white rounded-lg disabled:bg-indigo-400 disabled:cursor-not-allowed hover:bg-indigo-700 transition-colors"
            >
              <SendIcon className="h-6 w-6" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;