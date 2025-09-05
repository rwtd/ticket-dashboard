# 📊 Google Sheets AI Integration Setup

Configure the AI Assistant to access your complete historical data from Google Sheets archives.

## 🎯 Benefits of Sheets Integration

✅ **Complete Historical Data** - Access all tickets/chats, not just recent CSV files  
✅ **Real-time Data** - Always query the latest information  
✅ **Natural Time Queries** - "Last 35 days", "this quarter", "past 6 months"  
✅ **Dashboard Logic Awareness** - AI understands exactly how your dashboards calculate metrics  

## 🚀 Quick Setup (15 minutes)

### Step 1: Prepare Your Google Sheets

1. **Ensure your sheets contain historical data**:
   - Tickets: All ticket data with proper date columns
   - Chats: Complete chat history with timestamps
   - Standard column names matching your CSV exports

2. **Note your Sheet IDs**:
   ```
   Sheet URL: https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
   Ticket Sheet ID: [your-ticket-sheet-id]
   Chat Sheet ID: [your-chat-sheet-id]
   ```

### Step 2: Configure Credentials

Your existing service account credentials (`service_account_credentials.json`) will work automatically.

If you don't have them set up:
```bash
# Follow the existing GOOGLE_SHEETS_QUICK_REFERENCE.md guide
# The enhanced AI will detect and use your existing credentials
```

### Step 3: Update Sheet Integration (Optional)

Edit `enhanced_query_engine.py` to specify your sheet IDs:

```python
def load_sheets_data(self):
    """Load data from Google Sheets if available"""
    if not self.sheets_service:
        return
        
    # Add your specific sheet IDs and ranges
    self.load_sheet_data('YOUR_TICKET_SHEET_ID', 'Tickets!A:Z', 'tickets_archive')
    self.load_sheet_data('YOUR_CHAT_SHEET_ID', 'Chats!A:Z', 'chats_archive')
```

### Step 4: Test the Integration

```bash
# Start the application
python start_ui.py

# Go to AI-Powered Analysis
# Test with: "For the last 35 days, what was the average response time?"
# The AI will automatically use your complete dataset
```

## 🧠 Enhanced AI Capabilities

### Natural Time Range Queries
```
🤖 "For the last 35 days, what was the average response time?"
→ Automatically filters to the exact date range

🤖 "Show me ticket volume this quarter compared to last quarter"  
→ Calculates quarterly comparisons with proper date filtering

🤖 "Which agent performed best in the past 90 days?"
→ Analyzes 90-day performance window with agent standardization
```

### Dashboard Logic Awareness
The AI now understands exactly how your dashboards work:

```
🤖 "Why is the weekend response time higher?"
→ "Weekend responses average 3.2 hours vs 1.9 hours on weekdays. This is expected given reduced staffing from Friday 7PM through Monday 6AM as defined in your schedule configuration."

🤖 "How do you calculate bot satisfaction?"
→ "Bot satisfaction uses LiveChat's rating system where 'rated good' = 5 (positive), 'rated bad' = 1 (negative), and 'not rated' is excluded. We track Wynn AI (sales) and Agent Scrape (support) separately."
```

### Advanced Time Analysis
```
🤖 "Compare response times: last month vs same month last year"
🤖 "Show me the trend for the past 6 months by month"
🤖 "What was our busiest week in the last quarter?"
🤖 "How does weekend performance compare to weekdays this year?"
```

## 📊 Data Source Priority

The enhanced AI uses this priority order:
1. **Google Sheets** (if configured) - Complete historical data
2. **Local CSV files** (fallback) - Recent data from uploads/directories

This ensures you always get the most complete analysis possible.

## 🔧 Advanced Configuration

### Custom Sheet Ranges
Modify `enhanced_query_engine.py` for specific data ranges:
```python
# Load specific date ranges
self.load_sheet_data('SHEET_ID', 'Tickets!A1:Z1000', 'recent_tickets')

# Load specific columns  
self.load_sheet_data('SHEET_ID', 'Tickets!A:E', 'ticket_summary')

# Load multiple sheets
self.load_sheet_data('SHEET_ID', '2025_Data!A:Z', 'tickets_2025')
self.load_sheet_data('SHEET_ID', '2024_Data!A:Z', 'tickets_2024')
```

### Performance Optimization
For large datasets (10k+ rows):
```python
# In enhanced_query_engine.py, add data sampling
def load_sheet_data(self, sheet_id, range_name, table_name):
    # ... existing code ...
    
    # For large datasets, consider sampling or pagination
    if len(df) > 50000:
        logging.info(f"Large dataset detected ({len(df)} rows), optimizing...")
        # Add indexing or sampling logic as needed
```

## 🎯 Dashboard Logic Integration

The AI is now aware of these key calculations:

### Response Time Logic
- Converts HH:mm:ss to decimal hours: `hours + (minutes/60)`
- Applies timezone conversion: CDT→ADT (+1 hour)
- Excludes weekend periods unless specifically requested

### Agent Standardization  
- Maps all name variations to real names consistently
- Handles historical name changes in data
- Provides consistent reporting across time periods

### Weekend Detection
- Uses schedule.yaml configuration: Friday 7PM - Monday 6AM
- Applies separate performance expectations
- Excludes from standard metrics unless requested

### Bot Analysis
- Identifies Wynn AI (sales) and Agent Scrape (support) separately  
- Tracks satisfaction ratings with proper exclusions
- Monitors transfer rates and escalation patterns

## ✅ Success Indicators

After setup, you should see:
- ✅ AI responds to natural time range queries ("last 35 days")
- ✅ Explanations reference actual dashboard calculation logic
- ✅ Historical analysis beyond local CSV file dates
- ✅ Consistent agent names and proper timezone handling
- ✅ Business context in responses (weekend impact, bot performance, etc.)

## 🚨 Troubleshooting

### "No Google Sheets data found"
```bash
# Check credentials
ls -la service_account_credentials.json

# Verify sheet permissions
# Ensure service account has "Viewer" access to your sheets
```

### "Time range not working"
```bash
# Test time parsing
python -c "
from enhanced_query_engine import EnhancedSupportQueryEngine
engine = EnhancedSupportQueryEngine('test-key')
print(engine.parse_time_range('last 35 days'))
"
```

### Performance Issues
```bash
# Check data size
# Large sheets (>100k rows) may need optimization
# Consider using specific ranges or recent data subsets
```

## 🎉 You're Ready!

Your AI Assistant now has:
- 🧠 **Complete Historical Knowledge** - All your tickets and chats
- ⏰ **Natural Time Understanding** - "Last 35 days", "this quarter", etc.  
- 📊 **Dashboard Logic Awareness** - Explains exactly how metrics are calculated
- 🚀 **Real-time Analysis** - Always uses the latest data from Google Sheets

Ask natural questions and get intelligent, contextual responses that understand your business! 🎯