# Admin Panel Configuration Guide

## Quick Start

1. **Access Admin Panel**
   - Start the app: `python start_ui.py`
   - Navigate to: `http://localhost:5000/admin`
   - Login with password (default: `admin123`)
   - **IMPORTANT**: Change default password via `ADMIN_PASSWORD` environment variable!

2. **Configure API Credentials**
   - Click **"Configure"** button or navigate to **Configuration** page
   - Enter your API credentials (see below for where to get them)
   - Click **"Save Configuration"**
   - Credentials are saved to `.env` file and take effect immediately

3. **Test Connections**
   - Return to Admin Dashboard
   - Click **"Test Connections"** to verify all APIs are working
   - Green badges indicate successful connections

4. **Run Initial Sync**
   - Click **"Full Sync (365 days)"** to fetch all historical data
   - This will take 5-10 minutes depending on data volume
   - Monitor progress in sync status section

## Getting API Credentials

### HubSpot API Key

1. Go to HubSpot → **Settings** → **Integrations** → **Private Apps**
2. Click **"Create a private app"**
3. Name it: `Ticket Dashboard Analytics`
4. Go to **Scopes** tab and enable:
   - `crm.objects.tickets.read`
   - `crm.schemas.tickets.read`
   - `crm.objects.owners.read`
5. Click **"Create app"**
6. Copy the **Access Token** (starts with `pat-na1-...`)
7. Paste into **HubSpot API Key** field in admin panel

**Quick Test:**
```bash
export HUBSPOT_API_KEY="your_token_here"
python test_hubspot_connection.py
```

### LiveChat PAT Token

1. Go to LiveChat Developer Console: https://developers.livechat.com/console/tools/personal-access-tokens
2. Click **"Create new token"**
3. Name it: `Ticket Dashboard Analytics`
4. Select scopes:
   - `chats--all:ro`
   - `chats--access:ro`
   - `agents--all:ro`
   - `agents-bot--all:ro`
5. Click **"Create token"**
6. Copy the generated token
7. Paste into **LiveChat PAT** field in admin panel

**Alternative Format:**
If you have separate username/password, use format: `username:password`

### Google Sheets

1. **Create Service Account:**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create or select a project
   - Enable **Google Sheets API**
   - Go to **IAM & Admin** → **Service Accounts**
   - Click **"Create Service Account"**
   - Name it: `ticket-dashboard-sync`
   - Grant role: **Editor**
   - Click **"Create key"** → **JSON**
   - Download the JSON file

2. **Set Up Sheet:**
   - Create a new Google Sheet
   - Copy the Spreadsheet ID from URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit`
   - Share the sheet with your service account email (from JSON file)
   - Grant **Editor** permission

3. **Configure in Admin Panel:**
   - Enter **Spreadsheet ID** in admin panel
   - Place credentials JSON file in project root as `service_account_credentials.json`
   - Or specify custom path in **Google Sheets Credentials Path** field

## Configuration Fields Explained

### API Credentials Section

| Field | Required | Description |
|-------|----------|-------------|
| **HubSpot API Key** | Yes | Private App token for fetching tickets |
| **LiveChat PAT** | Yes | Personal Access Token or username:password |
| **Google Sheets Spreadsheet ID** | Yes | ID from sheet URL |
| **Google Sheets Credentials Path** | Yes | Path to service account JSON (default: `service_account_credentials.json`) |

### Sync Configuration Section

| Field | Default | Description |
|-------|---------|-------------|
| **Sync Interval** | 4 hours | How often to automatically sync data |
| **Data Retention** | 365 days | Rolling window for Google Sheets data |

### AI Configuration Section

| Field | Required | Description |
|-------|----------|-------------|
| **Gemini API Key** | Optional | For AI-powered conversational analysis |

## Using the Admin Panel

### Dashboard Overview

**API Status Card:**
- Shows which APIs are configured
- Green = configured, Red = not configured
- Click **"Test Connections"** to verify

**Sync Status Card:**
- Shows last sync times for tickets, chats, and full sync
- Displays current sync interval and retention settings

**Sync Actions Card:**
- **Incremental Sync**: Fetches only new/modified data (fast, use regularly)
- **Full Sync**: Fetches last 365 days (slow, use once initially)

**Quick Links Card:**
- View Sync Logs
- Edit Configuration
- Return to Main Dashboard
- Access Widgets

### Configuration Page

1. **Entering New Credentials:**
   - Type directly into password fields
   - Click **"Show"** button to verify what you typed
   - Leave blank to keep existing credential
   - Click **"Save Configuration"**

2. **Updating Existing Credentials:**
   - Fields show "(Currently configured)" if already set
   - Enter new value to replace
   - Leave blank to keep current
   - Changes save to `.env` file

3. **Viewing Current Values:**
   - Click **"Show"** button next to password fields
   - Reveals actual stored value
   - Click **"Hide"** to mask again

### Sync Logs

- View history of all sync operations
- Shows timestamps, type, and status
- Useful for troubleshooting

## Troubleshooting

### "Not Configured" Status

**Problem:** API shows as "Not Configured"
**Solution:** 
1. Go to Configuration page
2. Enter the API credential
3. Click "Save Configuration"
4. Return to dashboard and test connection

### Connection Test Fails

**HubSpot:**
- Verify token hasn't expired
- Check scopes are correct
- Try the test script: `python test_hubspot_connection.py`

**LiveChat:**
- Verify token is active in Developer Console
- Check scopes include `chats--all:ro` and `agents--all:ro`
- Try username:password format if PAT fails

**Google Sheets:**
- Verify credentials JSON file exists at specified path
- Check service account has Editor access to sheet
- Verify Sheets API is enabled in Google Cloud Console

### Sync Fails or Takes Too Long

**Incremental Sync:**
- Should complete in < 30 seconds
- Fetches only new data since last sync
- If fails, check API rate limits

**Full Sync:**
- Can take 5-10 minutes for large datasets
- Fetches entire 365-day window
- Monitor sync status in dashboard

### Changes Don't Take Effect

**Immediate Effect:**
- Most credential changes work immediately
- Test connection to verify

**Requires Restart:**
- Some settings require app restart
- Stop app with Ctrl+C
- Restart with `python start_ui.py`

## Security Best Practices

1. **Change Default Password:**
   ```bash
   export ADMIN_PASSWORD="your_secure_password_here"
   ```

2. **Protect .env File:**
   - Add to `.gitignore`
   - Never commit credentials to version control

3. **Use Environment Variables:**
   - For production, set via hosting platform
   - Don't hardcode credentials in files

4. **Rotate Credentials:**
   - Regularly update API tokens
   - Update in admin panel when changed

5. **Service Account Security:**
   - Limit sheet sharing to service account only
   - Use least-privilege principle for GCP roles

## Next Steps

After configuring credentials:

1. ✅ Test all connections in admin panel
2. ✅ Run initial full sync
3. ✅ Verify data appears in Google Sheets
4. ✅ Check main dashboard shows current data
5. ✅ Set up scheduled sync (if deploying to cloud)

For deployment instructions, see:
- [`CLOUD_RUN_DEPLOYMENT_GUIDE.md`](CLOUD_RUN_DEPLOYMENT_GUIDE.md)
- [`DOCKER_README.md`](DOCKER_README.md)