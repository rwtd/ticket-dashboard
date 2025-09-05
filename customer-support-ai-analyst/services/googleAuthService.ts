// These declarations are used to inform TypeScript about the Google APIs loaded from script tags.
declare const gapi: any;
declare const google: any;

let gapiInited = false;
let gsiInited = false;
let tokenClient: any;

/**
 * Initializes the Google API client (gapi) and Google Identity Services (GSI) client.
 * This function ensures that the necessary Google libraries are loaded and ready for use.
 * It's safe to call this function multiple times; it will only initialize the clients once.
 * @param apiKey The Google Cloud Platform API Key.
 * @param clientId The Google OAuth 2.0 Client ID.
 */
export function init(apiKey: string, clientId: string): Promise<void> {
    return new Promise((resolve, reject) => {
        if (!apiKey || !clientId) {
            return reject(new Error("Google API Key and Client ID must be provided."));
        }

        const checkAndResolve = () => {
            if (gapiInited && gsiInited) {
                resolve();
            }
        };

        if (gapiInited && gsiInited) {
            return resolve();
        }

        // Initialize gapi
        if (!gapiInited) {
            if (typeof gapi === 'undefined') return reject(new Error("gapi is not loaded. Ensure Google API script is in index.html."));
            gapi.load('client:picker', {
                callback: () => {
                    gapi.client.init({ 
                        apiKey: apiKey,
                        // discoveryDocs are essential for gapi.client.docs to work
                        discoveryDocs: ["https://docs.googleapis.com/$discovery/rest?version=v1", "https://sheets.googleapis.com/$discovery/rest?version=v4"],
                    })
                    .then(() => {
                        gapiInited = true;
                        checkAndResolve();
                    })
                    .catch((err: any) => reject(new Error("Failed to initialize gapi client: " + err.message)));
                },
                onerror: (err: any) => reject(new Error("Failed to load gapi modules: " + err.message))
            });
        }

        // Initialize GSI
        if (!gsiInited) {
             if (typeof google === 'undefined') return reject(new Error("Google Identity Service is not loaded. Ensure GSI script is in index.html."));
            
             tokenClient = google.accounts.oauth2.initTokenClient({
                client_id: clientId,
                scope: '', // Scopes will be provided dynamically
                callback: () => {}, // Callback is handled by the promise wrapper
             });
             gsiInited = true;
             checkAndResolve();
        }
    });
}


/**
 * Requests an OAuth 2.0 access token from the user for the specified scopes.
 * This triggers the Google sign-in and consent pop-up if needed.
 * @param scopes An array of scope strings to request permission for.
 * @returns A promise that resolves with the access token string.
 */
export function getAccessToken(scopes: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
        if (!gsiInited) {
            return reject(new Error("GSI client not initialized."));
        }
        
        tokenClient.callback = (resp: any) => {
            if (resp.error) {
                return reject(new Error("Error getting access token: " + resp.error));
            }
            resolve(resp.access_token);
        };
        
        tokenClient.requestAccessToken({ scope: scopes.join(' '), prompt: 'consent' });
    });
}
