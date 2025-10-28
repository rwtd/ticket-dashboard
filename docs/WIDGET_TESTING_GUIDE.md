# Widget Testing Guide

This guide helps you test all widgets locally with Firestore integration before deployment.

## Prerequisites

1. **Firestore Setup**: Ensure Firestore is configured and has data
   ```bash
   # Check if Firestore has data
   python debug_firestore_chats.py
   ```

2. **Start the Application**:
   ```bash
   python start_ui.py
   ```

## Widget Endpoints

All widgets are accessible at: `http://localhost:5000/widgets/<widget_name>`

### Testing Strategy

#### 1. Quick Smoke Test (Test All Widgets)
Open these URLs in your browser to verify they load without errors:

**Ticket Widgets:**
- http://localhost:5000/widgets/tickets_by_pipeline
- http://localhost:5000/widgets/weekday_weekend_distribution
- http://localhost:5000/widgets/weekly_response_breakdown
- http://localhost:5000/widgets/agent_ticket_volume_distribution
- http://localhost:5000/widgets/agent_response_time_comparison
- http://localhost:5000/widgets/agent_weekly_response_by_agent
- http://localhost:5000/widgets/agent_weekly_ticket_volume_by_agent
- http://localhost:5000/widgets/performance_vs_volume
- http://localhost:5000/widgets/pipeline_distribution_by_agent
- http://localhost:5000/widgets/pipeline_response_time_heatmap
- http://localhost:5000/widgets/weekly_response_trends_weekday
- http://localhost:5000/widgets/weekly_response_trends_weekend
- http://localhost:5000/widgets/historic_weekly_volume

**Chat Widgets:**
- http://localhost:5000/widgets/chat_weekly_volume_breakdown
- http://localhost:5000/widgets/weekly_bot_satisfaction
- http://localhost:5000/widgets/bot_volume_duration
- http://localhost:5000/widgets/human_volume_duration
- http://localhost:5000/widgets/bot_performance_comparison
- http://localhost:5000/widgets/daily_chat_trends_performance

**General Widgets:**
- http://localhost:5000/widgets/weekly_response_time_trends
- http://localhost:5000/widgets/volume_daily_historic

#### 2. Parameter Testing

Test widgets with different parameters to verify they work correctly:

**Time Range Testing:**
```bash
# 8 weeks
http://localhost:5000/widgets/weekly_response_breakdown?range=8w

# 12 weeks (default)
http://localhost:5000/widgets/weekly_response_breakdown?range=12w

# Year to date
http://localhost:5000/widgets/weekly_response_breakdown?range=ytd

# All time
http://localhost:5000/widgets/weekly_response_breakdown?range=all
```

**Stat Toggle Testing:**
```bash
# Median (default)
http://localhost:5000/widgets/weekly_response_time_trends?stat=median

# Mean
http://localhost:5000/widgets/weekly_response_time_trends?stat=mean
```

**Agent Filtering:**
```bash
# Single agent
http://localhost:5000/widgets/agent_response_time_comparison?agents=Nova

# Multiple agents
http://localhost:5000/widgets/agent_response_time_comparison?agents=Nova,Girly
```

**Pipeline Filtering:**
```bash
# Single pipeline
http://localhost:5000/widgets/tickets_by_pipeline?pipelines=Support

# Multiple pipelines
http://localhost:5000/widgets/tickets_by_pipeline?pipelines=Support,Live%20Chat
```

#### 3. Data Source Verification

Check the console output to verify data source priority:

**Expected Console Output:**
```
✅ Using cached tickets data (fastest)
# OR
✅ Using Firestore tickets data (real-time primary source)
# OR
✅ Using Google Sheets tickets data (batch fallback)
# OR
✅ Using processed tickets data from results directory
# OR
⚙️ Processed raw tickets CSV data (final fallback)
```

#### 4. Visual Inspection Checklist

For each widget, verify:
- [ ] Chart renders without errors
- [ ] Data appears correct (matches expected values)
- [ ] Interactive controls work (hover, zoom, pan)
- [ ] Legends are visible and accurate
- [ ] Axes labels are clear
- [ ] Colors match the design theme
- [ ] No console errors in browser DevTools

#### 5. Widget Gallery Test

Visit the widget gallery page to test all widgets at once:
```bash
http://localhost:5000/widgets
```

This page shows all available widgets with example parameters.

## Automated Testing Script

Create a test script to check all widgets programmatically:

