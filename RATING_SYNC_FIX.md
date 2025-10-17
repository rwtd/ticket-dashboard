# Rating Data Sync Fix

## Problem Summary

**Issue**: Source CSV data contained ~25% of chats with ratings ("rated good", "rated bad"), but Firestore showed all 842 chats with `has_rating=False`.

**Root Cause**: The `rate_raw` column (containing the source rating text from CSV) was not being preserved when saving to Firestore, causing the rating calculation logic to fail when data was retrieved.

## Technical Details

### The Data Flow

1. **CSV Source** → Contains `rate` column with values:
   - `"rated good"` → Should map to `rating_value=5.0`, `has_rating=True`
   - `"rated bad"` → Should map to `rating_value=1.0`, `has_rating=True`
   - `"not rated"` → Should map to `rating_value=None`, `has_rating=False`

2. **ChatDataProcessor** ([`chat_processor.py:192-194`](chat_processor.py:192-194)):
   ```python
   self.df['rating_value'] = self.df['rate_raw'].apply(self._normalize_rating)
   self.df['has_rating'] = self.df['rating_value'].notna()
   ```
   - Reads `rate_raw` column
   - Applies `_normalize_rating()` method to convert text to numeric values
   - Sets `has_rating` flag based on whether rating_value exists

3. **Firestore Storage** ([`firestore_db.py:458-530`](firestore_db.py:458-530)):
   - **PROBLEM**: The `_prepare_chat_data()` method had logic that skipped columns with `pd.NA` values
   - When `rate_raw` was empty or NA, it wasn't saved to Firestore
   - Without `rate_raw` in Firestore, the processor couldn't recalculate ratings

### The Fix

Modified [`firestore_db.py:495-501`](firestore_db.py:495-501) to always preserve `rate_raw`:

```python
# Special handling for rate_raw - always include it even if empty/NA
# This is critical because chat_processor needs it to calculate rating_value
if col == 'rate_raw':
    value = row[col]
    # Store empty string for NA/None to preserve the column
    data[key] = str(value) if pd.notna(value) else ''
    continue
```

**Key Changes**:
- `rate_raw` is now **always** saved to Firestore, even if empty
- Empty/NA values are stored as empty strings to preserve the column
- This ensures the chat processor can always recalculate `rating_value` and `has_rating`

## Testing

Created [`test_rating_sync_fix.py`](test_rating_sync_fix.py) which verifies:

✅ **Rating Processing**:
- "rated good" → `rating_value=5.0`, `has_rating=True`
- "rated bad" → `rating_value=1.0`, `has_rating=True`  
- "not rated" → `rating_value=None`, `has_rating=False`

✅ **Firestore Data Preparation**:
- `rate_raw` is always present in Firestore data
- `rating_value` and `has_rating` are correctly calculated
- All rating fields are preserved through the sync process

**Test Results**: All tests passed ✅

## Next Steps

To apply this fix to your Firestore database:

1. **Run a full sync** to update all existing chat records:
   ```bash
   python firestore_sync_service.py --full
   ```

2. **Verify the fix** by checking a few chat records in Firestore:
   ```bash
   python debug_firestore_chats.py
   ```
   
   You should now see:
   - `rate_raw` column present in all chats
   - `rating_value` correctly set for rated chats (1.0 or 5.0)
   - `has_rating=True` for ~25% of chats (those with ratings)

3. **Monitor** the dashboard to confirm satisfaction metrics are now displaying correctly

## Files Modified

- [`firestore_db.py`](firestore_db.py:495-501) - Added special handling for `rate_raw` column
- [`test_rating_sync_fix.py`](test_rating_sync_fix.py) - Created comprehensive test suite

## Related Code

- [`chat_processor.py:316-351`](chat_processor.py:316-351) - `_normalize_rating()` method that handles rating conversion
- [`firestore_sync_service.py:242-250`](firestore_sync_service.py:242-250) - `_process_chats()` method that uses ChatDataProcessor