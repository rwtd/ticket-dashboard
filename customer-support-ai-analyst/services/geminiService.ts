
import { GoogleGenAI, Type, GenerateContentResponse } from "@google/genai";
import { ChatMessage } from '../types';

function formatCSVToText(data: string[][]): string {
  return data.map(row => row.join(',')).join('\n');
}

const fileToGenerativePart = async (file: File) => {
    const base64EncodedDataPromise = new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve((reader.result as string).split(',')[1]);
      reader.readAsDataURL(file);
    });
    return {
      inlineData: {
        data: await base64EncodedDataPromise,
        mimeType: file.type
      },
    };
  }

export async function getGeminiSchemaSuggestion(apiKey: string, ticketData: string[][], chatData: string[][]): Promise<string> {
  if (!apiKey) {
    throw new Error("API_KEY is required.");
  }
  const ai = new GoogleGenAI({ apiKey });

  try {
    const model = 'gemini-2.5-flash';
    
    const ticketSample = formatCSVToText(ticketData.slice(0, 5));
    const chatSample = formatCSVToText(chatData.slice(0, 5));

    const prompt = `
      Analyze the following two CSV data samples for customer support tickets and live chats.
      Based on the headers and data, infer a combined, simplified JSON schema that could represent this data for analysis.
      Focus on key metrics like response times, resolution times, agent performance, and customer satisfaction.
      Do not just list all columns. Synthesize and suggest a structured schema.
      Provide your response as a JSON object within a markdown code block.

      **Ticket Data Sample:**
      \`\`\`csv
      ${ticketSample}
      \`\`\`

      **Chat Data Sample:**
      \`\`\`csv
      ${chatSample}
      \`\`\`
    `;

    const response: GenerateContentResponse = await ai.models.generateContent({
        model: model,
        contents: prompt
    });
    
    const rawText = response.text;
    const jsonMatch = rawText.match(/```json\n([\s\S]*?)\n```/);
    
    if (jsonMatch && jsonMatch[1]) {
      try {
        // Prettify the JSON
        const parsed = JSON.parse(jsonMatch[1]);
        return JSON.stringify(parsed, null, 2);
      } catch (e) {
        console.error("Failed to parse JSON from schema suggestion", e);
        return "Could not generate a valid JSON schema. The AI's response was:\n" + rawText;
      }
    }

    return rawText;
  } catch (error) {
    console.error("Error calling Gemini API for schema suggestion:", error);
    let friendlyMessage = "An unexpected error occurred while analyzing your data schema. Please check the data format and try again.";
    if (error instanceof Error) {
        if (error.message.includes('API key not valid')) {
            friendlyMessage = "The API key is invalid. Please check your application configuration.";
        } else if (error.message.includes('429')) { // Too many requests
            friendlyMessage = "The service is currently busy and could not process your request. Please try again in a few moments.";
        } else if (error.message.includes('500')) { // Server error
            friendlyMessage = "A server error occurred on the AI service's end. Please try again later.";
        }
    }
    throw new Error(friendlyMessage);
  }
}

export async function getGeminiChatResponse(
  apiKey: string,
  userMessage: string,
  ticketData: string[][],
  chatData:string[][],
  chatHistory: ChatMessage[],
  file?: File | null
): Promise<string> {
    if (!apiKey) {
        throw new Error("API_KEY is required.");
    }
    const ai = new GoogleGenAI({ apiKey });

  try {
    const model = 'gemini-2.5-flash';

    const ticketSample = formatCSVToText(ticketData.slice(0, 20)); // Provide a larger sample for analysis
    const chatSample = formatCSVToText(chatData.slice(0, 20));

    const history = chatHistory.map(msg => ({
        role: msg.sender === 'user' ? 'user' : 'model',
        parts: [{ text: msg.text }]
    })).slice(-10); // keep last 10 messages for context

    const systemInstruction = `
      You are a world-class customer support data analyst.
      You have been provided with two data sets: support tickets and live chat logs.
      Your task is to answer questions and provide insights based *only* on the data provided.
      You may also receive images (e.g., charts, screenshots) or text files (e.g., customer feedback) for additional context in user prompts. Use this context to inform your analysis.
      Be concise and data-driven in your responses. If the data doesn't support an answer, say so.
      Do not make up information.
      
      Here is a sample of the data you are working with:
      
      **Ticket Data (first 20 rows):**
      \`\`\`csv
      ${ticketSample}
      \`\`\`

      **Chat Data (first 20 rows):**
      \`\`\`csv
      ${chatSample}
      \`\`\`
    `;
    
    const userParts = [{ text: userMessage }];
    if (file) {
        const filePart = await fileToGenerativePart(file);
        userParts.push(filePart as any);
    }

    const contents = [
      ...history,
      { role: 'user', parts: userParts }
    ];

    const response: GenerateContentResponse = await ai.models.generateContent({
        model: model,
        contents: contents,
        config: {
          systemInstruction: systemInstruction,
        }
    });

    return response.text;
  } catch(error) {
    console.error("Error calling Gemini API for chat response:", error);
    let friendlyMessage = "I'm having trouble responding right now. Please try your request again in a moment.";
    if (error instanceof Error) {
        if (error.message.includes('API key not valid')) {
            friendlyMessage = "There seems to be an issue with the API configuration, so I can't process your request.";
        } else if (error.message.includes('429')) { // Too many requests
            friendlyMessage = "I'm experiencing high traffic at the moment. Please wait a moment before sending another message.";
        } else if (error.message.includes('500')) { // Server error
            friendlyMessage = "Sorry, I've encountered a server issue. Please try again later.";
        }
    }
    throw new Error(friendlyMessage);
  }
}

/**
 * A general-purpose function for the application to use the AI for internal tasks.
 * This is separate from the user-facing chat and does not use chat history or data context.
 * @param apiKey The Gemini API key.
 * @param prompt The internal prompt for the AI.
 * @returns A promise that resolves to the AI's text response.
 */
export async function getInternalGeminiResponse(apiKey: string, prompt: string): Promise<string> {
  if (!apiKey) {
    throw new Error("API_KEY is required.");
  }
  const ai = new GoogleGenAI({ apiKey });

  try {
    const model = 'gemini-2.5-flash';

    const response: GenerateContentResponse = await ai.models.generateContent({
        model: model,
        contents: prompt
    });

    return response.text;
  } catch (error) {
    console.error("Error calling Gemini API for internal task:", error);
    let friendlyMessage = "An internal AI task failed. Please check the console for details.";
    if (error instanceof Error) {
        if (error.message.includes('API key not valid')) {
            friendlyMessage = "The API key is invalid. Please check your application configuration.";
        } else if (error.message.includes('429')) { // Too many requests
            friendlyMessage = "The service is currently busy. Internal task could not be completed.";
        } else if (error.message.includes('500')) { // Server error
            friendlyMessage = "A server error occurred on the AI service's end. Internal task failed.";
        }
    }
    throw new Error(friendlyMessage);
  }
}