```python
# test_widgets.py
import requests
from urllib.parse import urljoin

BASE_URL = "http://localhost:5000"
WIDGETS = [
    # Ticket widgets
    "tickets_by_pipeline",
    "weekday_weekend_distribution",
    "weekly_response_breakdown",
    "agent_ticket_volume_distribution",
    "agent_response_time_comparison",
    "agent_weekly_response_by_agent",
    "agent_weekly_ticket_volume_by_agent",
    "performance_vs_volume",
    "pipeline_distribution_by_agent",
    "pipeline_response_time_heatmap",
    "weekly_response_trends_weekday",
    "weekly_response_trends_weekend",
    "historic_weekly_volume",
    # Chat widgets
    "chat_weekly_volume_breakdown",
    "weekly_bot_satisfaction",
    "bot_volume_duration",
    "human_volume_duration",
    "bot_performance_comparison",
    "daily_chat_trends_performance",
    # General widgets
    "weekly_response_time_trends",
    "volume_daily_historic",
]

def test_widgets():
    results = []
    for widget in WIDGETS:
        url = urljoin(BASE_URL, f"/widgets/{widget}")
        try:
            response = requests.get(url, timeout=10)
            status = "✅ PASS" if response.status_code == 200 else f"❌ FAIL ({response.status_code})"
            results.append(f"{status} - {widget}")
        except Exception as e:
            results.append(f"❌ ERROR - {widget}: {e}")
    
    print("\n".join(results))
    print(f"\nTotal: {len([r for r in results if '✅' in r])}/{len(WIDGETS)} passed")

if __name__ == "__main__":
    test_widgets()
```

Run the test:
```bash
python test_widgets.py
```

## Common Issues and Solutions

### Issue: "No data for selected range/params"

**Causes:**
- Firestore has no data for the date range
- Date filtering is too restrictive
- Data hasn't been synced yet

**Solutions:**
1. Check Firestore data:
   ```bash
   python debug_firestore_chats.py
   ```

2. Run a sync:
   ```bash
   python firestore_sync_service.py --full
   ```

3. Try "all" range:
   ```
   http://localhost:5000/widgets/weekly_response_breakdown?range=all
   ```

### Issue: Widget shows "⚠️ Firestore unavailable"

**Causes:**
- Firestore credentials not configured
- Firestore database doesn't exist
- Network connectivity issues

**Solutions:**
1. Verify Firestore setup:
   ```bash
   python test_firestore_setup.py
   ```

2. Check environment variables:
   ```bash
   echo $GOOGLE_APPLICATION_CREDENTIALS
   ```

3. Widget should gracefully fall back to Google Sheets or local CSV

### Issue: Widget loads slowly

**Causes:**
- Cache not working
- Large dataset without date filtering
- Multiple fallback attempts

**Solutions:**
1. Enable caching (should be automatic)
2. Use date range parameters: `?range=12w`
3. Check console for data source being used

## Performance Testing

Test widget performance with different configurations:

```bash
# Small dataset (4 weeks)
time curl "http://localhost:5000/widgets/weekly_response_breakdown?range=4w"

# Medium dataset (12 weeks - default)
time curl "http://localhost:5000/widgets/weekly_response_breakdown?range=12w"

# Large dataset (all time)
time curl "http://localhost:5000/widgets/weekly_response_breakdown?range=all"
```

**Expected Performance:**
- Cached: < 100ms
- Firestore: < 500ms
- Google Sheets: < 1s
- CSV processing: < 2s

## Embedding Test

Test widget embedding in an iframe:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Widget Embed Test</title>
</head>
<body>
    <h1>Embedded Widget Test</h1>
    
    <iframe 
        src="http://localhost:5000/widgets/weekly_response_breakdown?range=12w" 
        width="100%" 
        height="400" 
        frameborder="0">
    </iframe>
</body>
</html>
```

## Next Steps

Once all widgets pass local testing:

1. ✅ Verify all widgets load without errors
2. ✅ Confirm data appears correct
3. ✅ Test parameter variations
4. ✅ Verify Firestore integration works
5. ✅ Check fallback behavior
6. 📦 Ready for Cloud Run deployment!

## Deployment Readiness Checklist

Before deploying to Cloud Run:

- [ ] All widgets tested locally
- [ ] Firestore integration verified
- [ ] Fallback chain tested (Firestore → Sheets → CSV)
- [ ] Performance acceptable (< 1s response time)
- [ ] No console errors
- [ ] Embedding works in iframe
- [ ] All parameter combinations tested
- [ ] Visual appearance matches design

Once complete, proceed with:
```bash
# Deploy to Cloud Run
make PROJECT_ID=your-project REGION=us-central1 all