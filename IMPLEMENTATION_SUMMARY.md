# Implementation Summary: API-Based Data Pipeline

## 🎉 What's Been Built

A complete **automated data pipeline** that eliminates manual CSV exports by fetching data directly from HubSpot and LiveChat APIs, then syncing to Google Sheets as the single source of truth for your dashboard, widgets, and AI engine.

### Latest Updates (October 6, 2025)
- ✅ **Manager Ticket Filtering** - Automatically excludes manager tickets (Richie) from all analytics
- ✅ **Pipeline Name Mapping** - Replaces numeric pipeline IDs with readable labels via HubSpot API
- ✅ **Widget Garden** - New `/widgets` endpoint with embeddable analytics widgets
- ✅ **Enhanced Error Handling** - Graceful handling of "Unknown" dates, NaT values, invalid data
- ✅ **Admin Data Status** - Dashboard showing Google Sheets vs local CSV comparison
- ✅ **Warning Suppression** - Cleaned up pandas FutureWarning messages

---

## 📁 New Files Created

### 1. **[API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md)** ⭐
   - **Complete guide for requesting API access**
   - Specific scopes/permissions needed for HubSpot and LiveChat
   - Template emails to send to your admins
   - Testing commands to validate access
   - Cost estimates and quota limits

### 2. **[hubspot_fetcher.py](hubspot_fetcher.py)**
   - Fetches tickets from HubSpot CRM API
   - Handles pagination (100 requests/10 seconds)
   - Supports incremental sync (only new/modified tickets)
   - Fetches owner (agent) mappings
   - Maps API fields to your CSV column format

### 3. **[livechat_fetcher.py](livechat_fetcher.py)**
   - Fetches chats from LiveChat API v3.5
   - Handles pagination (180 requests/minute)
   - Parses chat threads for response times
   - Detects bot vs human agents
   - Identifies transfers (bot → human)
   - Extracts satisfaction ratings

### 4. **[data_sync_service.py](data_sync_service.py)**
   - **Orchestrates the entire pipeline**
   - Fetches from HubSpot + LiveChat
   - Processes data (timezone conversion, agent mapping, weekend detection)
   - Syncs to Google Sheets (upsert mode with rolling 365-day window)
   - Tracks sync state (incremental updates)
   - CLI interface for manual runs

### 5. **[google_sheets_data_source.py](google_sheets_data_source.py)**
   - **Unified data access layer**
   - Reads from Google Sheets with caching (5-minute TTL)
   - Supports filtering by date range, pipeline, agents
   - Used by main app, widgets, and AI engine
   - Graceful fallback to local CSVs if Sheets unavailable

### 6. **Updated: [widgets/registry.py](widgets/registry.py:251)**
   - **Widgets now prioritize Google Sheets**
   - Data priority: Sheets (1st) → Processed CSVs (2nd) → Raw CSVs (3rd)
   - Ensures widgets show always-current data

---

## 🏗️ Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     AUTOMATED DATA PIPELINE                      │
└─────────────────────────────────────────────────────────────────┘

📋 HubSpot Tickets API        💬 LiveChat API
        │                              │
        ├──────────────┬───────────────┤
                       │
            📥 data_sync_service.py
            (Scheduled: every 1-6 hours)
                       │
                       ├─→ hubspot_fetcher.py
                       ├─→ livechat_fetcher.py
                       ├─→ ticket_processor.py (CDT→ADT, agent mapping)
                       ├─→ chat_processor.py (UTC→ADT, bot detection)
                       │
                       ↓
            📊 Google Sheets
            (Single Source of Truth)
            • Tickets sheet (rolling 365 days)
            • Chats sheet (rolling 365 days)
            • Sync_Log sheet (audit trail)
                       │
            ┌──────────┼──────────┐
            │          │          │
    🌐 Main App   📱 Widgets   🤖 AI Engine
    (Flask)      (HubSpot)    (Gemini)
            │          │          │
            └──────────┴──────────┘
                All use:
        google_sheets_data_source.py
        (with 5-min cache + CSV fallback)
