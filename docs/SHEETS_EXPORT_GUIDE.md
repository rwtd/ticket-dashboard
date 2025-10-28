# Firestore to Google Sheets Export Guide

Automated export of Firestore data to Google Sheets for external stakeholder viewing.

## Overview

This system syncs your Firestore database to Google Sheets daily, providing stakeholders with a live view of your support data without giving them direct database access.

**Architecture:**
```
APIs (HubSpot/LiveChat)
    ↓
Firestore Database (Source of Truth)
    ↓
Google Sheets (Stakeholder View)
    ↓
External Stakeholders
```

## Features

✅ **Full Mirror**: Complete upsert of all Firestore data  
✅ **Separate Sheets**: Tickets and Chats in separate tabs  
✅ **Metadata**: Sync timestamp and record counts  
✅ **Formatted**: Bold headers, frozen rows  
✅ **Automated**: Daily scheduled sync  
✅ **Safe**: Read-only for stakeholders (they can't break your database)

## Setup

### 1. Prerequisites

- ✅ Firestore database populated (you've done this!)
- ✅ Google Sheets API credentials (`service_account_credentials.json`)
- ✅ Target spreadsheet ID: `1KVAQLE2vL3z2CpRH_CIqA26ABhr0Oeuu2b7GUrTTjBY`

### 2. Grant Service Account Access

Your service account needs write access to the spreadsheet:

1. Open your spreadsheet: https://docs.google.com/spreadsheets/d/1KVAQLE2vL3z2CpRH_CIqA26ABhr0Oeuu2b7GUrTTjBY
2. Click **Share** button
3. Add your service account email (found in `service_account_credentials.json` as `client_email`)
4. Give it **Editor** permissions
5. Click **Done**

### 3. Test the Export

Run manually to test:

```bash
python export_firestore_to_sheets.py
```

**Expected output:**
```
============================================================
🔄 Starting Firestore → Google Sheets Export
============================================================
✅ Authenticated with Google Sheets API
✅ Connected to Firestore

📋 Exporting Tickets...
  ✓ Retrieved 1,234 tickets from Firestore
  ✓ Cleared sheet: Tickets
  ✓ Wrote 1,235 rows to Tickets
  ✓ Formatted headers for Tickets

💬 Exporting Chats...
  ✓ Retrieved 567 chats from Firestore
  ✓ Cleared sheet: Chats
  ✓ Wrote 568 rows to Chats
  ✓ Formatted headers for Chats

📊 Adding Metadata...
  ✓ Added metadata sheet

============================================================
✅ Export Complete!
============================================================
📋 Tickets exported: 1,234
💬 Chats exported: 567
📊 Spreadsheet: https://docs.google.com/spreadsheets/d/1KVAQLE2vL3z2CpRH_CIqA26ABhr0Oeuu2b7GUrTTjBY
============================================================
```

## Scheduling

### Option 1: Cron (Linux/Mac)

Daily at 2 AM:

```bash
# Edit crontab
crontab -e

# Add this line
0 2 * * * cd /path/to/ticket-dashboard && /path/to/venv/bin/python export_firestore_to_sheets.py >> logs/sheets_export.log 2>&1
```

### Option 2: Cloud Scheduler (GCP)

```bash
# Create Cloud Scheduler job
gcloud scheduler jobs create http sheets-export \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --uri="YOUR_CLOUD_RUN_URL/api/export-sheets" \
  --http-method=POST \
  --oidc-service-account-email=YOUR_SERVICE_ACCOUNT@PROJECT.iam.gserviceaccount.com
```

### Option 3: GitHub Actions

Create `.github/workflows/export-sheets.yml`:

```yaml
name: Export to Google Sheets

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run export
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_CREDENTIALS }}
          GOOGLE_SHEETS_SPREADSHEET_ID: 1KVAQLE2vL3z2CpRH_CIqA26ABhr0Oeuu2b7GUrTTjBY
        run: |
          python export_firestore_to_sheets.py
```

## What Gets Exported

### Tickets Sheet
All ticket data from Firestore including:
- Ticket ID
- Create date
- Owner
- Status
- Priority
- Subject
- Response times
- All custom fields

### Chats Sheet
All chat data from Firestore including:
- Chat ID
- Creation date
- Agent
- Duration
- Satisfaction rating
- Transfer status
- All custom fields

### Metadata Sheet
- Last updated timestamp
- Record counts
- Data source info
- Update frequency
- Usage notes

## Spreadsheet Structure

```
📊 Your Spreadsheet
├── Metadata (sync info)
├── Tickets (all ticket data)
└── Chats (all chat data)
```

## Sharing with Stakeholders

### Read-Only Access (Recommended)

1. Open spreadsheet
2. Click **Share**
3. Add stakeholder emails
4. Set permission to **Viewer**
5. Uncheck "Notify people"
6. Click **Done**

### Why Read-Only?
- ✅ They can view and filter data
- ✅ They can create their own pivot tables
- ✅ They can download/export
- ❌ They **cannot** edit (protects your data)
- ❌ Changes won't sync back to Firestore

## Monitoring

### Check Last Sync

Open the **Metadata** sheet to see:
- Last updated timestamp
- Record counts
- Any sync issues

### Logs

If using cron, check logs:
```bash
tail -f logs/sheets_export.log
```

### Manual Sync

Run anytime:
```bash
python export_firestore_to_sheets.py
```

## Troubleshooting

### Error: "Authentication failed"

**Problem:** Service account credentials not found or invalid

**Solution:**
```bash
# Check credentials file exists
ls -la service_account_credentials.json

# Verify it's valid JSON
python -c "import json; json.load(open('service_account_credentials.json'))"
```

### Error: "Permission denied"

**Problem:** Service account doesn't have access to spreadsheet

**Solution:**
1. Open spreadsheet
2. Share with service account email (from credentials file)
3. Give Editor permissions

### Error: "Firestore connection failed"

**Problem:** GCP credentials not configured

**Solution:**
```bash
# Set credentials environment variable
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service_account_credentials.json"

# Or add to .env file
echo 'GOOGLE_APPLICATION_CREDENTIALS="service_account_credentials.json"' >> .env
```

### No Data Exported

**Problem:** Firestore database is empty

**Solution:**
```bash
# Run sync first
python firestore_sync_service.py --full

# Then export
python export_firestore_to_sheets.py
```

## Best Practices

### 1. **Schedule During Off-Hours**
Run exports at 2 AM when stakeholders aren't viewing the sheet

### 2. **Monitor Record Counts**
Check Metadata sheet to ensure counts match expectations

### 3. **Keep Credentials Secure**
- Never commit `service_account_credentials.json` to git
- Use environment variables in production
- Rotate credentials periodically

### 4. **Communicate with Stakeholders**
Let them know:
- Data updates daily at 2 AM
- Sheet is read-only (by design)
- They can filter/pivot but not edit
- Changes won't sync back to database

### 5. **Test Before Scheduling**
Always run manual export first to verify everything works

## Advanced Usage

### Custom Spreadsheet ID

```bash
# Use different spreadsheet
export GOOGLE_SHEETS_SPREADSHEET_ID="your-spreadsheet-id"
python export_firestore_to_sheets.py
```

### Custom Credentials Path

```bash
# Use different credentials
export GOOGLE_SHEETS_CREDENTIALS_PATH="path/to/other-credentials.json"
python export_firestore_to_sheets.py
```

### Export Specific Date Range

Modify `export_firestore_to_sheets.py`:

```python
# In export_tickets() method
tickets_df = self.db.get_tickets(
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 31)
)
```

## API Endpoint (Optional)

Add to `app.py` for on-demand exports via dashboard:

```python
@app.route('/api/export-sheets', methods=['POST'])
def export_to_sheets():
    """Trigger Firestore to Sheets export"""
    try:
        from export_firestore_to_sheets import FirestoreToSheetsExporter
        
        spreadsheet_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
        exporter = FirestoreToSheetsExporter(spreadsheet_id)
        result = exporter.run_export()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

Then trigger via:
```bash
curl -X POST http://localhost:5000/api/export-sheets
```

## FAQ

**Q: How long does export take?**  
A: ~30 seconds for 10,000 records. Scales linearly.

**Q: Will this overwrite stakeholder filters/views?**  
A: No. Filters and views are preserved. Only data is updated.

**Q: Can stakeholders edit the data?**  
A: Only if you give them Editor permissions. Use Viewer for read-only.

**Q: What if Firestore is down?**  
A: Export will fail gracefully with error message. Previous data remains in Sheets.

**Q: Can I export to multiple spreadsheets?**  
A: Yes! Run the script multiple times with different `GOOGLE_SHEETS_SPREADSHEET_ID` values.

**Q: Does this cost money?**  
A: No. Google Sheets API is free for reasonable usage (100 requests/100 seconds).

## Support

If you encounter issues:

1. Check logs: `tail -f logs/sheets_export.log`
2. Run manual export: `python export_firestore_to_sheets.py`
3. Verify credentials: `ls -la service_account_credentials.json`
4. Check spreadsheet permissions
5. Ensure Firestore has data: `python -c "from firestore_db import get_database; print(get_database().get_tickets().shape)"`

## Summary

✅ **What it does:** Mirrors Firestore → Google Sheets daily  
✅ **Why:** Gives stakeholders read-only data access  
✅ **How:** Automated script with upsert logic  
✅ **When:** Daily at 2 AM (configurable)  
✅ **Cost:** $0 (free tier)  

**Your stakeholders get live data without touching your database!** 🎉