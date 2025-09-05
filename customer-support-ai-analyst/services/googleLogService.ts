// These declarations are used to inform TypeScript about the Google APIs loaded from script tags.
declare const gapi: any;

/**
 * Creates a new Google Doc with the given title.
 * @param accessToken The user's OAuth 2.0 access token.
 * @param title The title for the new document.
 * @returns A promise that resolves with the ID of the newly created document.
 */
export async function createLogDoc(accessToken: string, title: string): Promise<string> {
    try {
        await gapi.client.setToken({ access_token: accessToken });
        const response = await gapi.client.docs.documents.create({
            title: title,
        });
        return response.result.documentId;
    } catch (err: any) {
        console.error("Error creating Google Doc:", err);
        throw new Error("Failed to create a new log document in Google Docs.");
    }
}

/**
 * Appends text to a specified Google Doc.
 * @param accessToken The user's OAuth 2.0 access token.
 * @param documentId The ID of the document to append to.
 * @param text The text content to add.
 * @returns A promise that resolves when the operation is complete.
 */
export async function appendToDoc(accessToken: string, documentId: string, text: string): Promise<void> {
    try {
        await gapi.client.setToken({ access_token: accessToken });
        await gapi.client.docs.documents.batchUpdate({
            documentId: documentId,
            requests: [
                {
                    insertText: {
                        text: text,
                        endOfSegmentLocation: {},
                    },
                },
            ],
        });
    } catch (err: any) {
        console.error("Error appending to Google Doc:", err);
        // Don't throw here to avoid interrupting the user flow if logging fails.
    }
}