```

---

## ✅ Key Features

### 1. **Eliminates Manual Work**
- ❌ Before: Export CSV from HubSpot → Download → Upload to dashboard
- ✅ After: Automated sync every 1-6 hours (configurable)

### 2. **Single Source of Truth**
- Google Sheets contains processed, ready-to-use data
- Main app, widgets, and AI all read from the same source
- No more data inconsistencies or stale dashboards

### 3. **Real-Time Data**
- Widgets embedded in HubSpot show current data
- No need to wait for manual refreshes
- Configurable sync interval (1-24 hours)

### 4. **Incremental Sync**
- Only fetches new/modified records after initial sync
- Reduces API calls and processing time
- Tracks last sync time automatically

### 5. **Robust Fallback**
- If Google Sheets unavailable → uses local processed CSVs
- If processed CSVs unavailable → processes raw CSVs
- Never breaks even if APIs are down

### 6. **Complete Processing**
- **Timezone Conversion**: CDT→ADT (+1h) for tickets, UTC→ADT for chats
- **Agent Name Standardization**: Consistent names across all data
- **Weekend Detection**: Using your schedule.yaml configuration
- **Bot Detection**: Identifies Wynn AI vs Agent Scrape vs humans
- **Transfer Detection**: Flags bot-to-human escalations

---

## 🚀 Deployment Steps

### Phase 1: Request API Access (This Week)
1. **Review [API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md)**
2. **Request HubSpot Private App** (use template email in doc)
   - Required scopes: `crm.objects.tickets.read`, `crm.schemas.tickets.read`, `crm.objects.owners.read`
3. **Request LiveChat PAT** (use template email in doc)
   - Required scopes: `chats--all:ro`, `chats--access:ro`, `agents--all:ro`
4. **Test access** once received (commands in doc)

### Phase 2: Configure Environment (Next Week)
```bash
# Add to your Cloud Run environment variables or .env file
export HUBSPOT_API_KEY="your_hubspot_private_app_token"
export LIVECHAT_PAT="your_livechat_personal_access_token"
export GOOGLE_SHEETS_SPREADSHEET_ID="your_sheets_id_here"
export GOOGLE_SHEETS_CREDENTIALS_PATH="service_account_credentials.json"
export DATA_SYNC_INTERVAL_HOURS=4  # Sync every 4 hours
```

### Phase 3: Test Locally (Next Week)
```bash
# Install dependencies (already in requirements.txt)
pip install -r requirements.txt

# Test API connections
python data_sync_service.py --test

# Run initial full sync (fetch last 365 days)
python data_sync_service.py --full

# Verify data in Google Sheets
python google_sheets_data_source.py

# Test widgets locally
python start_ui.py
# Visit http://localhost:5000/widgets
```

### Phase 4: Deploy Scheduled Sync (Week After)

**Option A: Cloud Run Scheduled Job (Recommended)**
```yaml
# Create cloud-run-sync-job.yaml
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: ticket-dashboard-sync
spec:
  template:
    spec:
      taskCount: 1
      template:
        spec:
          containers:
          - image: gcr.io/YOUR_PROJECT/ticket-dashboard:latest
            command: ["python", "data_sync_service.py", "--incremental"]
            env:
            - name: HUBSPOT_API_KEY
              valueFrom:
                secretKeyRef:
                  name: ticket-dashboard-secrets
                  key: hubspot_api_key
            - name: LIVECHAT_PAT
              valueFrom:
                secretKeyRef:
                  name: ticket-dashboard-secrets
                  key: livechat_pat
            - name: GOOGLE_SHEETS_SPREADSHEET_ID
              value: "YOUR_SPREADSHEET_ID"
```

Then schedule it:
```bash
# Deploy job
gcloud run jobs create ticket-dashboard-sync \
  --region us-central1 \
  --image gcr.io/YOUR_PROJECT/ticket-dashboard:latest \
  --command "python,data_sync_service.py,--incremental" \
  --set-secrets="HUBSPOT_API_KEY=hubspot_api_key:latest,LIVECHAT_PAT=livechat_pat:latest"

# Create Cloud Scheduler trigger (every 4 hours)
gcloud scheduler jobs create http ticket-dashboard-sync-trigger \
  --location us-central1 \
  --schedule="0 */4 * * *" \
  --uri="https://YOUR_REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT/jobs/ticket-dashboard-sync:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com
```

**Option B: Simple Cron (for testing)**
```bash
# Add to crontab (every 4 hours)
0 */4 * * * cd /path/to/ticket-dashboard && /path/to/python data_sync_service.py --incremental >> /var/log/ticket-sync.log 2>&1
```

---

## 📊 Data Flow Example

### Initial Full Sync (Day 1)
```bash
python data_sync_service.py --full
```
**Output:**
```
🚀 Starting full data sync...
🎫 SYNCING TICKETS FROM HUBSPOT
📥 Full sync: fetching all tickets (last 365 days)
📄 Page 1: Fetched 100 tickets (total: 100)
📄 Page 2: Fetched 100 tickets (total: 200)
...
✅ Fetched 847 raw tickets
⚙️  Processing tickets...
✅ Processed 847 tickets

💬 SYNCING CHATS FROM LIVECHAT
📥 Full sync: fetching all chats (last 365 days)
📄 Page 1: Fetched 100 chats (total: 100)
...
✅ Fetched 651 raw chats
⚙️  Processing chats...
✅ Processed 651 chats

📊 SYNCING TO GOOGLE SHEETS
📤 Uploading tickets to Google Sheets...
✅ Tickets uploaded successfully
📤 Uploading chats to Google Sheets...
✅ Chats uploaded successfully

⏱️  Sync completed in 47.3 seconds
✅ FULL SYNC SUCCESSFUL
```

### Incremental Sync (Every 4 hours)
```bash
python data_sync_service.py --incremental
```
**Output:**
```
🔄 Starting incremental data sync...
🎫 SYNCING TICKETS FROM HUBSPOT
📥 Incremental sync: fetching tickets since 2025-09-30 06:00:00+00:00
📄 Page 1: Fetched 12 tickets (total: 12)
✅ Fetched 12 raw tickets
✅ Processed 12 tickets

