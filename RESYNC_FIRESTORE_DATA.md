# Re-sync Firestore Data - Fix Satisfaction Data

## Problem Identified

The Firestore database has OLD data from before the chat processing fix. The current data is missing:
- ❌ `rate_raw` - Raw rating text
- ❌ `rating_value` - Numeric rating (1 or 5)

The sync service code is now CORRECT (uses ChatDataProcessor), but the data needs to be re-synced.

## Solution: Re-sync Data

### Step 1: Clear Old Chat Data (Optional but Recommended)

You can either:
1. **Delete old data** (clean slate)
2. **Just re-sync** (will overwrite existing records)

**Option A: Clean Slate (Recommended)**
```python
# Delete old chat data from Firestore
from firestore_db import get_database
db = get_database()

# This will delete all old chat records
# (New sync will repopulate with properly processed data)
print("Clearing old chat data...")
# Note: Firestore doesn't have a "clear collection" API
# Safest is to just re-sync (it will overwrite with correct data)
```

**Option B: Just Re-sync** (Easier - will overwrite)
```bash
# This will fetch last 365 days and overwrite existing records
python firestore_sync_service.py --full
```

### Step 2: Run Full Sync

```bash
# Re-sync all data with proper chat processing
python firestore_sync_service.py --full
```

**Expected Output:**
```
======================================================================
🎫 SYNCING TICKETS FROM HUBSPOT
======================================================================
📥 Full sync: fetching last 365 days
📥 Fetched X tickets from HubSpot
✅ Synced X tickets to Firestore

======================================================================
💬 SYNCING CHATS FROM LIVECHAT
======================================================================
📥 Full sync: fetching last 365 days
📥 Fetched X chats from LiveChat
✅ Synced X chats to Firestore

⏱️  Completed in XX.Xs
✅ FULL SYNC COMPLETE: X tickets, X chats
```

### Step 3: Verify Satisfaction Data

```bash
python debug_firestore_chats.py
```

**Expected Output (AFTER fix):**
```
============================================================
🔍 Checking for satisfaction data columns:
============================================================
  ✅ rate_raw             - Raw rating text (e.g., "rated good")
     └─ X/X records have data
     └─ Sample: rated good
  
  ✅ rating_value         - Numeric rating (1 or 5)
     └─ X/X records have data
     └─ Sample: 5
  
  ✅ has_rating           - Boolean - was chat rated?
     └─ X/X records have data
     └─ Sample: True

============================================================
📊 Satisfaction Statistics:
============================================================
  Rated chats: X/X
  Good ratings: X (XX%)
  Bad ratings: X (XX%)
```

### Step 4: Test Widgets

Once data is re-synced with satisfaction columns:

```bash
# Start the app
python start_ui.py

# In another terminal, test widgets
python test_widgets.py
```

**Test satisfaction-dependent widgets:**
```bash
# Weekly bot satisfaction (requires rating_value)
curl http://localhost:5000/widgets/weekly_bot_satisfaction

# Bot performance comparison (requires rating_value)
curl http://localhost:5000/widgets/bot_performance_comparison

# Daily chat trends (requires rating_value)
curl http://localhost:5000/widgets/daily_chat_trends_performance
```

## Understanding the Fix

### What Was Wrong
The old sync service was NOT using ChatDataProcessor, so it saved raw API data to Firestore without processing satisfaction ratings.

### What Was Fixed
Updated [`firestore_sync_service.py:242-250`](firestore_sync_service.py:242):
```python
def _process_chats(self, df: pd.DataFrame) -> pd.DataFrame:
    """Process chats using ChatDataProcessor"""
    processor = ChatDataProcessor()
    processor.df = df
    processor.process_data()  # ← This processes ratings!
    return processor.df
```

### What ChatDataProcessor Does
The [`ChatDataProcessor.process_data()`](chat_processor.py:90) method:
1. Normalizes column names
2. **Processes satisfaction ratings** (`rate` → `rate_raw`, `rating_value`, `has_rating`)
3. Classifies agent types (bot vs human)
4. Detects transfers
5. Calculates duration metrics
6. Standardizes agent names

## Troubleshooting

### Issue: Still Missing Satisfaction Data After Re-sync

**Check 1: Verify ChatDataProcessor Works**
```python
from chat_processor import ChatDataProcessor
import pandas as pd

# Test with sample data
test_data = pd.DataFrame([{
    'rate': 'rated good',
    'chat_id': 'TEST123',
    'created_at': '2025-01-01T00:00:00Z'
}])

processor = ChatDataProcessor()
processor.df = test_data
processor.process_data()

print(processor.df.columns.tolist())
# Should include: rate_raw, rating_value, has_rating
```

**Check 2: Verify Sync Service Uses Processor**
```bash
# Add debug logging to see what's happening
grep -A 5 "_process_chats" firestore_sync_service.py
```

Should show:
```python
def _process_chats(self, df: pd.DataFrame) -> pd.DataFrame:
    """Process chats using ChatDataProcessor"""
    processor = ChatDataProcessor()
    processor.df = df
    processor.process_data()
    return processor.df
```

**Check 3: Source Data Has Ratings**
```bash
# Check if source CSV has rating data
head -1 chats/*.csv | grep -i rate
```

If source data has no ratings, then Firestore won't have them either (garbage in, garbage out).

### Issue: Sync is Slow

**Solution: Run Incremental Sync Instead**
```bash
# After initial full sync, use incremental for updates
python firestore_sync_service.py --incremental
```

Incremental sync only fetches data since last sync (much faster).

## Next Steps After Re-sync

1. ✅ Verify satisfaction data exists: `python debug_firestore_chats.py`
2. ✅ Test chat widgets: `python test_widgets.py`
3. ✅ Test dashboard locally: `python start_ui.py`
4. ✅ Verify chat satisfaction charts display correctly
5. 📦 Ready for deployment!

## Quick Command Reference

```bash
# Re-sync everything
python firestore_sync_service.py --full

# Verify data
python debug_firestore_chats.py

# Test widgets
python test_widgets.py

# Start dashboard
python start_ui.py
```

## Summary

The code is correct, but the data in Firestore is old. Running a full sync will:
1. Fetch data from LiveChat API
2. Process it through ChatDataProcessor (adds satisfaction columns)
3. Save properly processed data to Firestore
4. Widgets will then display satisfaction metrics correctly

**Critical Fix Applied:**
- Sync service now uses ChatDataProcessor
- New data will have: `rate_raw`, `rating_value`, `has_rating`
- Widgets depending on satisfaction data will work

Just run: `python firestore_sync_service.py --full` 🚀