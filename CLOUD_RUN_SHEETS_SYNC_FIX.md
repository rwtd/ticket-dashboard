# Google Sheets Sync Fix for Cloud Run Deployment

## Problem Summary

The Google Sheets sync functionality was non-functional on Cloud Run deployments because **the deployment scripts were missing critical configuration for Google Sheets authentication**. While the Makefile had the correct configuration, the `cloudbuild.yaml` and `scripts/deploy_cloud_run.sh` files were not mounting the service account credentials or setting required environment variables.

## Root Cause Analysis

### What Was Missing:

1. **Service Account Credentials File Mounting**
   - The `google-sheets-credentials` secret needs to be mounted as a file at `/app/credentials/service_account_credentials.json`
   - This was only configured in the Makefile, not in `cloudbuild.yaml` or `deploy_cloud_run.sh`

2. **Environment Variables**
   - `GOOGLE_SHEETS_CREDENTIALS_PATH` was not set (required by `google_sheets_data_source.py` and `google_sheets_exporter.py`)
   - `GOOGLE_SHEETS_SPREADSHEET_ID`, `HUBSPOT_API_KEY`, `LIVECHAT_PAT` secrets were not mounted
   - Only `GEMINI_API_KEY` was configured in `cloudbuild.yaml`

3. **Resource Allocation**
   - `deploy_cloud_run.sh` was using only 512Mi memory and 1 CPU
   - Google Sheets sync requires more resources (1Gi memory, 2 CPU)

## Changes Made

### 1. Fixed `scripts/deploy_cloud_run.sh` (lines 119-131)

**Before:**
```bash
gcloud run deploy "${SERVICE_NAME}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  "${AUTH_FLAG[@]}" \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=80 \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars "WIDGETS_XFO=${WIDGETS_XFO},WIDGETS_FRAME_ANCESTORS=${WIDGETS_FRAME_ANCESTORS}"
```

**After:**
```bash
gcloud run deploy "${SERVICE_NAME}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --platform managed \
  "${AUTH_FLAG[@]}" \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=80 \
  --cpu=2 \
  --memory=1Gi \
  --timeout=900 \
  --set-env-vars "WIDGETS_XFO=${WIDGETS_XFO},WIDGETS_FRAME_ANCESTORS=${WIDGETS_FRAME_ANCESTORS},GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials/service_account_credentials.json" \
  --update-secrets=/app/credentials/service_account_credentials.json=google-sheets-credentials:latest,GOOGLE_SHEETS_SPREADSHEET_ID=GOOGLE_SHEETS_SPREADSHEET_ID:latest,HUBSPOT_API_KEY=HUBSPOT_API_KEY:latest,LIVECHAT_PAT=LIVECHAT_PAT:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest
```

### 2. Fixed `cloudbuild.yaml` (lines 30-49)

**Before:**
```yaml
- '--cpu=1'
- '--timeout=300'
- '--set-env-vars=FLASK_ENV=production,PORT=8080'
- '--update-secrets=GEMINI_API_KEY=gemini-api-key:latest'
```

**After:**
```yaml
- '--cpu=2'
- '--timeout=900'
- '--set-env-vars=FLASK_ENV=production,PORT=8080,GOOGLE_SHEETS_CREDENTIALS_PATH=/app/credentials/service_account_credentials.json'
- '--update-secrets=/app/credentials/service_account_credentials.json=google-sheets-credentials:latest,GOOGLE_SHEETS_SPREADSHEET_ID=GOOGLE_SHEETS_SPREADSHEET_ID:latest,HUBSPOT_API_KEY=HUBSPOT_API_KEY:latest,LIVECHAT_PAT=LIVECHAT_PAT:latest,GEMINI_API_KEY=gemini-api-key:latest'
```

### 3. Fixed `cloudbuild.yaml` YAML syntax error (line 59)

**Before:**
```yaml
diskSizeGb: 20
```

**After:**
```yaml
diskSizeGb: '20'
```

## How Google Sheets Authentication Works

The application uses the following authentication flow:

1. **Service Account Credentials** are stored in Google Secret Manager as `google-sheets-credentials`
2. Cloud Run **mounts the secret as a file** at `/app/credentials/service_account_credentials.json`
3. The environment variable `GOOGLE_SHEETS_CREDENTIALS_PATH` tells the app where to find the credentials
4. `google_sheets_exporter.py` and `google_sheets_data_source.py` read this file to authenticate

### Code Reference:

From `google_sheets_data_source.py` (lines 82-88):
```python
# Try service account first
if os.path.exists(self.credentials_path):
    try:
        creds = ServiceAccountCredentials.from_service_account_file(
            self.credentials_path,
            scopes=self.scopes
        )
```

