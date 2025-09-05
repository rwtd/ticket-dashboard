import { init, getAccessToken } from "./googleAuthService";

// These declarations are used to inform TypeScript about the Google APIs loaded from script tags.
declare const gapi: any;
declare const google: any;

interface SheetData {
    ticketData: string[][];
    chatData: string[][];
    accessToken: string;
}

// Scopes required for reading spreadsheets, files from Google Drive and writing to Google Docs
const SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents'
];

/**
 * Fetches data from a specific Google Sheet using its ID.
 * @param spreadsheetId The ID of the Google Sheet.
 * @returns A promise that resolves to a 2D array of strings representing the sheet data.
 */
async function getSheetData(spreadsheetId: string): Promise<string[][]> {
    try {
        const response = await gapi.client.sheets.spreadsheets.values.get({
            spreadsheetId: spreadsheetId,
            range: 'A1:Z1000', // Fetch a reasonably large range to capture most datasets.
        });
        return response.result.values || [];
    } catch (err: any) {
        console.error('Error fetching sheet data:', err);
        throw new Error(`Failed to fetch data from the spreadsheet. Please check its sharing permissions.`);
    }
}

/**
 * Main exported function that orchestrates the entire Google Sheets connection process.
 * It initializes clients, gets user authorization, shows a file picker, and fetches data.
 */
export async function pickAndLoadSheets(googleApiKey: string, googleClientId: string): Promise<SheetData> {
    await init(googleApiKey, googleClientId);
    
    const accessToken = await getAccessToken(SCOPES);
    gapi.client.setToken({ access_token: accessToken });
    
    return new Promise((resolve, reject) => {
        const picker = new google.picker.PickerBuilder()
            .addView(google.picker.ViewId.SPREADSHEETS)
            .setOAuthToken(accessToken)
            .setDeveloperKey(googleApiKey)
            .setTitle("Select your Ticket and Chat data sheets (select 2)")
            .setMaxItems(2)
            // This is a workaround to prevent the picker from obscuring the app
            .setRelayUrl(window.location.origin)
            .setOrigin(window.location.origin)
            .build();

        picker.setCallback(async (data: any) => {
            if (data.action === google.picker.Action.PICKED) {
                if (data.docs.length < 2) {
                    return reject(new Error("Please select two files: one for tickets and one for chats."));
                }
                try {
                    // The order of selection determines which is ticket vs chat. First is ticket.
                    const ticketFileId = data.docs[0].id;
                    const chatFileId = data.docs[1].id;

                    const [ticketData, chatData] = await Promise.all([
                        getSheetData(ticketFileId),
                        getSheetData(chatFileId),
                    ]);
                    
                    resolve({ ticketData, chatData, accessToken });

                } catch (error) {
                    reject(error);
                }
            } else if (data.action === google.picker.Action.CANCEL) {
                reject(new Error("File selection was cancelled."));
            }
        });
        
        picker.setVisible(true);
    });
}