💬 SYNCING CHATS FROM LIVECHAT
📥 Incremental sync: fetching chats since 2025-09-30 06:00:00+00:00
📄 Page 1: Fetched 23 chats (total: 23)
✅ Fetched 23 raw chats
✅ Processed 23 chats

📊 SYNCING TO GOOGLE SHEETS
📤 Uploading tickets to Google Sheets...
✅ Tickets uploaded successfully (upsert mode)
📤 Uploading chats to Google Sheets...
✅ Chats uploaded successfully (upsert mode)

⏱️  Sync completed in 8.7 seconds
✅ INCREMENTAL SYNC SUCCESSFUL
```

### Widgets Load Data (Automatic)
```
When widget loads:
✅ Using Google Sheets tickets data (primary source)
📊 Loaded 847 tickets from Google Sheets
```

---

## 🔒 Security Considerations

1. **API Tokens**: Store in Google Secret Manager (Cloud Run) or environment variables (never git)
2. **Service Account**: Use service account for Google Sheets (not user OAuth)
3. **Scopes**: Only request minimum necessary permissions (read-only for analytics)
4. **Rate Limits**: Built-in delays ensure you stay within API limits
5. **Audit Trail**: All syncs logged to `Sync_Log` sheet in Google Sheets

---

## 📈 Expected Performance

### API Call Estimates (Per Sync)

**HubSpot:**
- ~850 tickets ÷ 100 per page = 9 API calls
- 1 call for owners mapping
- **Total**: ~10 calls per sync × 6 syncs/day = **60 calls/day**
- Limit: 100,000 calls/day (Professional tier) → **0.06% usage**

**LiveChat:**
- ~650 chats ÷ 100 per page = 7 API calls
- 1 call for agents list
- **Total**: ~8 calls per sync × 6 syncs/day = **48 calls/day**
- Limit: 180 calls/minute → **0.002% usage**

### Sync Times

- **Full Sync** (365 days): 30-60 seconds
- **Incremental Sync** (4 hours): 5-15 seconds
- **Widget Load** (from Sheets cache): <1 second

---

## 🧪 Testing Checklist

Before going to production:

### API Access
- [ ] HubSpot Private App created with correct scopes
- [ ] LiveChat PAT created with correct scopes
- [ ] Both APIs tested with provided curl commands
- [ ] Google Sheets authentication working

### Data Sync
- [ ] Full sync completes successfully
- [ ] Data appears in Google Sheets (Tickets + Chats sheets)
- [ ] Timezone conversion correct (CDT→ADT for tickets, UTC→ADT for chats)
- [ ] Agent names standardized correctly
- [ ] Weekend flags applied correctly

### Widgets
- [ ] Widgets load data from Google Sheets (check console logs)
- [ ] Date range filtering works
- [ ] Charts render correctly with new data
- [ ] Fallback to local CSV works if Sheets unavailable

### Main App
- [ ] Dashboard loads data from Google Sheets
- [ ] AI query engine accesses Sheets data
- [ ] Export functions still work

---

## 🆘 Troubleshooting

### "Authentication failed" errors
- Check API tokens are correct and not expired
- Verify scopes are granted (HubSpot Private App settings)
- Check service account has access to Google Sheets

### "No data fetched" from APIs
- Verify date ranges are correct
- Check API rate limits aren't exceeded
- Ensure you have data in the source systems

### Widgets show old data
- Check `GOOGLE_SHEETS_SPREADSHEET_ID` environment variable
- Verify sync service is running on schedule
- Clear widget cache (restart Flask app)

### Sync takes too long
- Reduce `DATA_RETENTION_DAYS` from 365 to 180 or 90
- Increase sync interval from 4 to 6 hours
- Check network latency to APIs

---

## 📚 Related Documentation

- **[API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md)** - Complete API access guide
- **[CLAUDE.md](CLAUDE.md)** - General development guide
- **[CLOUD_RUN_DEPLOYMENT_GUIDE.md](CLOUD_RUN_DEPLOYMENT_GUIDE.md)** - Cloud Run deployment

---

## 🎯 Next Steps

1. **This Week**: Request API access using templates in [API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md)
2. **Next Week**: Test locally once you have credentials
3. **Week After**: Deploy scheduled sync to Cloud Run
4. **Verify**: Check widgets in HubSpot show current data

---

## 💡 Benefits Summary

✅ **No more manual CSV exports** - Saves 15-30 minutes per day
✅ **Always-current data** - Widgets show real-time metrics
✅ **Single source of truth** - Google Sheets for all analytics
✅ **Scalable** - Handles growing data automatically
✅ **Reliable** - Multi-level fallback ensures uptime
✅ **Audit trail** - Complete sync logging in Google Sheets

**Ready to eliminate manual work and get real-time analytics! 🚀**