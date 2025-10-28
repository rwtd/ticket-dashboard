# Weekly Response Breakdown Widget Fix

## Issue
The weekly response breakdown widget was showing only a green "All Tickets" bar instead of separate weekday and weekend bars.

## Root Cause
The widget was incorrectly showing three series:
1. "All Tickets" (green) - all tickets combined
2. "Weekday" (red) - weekday tickets only
3. "Weekend" (optional, yellow) - weekend tickets only

This caused the "All Tickets" and "Weekday" bars to be nearly identical (since most tickets are weekday), making the red bar invisible behind the green one.

## Solution
Changed the widget to show only two series:
1. **Weekday** (green) - weekday tickets only
2. **Weekend** (red) - weekend tickets only

This provides a clear visual comparison between weekday and weekend response times.

## Changes Made

### 1. Updated Bar Series (widgets/registry.py, lines 819-835)
**Before:**
```python
weekly_all = dfw.groupby("week_start")["val"].agg(agg).reset_index(name="All")
weekly_weekday = dfw[dfw["Weekend_Ticket"] == False].groupby("week_start")["val"].agg(agg).reset_index(name="Weekday")
# ...merge...
fig.add_trace(go.Bar(x=result["week_start"], y=result["All"], name="All Tickets", marker_color="rgba(78,205,196,0.85)"))
fig.add_trace(go.Bar(x=result["week_start"], y=result["Weekday"], name="Weekday", marker_color="rgba(255,107,107,0.85)"))
```

**After:**
```python
weekly_weekday = dfw[dfw["Weekend_Ticket"] == False].groupby("week_start")["val"].agg(agg).reset_index(name="Weekday")
weekly_weekend = dfw[dfw["Weekend_Ticket"] == True].groupby("week_start")["val"].agg(agg).reset_index(name="Weekend")
# ...merge...
fig.add_trace(go.Bar(x=result["week_start"], y=result["Weekday"], name="Weekday", marker_color="rgba(78,205,196,0.85)"))
fig.add_trace(go.Bar(x=result["week_start"], y=result["Weekend"], name="Weekend", marker_color="rgba(255,107,107,0.85)"))
```

### 2. Updated Trend Lines (widgets/registry.py, lines 839-860)
Removed "All Tickets" trend line and updated colors to match the new bar series:
- Weekday trend: green dashed line
- Weekend trend: red dotted line

### 3. Updated Widget Metadata (widgets/registry.py, lines 887-900)
- Removed `include_weekend_series` parameter (weekend always shown now)
- Updated description to reflect "Weekday vs Weekend" comparison
- Updated examples to remove weekend series toggle

### 4. Removed Unused Parameter (widgets/registry.py, line 793)
Removed the unused `include_weekend_series` parameter from the function.

## Data Verification
Confirmed that Firestore data is correct:
- **8,329 weekday tickets** (False)
- **1,482 weekend tickets** (True)
- Weekend_Ticket column properly saved as `is_weekend` in Firestore and restored as `Weekend_Ticket` when loaded

## Testing
Widget test passed successfully:
```
✅ PASS (6.56s) - weekly_response_breakdown
```

## Visual Result
The widget now shows:
- **Green bars** representing weekday response times
- **Red bars** representing weekend response times
- Optional trend lines for both series
- Clear visual comparison between weekday and weekend performance

## Related Files
- `widgets/registry.py` - Widget implementation
- `firestore_db.py` - Column mapping (`Weekend_Ticket` ↔ `is_weekend`)
- `ticket_processor.py` - Weekend detection logic
- `test_widgets.py` - Widget testing script