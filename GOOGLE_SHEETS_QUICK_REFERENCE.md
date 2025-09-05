# Google Sheets Integration - Quick Reference

## 🚨 Common Issue: Authentication Scopes

**Error:** "Request had insufficient authentication scopes"
**Solution:** Your credentials need broader scope permissions.

### Fix for Service Account (Recommended):
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "APIs & Services" > "Credentials"
3. Click your service account
4. Go to "Keys" tab > "Add Key" > "Create new key" > JSON
5. Replace your current `credentials.json`

### Fix for OAuth Token:
```bash
# Delete old token to force re-authentication
rm token.json
# Re-run with fresh authentication
python ticket_analytics.py --day 02092025 --export-to-sheets
```

## 🎯 Quick Commands

### Create New Sheet:
```bash
python ticket_analytics.py --day 02092025 --export-to-sheets
```

### Update Existing Sheet:
```bash
python ticket_analytics.py --day 02092025 --export-to-sheets --sheets-id "YOUR_SHEET_ID"
```

### Test Authentication:
```python
from google_sheets_exporter import GoogleSheetsExporter
exporter = GoogleSheetsExporter('credentials.json')
print("✅ Auth success" if exporter.authenticate() else "❌ Auth failed")
```

## 📋 What Gets Exported

### Tickets Sheet:
- All 320+ original columns
- **PLUS calculated fields:**
  - `Day_of_Week_Name`, `Is_Weekend`, `Is_Weekday`
  - `FY_Quarter_Full` (2025-Q3, 2025-Q4, etc.)
  - `Response_Time_Category` (< 1 hour, 1-4 hours, etc.)
  - `Created_During_Business_Hours` (9 AM-5 PM EST, Mon-Fri)
  - 28 QA scoring fields (empty, ready for population)

### Features:
- **Rolling 365-day window** - Only recent data
- **Upsert logic** - Updates existing, adds new
- **Automatic cleanup** - Removes old data

## 🔧 Troubleshooting

### "Permission denied":
- Share sheet with service account email (from credentials.json)
- Or use OAuth instead of service account

### "Sheet not found":
- Verify spreadsheet ID from URL: `docs.google.com/spreadsheets/d/[SHEET_ID]/edit`

### "Mixed data types":
- This is normal - system handles automatically

## 📊 Where Sheets Appear

New sheets created in your Google Drive root folder:
- Title: "Support Analytics Dashboard - YYYY-MM-DD"
- URL format: `https://docs.google.com/spreadsheets/d/[SHEET_ID]`

## 🔐 Credential Requirements

Your `credentials.json` needs these scopes:
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/drive` (optional, for permissions)

## 🚀 Next Steps After Setup

1. Run test export: `python ticket_analytics.py --day 02092025 --export-to-sheets`
2. Check Google Drive for new sheet
3. Use returned sheet ID for future updates
4. Set up automation with `--sheets-id` parameter