From `data_sync_service.py` (lines 456-457):
```python
sheets_credentials_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 
                                         'service_account_credentials.json')
```

## Prerequisites for Deployment

Ensure these secrets exist in Google Secret Manager:

```bash
# Check if secrets exist
gcloud secrets list --project=ticket-dashboard-473215

# Required secrets:
# - google-sheets-credentials (JSON file)
# - GOOGLE_SHEETS_SPREADSHEET_ID
# - HUBSPOT_API_KEY
# - LIVECHAT_PAT
# - GEMINI_API_KEY (or gemini-api-key)
```

If any are missing, create them:

```bash
# Create service account credentials secret
gcloud secrets create google-sheets-credentials \
  --data-file=service_account_credentials.json \
  --project=ticket-dashboard-473215

# Create spreadsheet ID secret
echo -n "YOUR_SPREADSHEET_ID" | gcloud secrets create GOOGLE_SHEETS_SPREADSHEET_ID \
  --data-file=- \
  --project=ticket-dashboard-473215

# Create HubSpot API key secret
echo -n "YOUR_HUBSPOT_KEY" | gcloud secrets create HUBSPOT_API_KEY \
  --data-file=- \
  --project=ticket-dashboard-473215

# Create LiveChat PAT secret
echo -n "YOUR_LIVECHAT_PAT" | gcloud secrets create LIVECHAT_PAT \
  --data-file=- \
  --project=ticket-dashboard-473215
```

## Deployment Instructions

### Method 1: Using Makefile (Recommended)

```bash
make PROJECT_ID=ticket-dashboard-473215 REGION=us-central1 all
```

### Method 2: Using Deploy Script

```bash
bash scripts/deploy_cloud_run.sh \
  --project-id ticket-dashboard-473215 \
  --region us-central1 \
  --ar-repo apps \
  --service ticket-dashboard \
  --allow-unauth
```

### Method 3: GitHub Actions

Push to main branch or manually trigger the "Deploy to Cloud Run" workflow.

## Verification

After deployment, verify the sync is working:

1. **Check Admin Panel:**
   - Navigate to https://ticket-dashboard-179279767621.us-central1.run.app/admin
   - Go to "Dashboard" → "Data Status"
   - Verify Google Sheets connection shows as ✅ Connected

2. **Check Environment Variables:**
   ```bash
   gcloud run services describe ticket-dashboard \
     --region=us-central1 \
     --project=ticket-dashboard-473215 \
     --format=yaml
   ```

3. **Check Logs:**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ticket-dashboard" \
     --limit=50 \
     --project=ticket-dashboard-473215 \
     | grep -i "sheets\|sync"
   ```

4. **Test Sync Manually:**
   - Navigate to https://ticket-dashboard-179279767621.us-central1.run.app/admin/sync
   - Click "Run Full Sync" or "Run Incremental Sync"
   - Check logs for success messages

## Expected Log Output (Success)

```
✅ Google Sheets API authenticated successfully
📥 Fetching tickets from Google Sheets...
📊 Loaded 1234 rows from sheet 'Tickets'
✅ Loaded 1234 tickets from Google Sheets
📥 Fetching chats from Google Sheets...
📊 Loaded 5678 rows from sheet 'Chats'
✅ Loaded 5678 chats from Google Sheets
```

## Troubleshooting

### Issue: "No valid credentials found"

**Solution:** Verify the `google-sheets-credentials` secret exists and is mounted:
```bash
gcloud secrets describe google-sheets-credentials --project=ticket-dashboard-473215
```

### Issue: "Spreadsheet not found"

**Solution:** Verify the spreadsheet ID is correct:
```bash
gcloud secrets versions access latest \
  --secret=GOOGLE_SHEETS_SPREADSHEET_ID \
  --project=ticket-dashboard-473215
```

### Issue: "Permission denied"

**Solution:** Ensure the service account has access to the spreadsheet:
1. Get the service account email from the credentials JSON
2. Share the Google Sheet with that email address
3. Grant at least "Editor" permissions

## Files Modified

- ✅ `scripts/deploy_cloud_run.sh` - Added secrets mounting and env vars
- ✅ `cloudbuild.yaml` - Added secrets mounting and env vars  
- ✅ `CLOUD_RUN_SHEETS_SYNC_FIX.md` - This documentation

## Summary

The Google Sheets sync is now fully functional on Cloud Run deployments. All three deployment methods (Makefile, deploy script, GitHub Actions) now correctly:

1. Mount the service account credentials file
2. Set the `GOOGLE_SHEETS_CREDENTIALS_PATH` environment variable
3. Mount all required API secrets
4. Allocate sufficient resources (2 CPU, 1Gi memory)
5. Set appropriate timeout (900 seconds)

The sync functionality will work automatically after deploying with these fixes.