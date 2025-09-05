# 🤖 Auto-Sync Monitor for Google Sheets

**Automated file monitoring and Google Sheets synchronization**

## 🎯 What It Does

- **👁️ Monitors** `./tickets` and `./chats` directories for new CSV files
- **🔄 Auto-detects** new or changed files using file hashes
- **📊 Automatically runs** analytics and syncs to Google Sheets
- **🚀 Real-time** file monitoring (or polling fallback)
- **📝 Logging** with auto_sync.log file

## 🚀 Quick Start

**Start monitoring:**
```bash
./start_auto_sync.sh
```

**Or with custom options:**
```bash
python auto_sync_monitor.py --spreadsheet-id "1fDek0n36V1oFAofYDzSsfvOeVu6hTjWjq-9zcy_JxEk"
```

## 🔧 How It Works

### 1. File Detection
- **Real-time monitoring** using `watchdog` library
- **File stability check** - waits 30s after file stops changing
- **Hash-based change detection** - only processes actual changes
- **State persistence** - remembers processed files across restarts

### 2. Processing Logic
- **Extract date** from filename (e.g., `ticket-export-03092025.csv`)
- **Run analytics** with appropriate date range
- **Auto-sync to Google Sheets** using existing sheet or create new
- **Track processed files** to avoid duplicates

### 3. Smart Features
- **Auto-sheet creation** if no spreadsheet ID provided
- **Upsert logic** - updates existing records, adds new ones
- **Rolling 365-day window** - automatically maintains recent data
- **Error handling** - continues monitoring even if individual files fail

## 📋 Configuration Options

```bash
python auto_sync_monitor.py \
  --spreadsheet-id "YOUR_SHEET_ID" \
  --sweep-interval 300 \              # Check every 5 minutes (polling mode)
  --min-file-age 30 \                 # Wait 30s for file stability
  --tickets-dir ./tickets \           # Custom tickets directory
  --chats-dir ./chats \              # Custom chats directory
  --no-watchdog                       # Use polling instead of real-time
```

## 📊 Workflow Example

1. **Drop CSV file** → `./tickets/ticket-export-04092025.csv`
2. **Monitor detects** → New file found
3. **Stability check** → Wait 30s for file to finish writing
4. **Extract date** → `04092025` from filename
5. **Run analytics** → `python ticket_analytics.py --day 04092025 --export-to-sheets`
6. **Update Google Sheets** → Data synced with all calculated fields
7. **Mark as processed** → Won't process again unless file changes

## 🔍 Monitoring Status

**Check if running:**
```bash
ps aux | grep auto_sync_monitor
```

**View logs:**
```bash
tail -f auto_sync.log
```

**Check processed files:**
```bash
cat .auto_sync_state.json
```

## 📝 Log Output Examples

```
2025-09-04 10:00:00 - INFO - 🔍 AutoSync Monitor initialized
2025-09-04 10:00:00 - INFO -    📂 Watching: ./tickets, ./chats
2025-09-04 10:00:00 - INFO -    📊 Target sheet: 1fDek0n36V1oFAofYDzSsfvOeVu6hTjWjq-9zcy_JxEk
2025-09-04 10:05:23 - INFO - 📄 New tickets file discovered: ticket-export-04092025.csv
2025-09-04 10:05:23 - INFO - 🚀 Processing 1 ticket files, 0 chat files
2025-09-04 10:05:45 - INFO - ✅ Analytics and Google Sheets sync completed successfully
```

## 🚨 Error Handling

- **File locked/in use** → Waits for file stability
- **Analytics failure** → Logs error, continues monitoring
- **Google Sheets API error** → Logs error, retries on next file
- **Authentication expired** → Uses saved token, re-authenticates if needed

## 🔄 Background Service Setup

**Run as systemd service (Linux):**
```bash
# Create service file
sudo nano /etc/systemd/system/ticket-autosync.service

[Unit]
Description=Ticket Dashboard Auto-Sync Monitor
After=network.target

[Service]
Type=simple
User=richie
WorkingDirectory=/home/richie/dev/td/ticket-dashboard
ExecStart=/home/richie/dev/td/ticket-dashboard/start_auto_sync.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable ticket-autosync
sudo systemctl start ticket-autosync
sudo systemctl status ticket-autosync
```

## 📈 Production Usage

**For continuous operation:**
1. **Start monitor** → `./start_auto_sync.sh`
2. **Drop files** → `./tickets/` directory from your CRM exports
3. **Monitor logs** → `tail -f auto_sync.log`
4. **Check Google Sheets** → Data appears automatically

**Historic data bulk import:**
1. **Copy all CSV files** → `./tickets/` directory
2. **Start monitor** → Processes all files in batch
3. **Rolling window** → Only keeps last 365 days
4. **Future files** → Automatically processed as they arrive

The system is now **fully automated** - just drop CSV files and they'll appear in Google Sheets! 🎉