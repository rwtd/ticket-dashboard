# Cloud Run Configuration Guide

## Managing API Credentials in Cloud Run

Your ticket dashboard is deployed to Google Cloud Run with all credentials managed through **Google Secret Manager**. This ensures:
- ✅ Secure credential storage
- ✅ Automatic loading on container startup  
- ✅ No manual `.env` file management needed
- ✅ Configuration persists across deployments

## Current Configuration

**Service URL:** https://ticket-dashboard-179279767621.us-central1.run.app

**Resources:**
- CPU: 2 vCPU
- Memory: 1 GB
- Max Instances: 3
- Concurrency: 80 requests per instance

**Configured Secrets (Auto-loaded as Environment Variables):**
- `GOOGLE_SHEETS_SPREADSHEET_ID` - Your Google Sheets ID
- `HUBSPOT_API_KEY` - HubSpot API token
- `LIVECHAT_PAT` - LiveChat Personal Access Token
- `GEMINI_API_KEY` - Google Gemini AI API key
- `GOOGLE_SHEETS_CREDENTIALS_PATH` - Path to service account file

**Mounted Files:**
- `/app/credentials/service_account_credentials.json` - Google Sheets service account credentials

## How to Update Configuration

### Option 1: Update Secrets via Google Cloud Console

1. Go to [Secret Manager](https://console.cloud.google.com/security/secret-manager?project=ticket-dashboard-473215)
2. Click on the secret you want to update (e.g., `GOOGLE_SHEETS_SPREADSHEET_ID`)
3. Click **"New Version"**
4. Paste the new value
5. Click **"Add new version"**
6. The Cloud Run service will automatically pick up the new value on next container start

### Option 2: Update Secrets via Command Line

```bash
# Update Google Sheets Spreadsheet ID
echo -n "YOUR_NEW_SPREADSHEET_ID" | gcloud secrets versions add GOOGLE_SHEETS_SPREADSHEET_ID \
  --data-file=- \
  --project=ticket-dashboard-473215

# Update HubSpot API Key
echo -n "YOUR_NEW_HUBSPOT_KEY" | gcloud secrets versions add HUBSPOT_API_KEY \
  --data-file=- \
  --project=ticket-dashboard-473215

# Update LiveChat PAT
echo -n "YOUR_NEW_LIVECHAT_PAT" | gcloud secrets versions add LIVECHAT_PAT \
  --data-file=- \
  --project=ticket-dashboard-473215

# Update Gemini API Key  
echo -n "YOUR_NEW_GEMINI_KEY" | gcloud secrets versions add GEMINI_API_KEY \
  --data-file=- \
  --project=ticket-dashboard-473215
```

### Option 3: Update Google Sheets Service Account Credentials

```bash
# Update the service account JSON file
gcloud secrets versions add google-sheets-credentials \
  --data-file=/path/to/new/service_account_credentials.json \
  --project=ticket-dashboard-473215
```

## Force Container Restart (Pick Up New Secrets)

After updating secrets, force a new container deployment to load the new values:

```bash
gcloud run services update ticket-dashboard \
  --region=us-central1 \
  --project=ticket-dashboard-473215
```

Or trigger traffic to the service - Cloud Run will spin up a new container with the latest secret versions.

## Admin Panel Behavior

**Important:** The admin panel's "Configuration" page in Cloud Run will:
- ✅ **Display** current values from Secret Manager (masked for security)
- ❌ **Cannot save** to `.env` file (containers are ephemeral)
- ⚠️ Changes made in the admin panel will **NOT persist** across container restarts

To make persistent configuration changes, you **must** update the secrets in Google Secret Manager using the methods above.

## Redeploy with Updated Configuration

When you need to redeploy the entire service (new code + config):

```bash
# From project root
make PROJECT_ID=ticket-dashboard-473215 REGION=us-central1 all
```

This will:
1. Build new Docker image
2. Push to Artifact Registry  
3. Deploy to Cloud Run with all secrets configured

## Viewing Current Configuration

```bash
# See all environment variables and secrets
gcloud run services describe ticket-dashboard \
  --region=us-central1 \
  --project=ticket-dashboard-473215

# List all secrets
gcloud secrets list --project=ticket-dashboard-473215

# View specific secret value (requires permissions)
gcloud secrets versions access latest --secret="GOOGLE_SHEETS_SPREADSHEET_ID" \
  --project=ticket-dashboard-473215
```

## Troubleshooting

### "Google Sheets configuration won't stick"
- The admin panel cannot save to `.env` in Cloud Run
- Update secrets via Secret Manager instead
- Container will load new values on next startup

### "API credentials not working after update"
1. Verify secret updated in Secret Manager
2. Force container restart: `gcloud run services update ticket-dashboard --region=us-central1 --project=ticket-dashboard-473215`
3. Check logs: `gcloud logging read "resource.labels.service_name=ticket-dashboard" --limit=20 --project=ticket-dashboard-473215`

### Out of Memory Errors
- Current allocation: 1GB RAM, 2 vCPU
- To increase: Update Makefile or use `--memory=2Gi --cpu=4` flags

## Security Notes

- ✅ All credentials stored in Google Secret Manager (encrypted at rest)
- ✅ Only accessible to the service account running Cloud Run
- ✅ Service account has minimal required permissions
- ✅ Secrets mounted as files (not in environment variables where possible)
- ⚠️ Admin panel password: Set via `ADMIN_PASSWORD` secret (default: admin123)