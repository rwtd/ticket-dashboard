# Create Service Account for Google Sheets

## Quick Steps:

1. **Go to Google Cloud Console:** https://console.cloud.google.com/
2. **Select your project:** "rw-assist" 
3. **Navigate:** "APIs & Services" > "Credentials"
4. **Create Service Account:**
   - Click "Create Credentials" > "Service Account"
   - Name: "ticket-dashboard-service"
   - Click "Create and Continue"
   - Skip roles (click "Continue")
   - Click "Done"

5. **Generate Key:**
   - Click on the service account email
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key" > "JSON"
   - Save as `credentials.json` (replace existing)

6. **Share your Google Sheet:**
   - Open: https://docs.google.com/spreadsheets/d/1fDek0n36V1oFAofYDzSsfvOeVu6hTjWjq-9zcy_JxEk/edit
   - Click "Share"
   - Add the service account email (from the JSON file: `client_email`)
   - Give "Editor" permissions

## Service account credentials look like:
```json
{
  "type": "service_account",
  "project_id": "rw-assist",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----...",
  "client_email": "ticket-dashboard-service@rw-assist.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

This approach doesn't require interactive authentication.