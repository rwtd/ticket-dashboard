# Debugging Skills Guide
Systematic debugging patterns and solutions for Ticket Dashboard issues

## Table of Contents
1. [Debugging Methodology](#debugging-methodology)
2. [Cloud Run Deployment Issues](#cloud-run-deployment-issues)
3. [Widget Data Issues](#widget-data-issues)
4. [Common Error Patterns](#common-error-patterns)
5. [Diagnostic Tools](#diagnostic-tools)

---

## Debugging Methodology

### Step 1: Gather Evidence
**ALWAYS start by collecting the complete error context:**

```bash
# For Cloud Run deployments, check logs
gcloud logging read "resource.type=cloud_run_revision" --limit=100 --format=json

# For local development
python start_ui.py 2>&1 | tee debug.log
```

**Evidence checklist:**
- [ ] Full error traceback
- [ ] Error frequency (1 occurrence vs 25 occurrences)
- [ ] Context: when does it happen? (startup, specific endpoint, data processing)
- [ ] Environment: local vs Cloud Run vs production
- [ ] Recent changes: what was modified before the error appeared?

### Step 2: Classify the Issue
Use this decision tree:

```
Is it a deployment issue?
├─ YES → See "Cloud Run Deployment Issues"
└─ NO
   └─ Is it a data display issue?
      ├─ YES → See "Widget Data Issues"
      └─ NO → See "Common Error Patterns"
```

### Step 3: Form Hypothesis
Based on error classification, formulate a testable hypothesis:
- "The widget is empty because Firestore data isn't being loaded"
- "Pipeline IDs show because HubSpot API mapping isn't applied"
- "Memory exceeded because container limit is too low"

### Step 4: Test Hypothesis
**CRITICAL**: Test ONE change at a time
- Make the smallest possible change
- Deploy/test
- Verify fix
- Document result

### Step 5: Verify Fix
Check multiple angles:
- Does the specific error disappear from logs?
- Do related features still work?
- Are there any new errors introduced?

---

## Cloud Run Deployment Issues

### Issue 1: ImportError for Python Packages

**Symptoms:**
```
ImportError: No module named 'google.cloud.firestore'
```

**Root Cause:** Missing or improperly specified dependency in requirements.txt

**Diagnosis:**
1. Check requirements.txt for the package
2. Verify version specification format
3. Check if package is commented out or has wrong name

**Solution Pattern:**
```python
# ❌ WRONG - No version specified
google-cloud-firestore

# ✅ CORRECT - Version constraint specified
google-cloud-firestore>=2.11.0
```

**Files to Check:**
- [`requirements.txt`](../../requirements.txt:1) - Main dependencies
- [`requirements.minimal.txt`](../../requirements.minimal.txt:1) - Minimal set (if used)

**Prevention:**
- Always specify version constraints (>=, ==, ~=)
- Test locally with `pip install -r requirements.txt` in fresh venv
- Check Cloud Run build logs for dependency resolution errors

---

### Issue 2: Memory Limit Exceeded

**Symptoms:**
```
Memory limit of 256 MiB exceeded with 279 MiB used
Container instance terminated
```

**Root Cause:** Container memory limit too low for data processing workload

**Diagnosis:**
1. Check current memory allocation in deployment config
2. Review memory usage patterns in Cloud Run metrics
3. Identify memory-intensive operations (data loading, processing, caching)

**Solution Pattern:**
```yaml
# In cloudrun/service.yaml
resources:
  limits:
    memory: "2Gi"  # ✅ Increased from 512Mi
    cpu: "1000m"
```

```makefile
# In Makefile
--memory=2Gi \  # ✅ Increased from 1Gi
```

**Files to Check:**
- [`Makefile`](../../Makefile:52) - Memory allocation for `gcloud run deploy`
- [`cloudrun/service.yaml`](../../cloudrun/service.yaml:40) - Service configuration

**Memory Sizing Guidelines:**
- **512Mi**: Basic Flask app, no data processing
- **1Gi**: Light data processing, small datasets
- **2Gi**: Widget data processing, medium datasets (RECOMMENDED for this app)
- **4Gi**: Heavy data processing, large datasets, ML models

**Prevention:**
- Monitor Cloud Run memory metrics in GCP Console
- Add memory usage logging: `psutil.Process().memory_info().rss / 1024 / 1024` MB
- Load-test locally with production data volumes

---

### Issue 3: Series Ambiguity Errors

**Symptoms:**
```python
ValueError: The truth value of a Series is ambiguous. Use a.empty, a.bool(), a.item(), a.any() or a.all()
```

**Root Cause:** Boolean comparison on pandas Series object instead of scalar value

**Common Patterns:**

#### Pattern A: Timezone Checking
```python
# ❌ WRONG - Compares Series object
if df['Create date'].dt.tz is None:
    df['Create date'] = df['Create date'].dt.tz_localize('UTC')

# ✅ CORRECT - Sample the Series accessor property first
current_tz = df['Create date'].dt.tz  # Get Series accessor property
if current_tz is None:
    df['Create date'] = df['Create date'].dt.tz_localize('UTC')
```

#### Pattern B: Data Validation
```python
# ❌ WRONG - Direct boolean comparison
if df['column'] is None:
    # handle missing data

# ✅ CORRECT - Use pandas methods
if df['column'].isna().all():
    # handle missing data

# ✅ CORRECT - Check existence first
if 'column' not in df.columns or df['column'].isna().all():
    # handle missing data
```

**Files to Check:**
- [`widgets/registry.py`](../../widgets/registry.py:843) - Timezone conversion
- Any pandas DataFrame operations with boolean conditions

**Prevention:**
- Never use `is None` or `== None` on pandas Series
- Use `.isna()`, `.notna()`, `.empty`, `.any()`, `.all()` instead
- Sample scalar values with `.iloc[0]` when needed for comparison

---

## Widget Data Issues

### Issue 1: Empty Charts (No Data Displayed)

**Symptoms:**
- Widget loads but shows "No data for selected range/params"
- Chart area is blank or shows fallback message

**Common Root Causes (in priority order):**

#### Cause A: Firestore Data Not Loading
```python
# Check if Firestore is actually being used
print(f"🔍 DEBUG: Attempting to load {source} from Firestore")
df = db.get_tickets(start_date=start_dt, end_date=end_dt)
print(f"🔍 DEBUG: Firestore returned {len(df) if df is not None else 0} records")
```

**Solution:**
1. Verify Firestore credentials are mounted in Cloud Run
2. Check if `GOOGLE_APPLICATION_CREDENTIALS` env var is set
3. Add debug logging to [`widgets/registry.py:_load_source_dataframe`](../../widgets/registry.py:294)
4. Verify fallback to CSV/Sheets if Firestore fails

#### Cause B: Missing Required Columns
```python
# Widget expects 'Weekend_Ticket' but Firestore data doesn't have it
if 'Weekend_Ticket' not in df.columns:
    # Need to generate it
    df = _ensure_ticket_columns(df)
```

**Solution:**
- Use [`_ensure_ticket_columns()`](../../widgets/registry.py:811) for ticket data
- Use [`_ensure_chat_columns()`](../../widgets/registry.py:865) for chat data
- These functions generate missing columns from available data

#### Cause C: Date Filtering Too Restrictive
```python
# Check if date range excludes all data
print(f"Date range: {start_dt} to {end_dt}")
print(f"Data date range: {df['Create date'].min()} to {df['Create date'].max()}")
```

**Solution:**
- Verify timezone consistency (tickets: `US/Eastern`, chats: `Canada/Atlantic`)
- Check if `compute_range_bounds()` returns correct dates
- Ensure date column is properly parsed with `errors='coerce'`

---

### Issue 2: Pipeline IDs Instead of Names

**Symptoms:**
- Chart legend shows numbers (e.g., "95947431") instead of names (e.g., "Support")
- Pipeline-related widgets display numeric IDs

**Root Cause:** HubSpot API pipeline mapping not applied to Firestore data

**Diagnosis:**
```python
# Check if Pipeline column contains IDs or names
sample_values = df['Pipeline'].dropna().head(5)
print(f"Pipeline values: {sample_values.tolist()}")
# If all numeric → needs mapping
# If all strings → already mapped
```

**Solution:**
```python
# Apply pipeline mapping in data loading pipeline
df = _apply_pipeline_mapping(df)

# This function:
# 1. Detects numeric pipeline IDs
# 2. Fetches mapping from HubSpot API (if HUBSPOT_API_KEY available)
# 3. Falls back to static mapping (if API unavailable)
# 4. Normalizes long names to short display names
```

**Files to Check:**
- [`widgets/registry.py:_apply_pipeline_mapping`](../../widgets/registry.py:739) - Pipeline ID to name mapping
- [`widgets/registry.py:_normalize_pipeline_names`](../../widgets/registry.py:731) - Display name normalization
- [`hubspot_fetcher.py:fetch_pipelines`](../../hubspot_fetcher.py:1) - HubSpot API integration

**Prevention:**
- Always call `_apply_pipeline_mapping()` after loading ticket data from Firestore
- Maintain fallback mapping for common pipeline IDs in code
- Monitor HubSpot API availability

---

### Issue 3: Non-CS Agents Appearing in Charts

**Symptoms:**
- Agent widgets show Spencer, Erin, Richie, test users
- Should only show: Bhushan, Girly, Nova, Francis

**Root Cause:** Agent filtering not applied to widget data

**Solution:**
```python
# Apply CS agent filtering
data = _filter_to_cs_agents(data, owner_col)

# This function:
# 1. Normalizes all agent name variations
# 2. Filters to only 4 CS agents
# 3. Returns None for non-CS agents
```

**Agent Name Normalization Map:**
```python
{
    'shan', 'shan d': 'Bhushan',
    'chris', 'chris s': 'Francis',
    'nora', 'nora n': 'Nova',
    'gillie', 'gillie e', 'girly', 'girly e': 'Girly'
}
```

**Files to Check:**
- [`widgets/registry.py:_filter_to_cs_agents`](../../widgets/registry.py:689) - CS agent filtering
- [`widgets/registry.py:_normalize_agent_name`](../../widgets/registry.py:651) - Name normalization

**Prevention:**
- Always apply `_filter_to_cs_agents()` in agent-related widgets
- Use normalized names in queries/filters
- Test with production data that includes non-CS agents

---

## Common Error Patterns

### Pattern 1: NaT (Not a Time) Comparison Errors

**Error:**
```python
TypeError: Cannot compare tz-naive and tz-aware datetime-like objects
# OR
ValueError: Invalid comparison between dtype=datetime64[ns] and NaT
```

**Root Cause:** Mixing timezone-aware and naive datetimes, or comparing NaT values

**Solution:**
```python
# ALWAYS use errors='coerce' when parsing dates
df['date_col'] = pd.to_datetime(df['date_col'], errors='coerce')

# ALWAYS check for NaT before comparisons
df = df[df['date_col'].notna()]

# ALWAYS localize or convert consistently
df['date_col'] = df['date_col'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
```

---

### Pattern 2: KeyError for Missing Columns

**Error:**
```python
KeyError: 'Weekend_Ticket'
# OR
KeyError: 'rating_value'
```

**Root Cause:** Expected column doesn't exist in DataFrame (Firestore schema drift)

**Solution:**
```python
# Check before accessing
if 'Weekend_Ticket' in df.columns:
    weekend_data = df[df['Weekend_Ticket'] == True]
else:
    # Generate or skip
    df = _ensure_ticket_columns(df)
    weekend_data = df[df['Weekend_Ticket'] == True]

# Or use .get() with default
value = row.get('column_name', default_value)
```

---

### Pattern 3: Duplicate Records Causing Data Anomalies

**Symptoms:**
- Chat counts double what they should be
- Metrics don't match between widgets
- Repeating patterns in time series

**Root Cause:** Firestore returning duplicate documents (by chat_id or ticket_id)

**Solution:**
```python
# ALWAYS deduplicate Firestore data
if 'chat_id' in df.columns:
    original_count = len(df)
    df = df.drop_duplicates(subset=['chat_id'], keep='first')
    if original_count != len(df):
        print(f"⚠️ Removed {original_count - len(df)} duplicates")
```

**Files to Check:**
- [`widgets/registry.py:_load_source_dataframe`](../../widgets/registry.py:294) - Chat deduplication
- Any widget function that processes chat data

---

## Diagnostic Tools

### Tool 1: Add Debug Logging

**Always add these debug statements when investigating data issues:**

```python
print(f"🔍 DEBUG: DataFrame shape: {df.shape}")
print(f"🔍 DEBUG: Available columns: {df.columns.tolist()}")
print(f"🔍 DEBUG: Sample data:\n{df.head(2)}")
print(f"🔍 DEBUG: Date range: {df['date_col'].min()} to {df['date_col'].max()}")
print(f"🔍 DEBUG: Unique values in key column: {df['column'].nunique()}")
```

**Pattern for widget debugging:**
```python
def widget_function(params):
    print(f"🔍 DEBUG: Widget called with params: {params}")
    
    df = load_data()
    print(f"🔍 DEBUG: Loaded {len(df) if df is not None else 0} records")
    
    if df is None or len(df) == 0:
        print("⚠️ WARNING: No data loaded")
        return _no_data_figure(...)
    
    print(f"🔍 DEBUG: Columns: {df.columns.tolist()}")
    # ... rest of processing
```

---

### Tool 2: Local Testing Script

**Create a diagnostic script to test widget data loading:**

```python
#!/usr/bin/env python3
"""diagnose_widget_data.py - Test widget data loading locally"""

from widgets.registry import _load_source_dataframe, compute_range_bounds

# Test tickets
print("=" * 50)
print("Testing TICKETS data loading")
start_dt, end_dt = compute_range_bounds("12w", "tickets")
df = _load_source_dataframe("tickets", start_dt, end_dt, "12w")
if df is not None:
    print(f"✅ Loaded {len(df)} tickets")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Date range: {df['Create date'].min()} to {df['Create date'].max()}")
else:
    print("❌ Failed to load tickets")

# Test chats
print("\n" + "=" * 50)
print("Testing CHATS data loading")
start_dt, end_dt = compute_range_bounds("12w", "chats")
df = _load_source_dataframe("chats", start_dt, end_dt, "12w")
if df is not None:
    print(f"✅ Loaded {len(df)} chats")
    print(f"Columns: {df.columns.tolist()}")
else:
    print("❌ Failed to load chats")
```

**Run it:**
```bash
python diagnose_widget_data.py
```

---

### Tool 3: Cloud Run Log Analysis

**Fetch and analyze Cloud Run logs:**

```bash
# Get recent errors
gcloud logging read "resource.type=cloud_run_revision severity>=ERROR" \
  --limit=50 \
  --format="table(timestamp,jsonPayload.message)"

# Count error types
gcloud logging read "resource.type=cloud_run_revision severity>=ERROR" \
  --limit=1000 \
  --format=json | jq '.[] | .jsonPayload.message' | sort | uniq -c | sort -rn

# Filter specific errors
gcloud logging read "resource.type=cloud_run_revision AND ImportError" \
  --limit=50
```

---

### Tool 4: DataFrame Inspector Function

**Add to widgets/registry.py for debugging:**

```python
def _inspect_dataframe(df, name="DataFrame"):
    """Comprehensive DataFrame inspection for debugging"""
    if df is None:
        print(f"⚠️ {name} is None")
        return
    
    print(f"\n{'=' * 60}")
    print(f"🔍 {name} Inspection")
    print(f"{'=' * 60}")
    print(f"Shape: {df.shape} (rows × columns)")
    print(f"\nColumns ({len(df.columns)}):")
    for col in df.columns:
        dtype = df[col].dtype
        null_count = df[col].isna().sum()
        null_pct = (null_count / len(df) * 100) if len(df) > 0 else 0
        print(f"  - {col:30} {str(dtype):20} {null_count:6} nulls ({null_pct:5.1f}%)")
    
    print(f"\nSample (first 3 rows):")
    print(df.head(3))
    
    # Date columns
    date_cols = df.select_dtypes(include=['datetime64']).columns
    if len(date_cols) > 0:
        print(f"\nDate Ranges:")
        for col in date_cols:
            min_date = df[col].min()
            max_date = df[col].max()
            print(f"  {col}: {min_date} to {max_date}")
    
    print(f"{'=' * 60}\n")
```

---

## Quick Reference: Common Fixes

### Fix Checklist for Widget Issues
- [ ] Data loading: Check Firestore connection and credentials
- [ ] Columns: Verify required columns exist or generate them
- [ ] Filtering: Apply CS agent filtering if agent-related
- [ ] Mapping: Apply pipeline mapping if pipeline-related
- [ ] Deduplication: Remove duplicate records by ID
- [ ] Dates: Ensure timezone consistency and valid dates
- [ ] Debugging: Add print statements at each step

### Fix Checklist for Deployment Issues
- [ ] Dependencies: All packages in requirements.txt with versions
- [ ] Memory: Allocated enough for data processing (2Gi recommended)
- [ ] Environment: All required secrets mounted
- [ ] Logs: Check Cloud Run logs for specific errors
- [ ] Testing: Test locally before deploying

---

## Example: Complete Debugging Session

**Problem:** Widget shows "No data for selected range/params"

**Step 1: Add debug logging**
```python
# In widgets/registry.py:_load_source_dataframe
print(f"🔍 DEBUG: Loading {source} data (range: {range_val})")
df = db.get_tickets(start_date=start_dt, end_date=end_dt)
print(f"🔍 DEBUG: Firestore returned {len(df) if df is not None else 0} records")
```

**Step 2: Deploy and check logs**
```bash
gcloud run deploy --image=... 
gcloud logging read "resource.type=cloud_run_revision" --limit=20
```

**Output shows:**
```
🔍 DEBUG: Loading tickets data (range: 12w)
⚠️ Firestore unavailable: ImportError: No module named 'google.cloud.firestore'
🔍 DEBUG: Firestore returned 0 records
```

**Step 3: Identify root cause**
- Firestore library not imported → Check requirements.txt

**Step 4: Apply fix**
```diff
# requirements.txt
- google-cloud-firestore
+ google-cloud-firestore>=2.11.0
```

**Step 5: Redeploy and verify**
```bash
make deploy
# Check logs again
gcloud logging read "resource.type=cloud_run_revision" --limit=20
```

**Output now shows:**
```
🔍 DEBUG: Loading tickets data (range: 12w)
🔍 DEBUG: Firestore returned 1234 records
✅ Using Firestore tickets data (real-time primary source)
```

**Success!** Widget now displays data.

---

## Related Documentation

- [`.roo/rules-debug/AGENTS.md`](./rules-debug/AGENTS.md) - Widget-specific debug patterns
- [`.roo/rules-code/AGENTS.md`](./rules-code/AGENTS.md) - Code implementation rules
- [`CLOUD_RUN_DEPLOYMENT_GUIDE.md`](../CLOUD_RUN_DEPLOYMENT_GUIDE.md) - Deployment instructions
- [`WIDGET_TESTING_GUIDE.md`](../WIDGET_TESTING_GUIDE.md) - Widget testing procedures