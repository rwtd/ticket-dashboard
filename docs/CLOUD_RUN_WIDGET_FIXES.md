l# Cloud Run Widget Fixes - October 18, 2025

## Issues Identified

### 1. Widgets Showing No Data
**Affected Widgets:**
- `daily_chat_trends_performance`
- `weekly_response_breakdown` (both weekday and weekend views)
- `agent_ticket_volume_distribution`

**Root Cause:** Firestore data is being retrieved but widgets may be missing required columns or have data type mismatches.

### 2. Wrong Agents Showing
**Affected Widgets:**
- `agent_response_time_comparison` - Shows Spencer, Erin (should only show 4 CS agents)
- `pipeline_response_time_heatmap` - Shows Spencer, Erin (should only show 4 CS agents)
- `performance_vs_volume` - Shows Spencer, Richie, "None", Erin (should only show 4 CS agents)
- `pipeline_distribution_by_agent` - Shows Spencer, Richie, "None", Erin (should only show 4 CS agents)

**Root Cause:** Missing agent name normalization and filtering in widgets.

### 3. Pipeline Names Showing IDs
**Affected Widget:**
- `pipeline_response_time_heatmap` - Shows pipeline IDs instead of names

**Root Cause:** Firestore stores pipeline IDs, need to map to display names.

## The 4 CS Agents (Canonical Names)
1. **Nova** (variations: Nora, Nora N)
2. **Girly** (variations: Gillie, Gillie E, Girly E)
3. **Bhushan** (variations: Shan, Shan D)
4. **Francis** (variations: Chris, Chris S)

## Fixes Required

### Fix 1: Add Agent Name Normalization Helper
Add to `widgets/registry.py` after line 617:

```python
def _normalize_agent_name(name: str) -> Optional[str]:
    """
    Normalize agent names to canonical CS agent names.
    Returns None for non-CS agents (Spencer, Erin, Richie, test users, etc.)
    """
    if pd.isna(name) or not name or str(name).lower() in ['none', 'nan', '']:
        return None
    
    name_lower = str(name).lower().strip()
    
    # Filter out non-CS agents
    if any(x in name_lower for x in ['spencer', 'erin', 'richie', 'test', 'admin']):
        return None
    
    # Map to canonical names
    name_mapping = {
        # Nova variations
        'nora': 'Nova',
        'nora n': 'Nova',
        'nova': 'Nova',
        # Girly variations
        'gillie': 'Girly',
        'gillie e': 'Girly',
        'girly': 'Girly',
        'girly e': 'Girly',
        # Bhushan variations
        'shan': 'Bhushan',
        'shan d': 'Bhushan',
        'bhushan': 'Bhushan',
        # Francis variations
        'chris': 'Francis',
        'chris s': 'Francis',
        'francis': 'Francis'
    }
    
    return name_mapping.get(name_lower)


def _filter_to_cs_agents(df: pd.DataFrame, owner_col: str) -> pd.DataFrame:
    """Filter DataFrame to only include the 4 CS agents"""
    if owner_col not in df.columns:
        return df
    
    # Normalize all agent names
    df = df.copy()
    df['_normalized_agent'] = df[owner_col].apply(_normalize_agent_name)
    
    # Filter to only CS agents (non-None normalized names)
    df = df[df['_normalized_agent'].notna()].copy()
    
    # Replace original column with normalized names
    df[owner_col] = df['_normalized_agent']
    df = df.drop(columns=['_normalized_agent'])
    
    return df
```

### Fix 2: Add Pipeline Name Mapping
Add to `widgets/registry.py` after the agent normalization:

```python
def _get_pipeline_display_name(pipeline_id: str) -> str:
    """Map pipeline IDs to display names"""
    if pd.isna(pipeline_id):
        return "Unknown"
    
    pipeline_id_str = str(pipeline_id).strip()
    
    # Common pipeline ID to name mappings
    pipeline_mapping = {
        '0': 'Support',
        '1': 'Sales',
        '2': 'Live Chat',
        '3': 'Technical',
        '4': 'Billing',
        # Add more as needed
    }
    
    return pipeline_mapping.get(pipeline_id_str, pipeline_id_str)


def _normalize_pipeline_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize pipeline IDs to display names"""
    if 'Pipeline' in df.columns:
        df = df.copy()
        df['Pipeline'] = df['Pipeline'].apply(_get_pipeline_display_name)
    return df
```

### Fix 3: Update Affected Widgets

#### 3.1 Fix `agent_response_time_comparison` (line 1131)
Replace lines 1150-1166 with:

```python
data = df.copy()

# CRITICAL: Filter to CS agents only and normalize names
owner_col_temp = owner_col
data = _filter_to_cs_agents(data, owner_col_temp)

if len(data) == 0:
    return _no_data_figure(meta.get("title"), "Agent", y_title)

if exclude_pipelines and "Pipeline" in data.columns:
    data = data[~data["Pipeline"].isin(exclude_pipelines)]
if agents:
    data = data[data[owner_col].isin(agents)]

vals = _safe_hour_series(data["First Response Time (Hours)"])
data = data.assign(val=vals)
data = data[data["val"].notna() & (data["val"] > 0)]
```

#### 3.2 Fix `performance_vs_volume` (line 1948)
Replace lines 1969-1976 with:

```python
data = df.copy()

# CRITICAL: Filter to CS agents only and normalize names
owner_col_temp = owner_col
data = _filter_to_cs_agents(data, owner_col_temp)

if agents:
    data = data[data[owner_col].isin(agents)]

if len(data) == 0:
    return _no_data_figure(meta.get("title"), "Agent", "Tickets")
```

#### 3.3 Fix `pipeline_distribution_by_agent` (line 2040)
Replace lines 2062-2071 with:

```python
data = df.copy()

# Normalize pipeline names
data = _normalize_pipeline_names(data)

# CRITICAL: Filter to CS agents only and normalize names
owner_col_temp = owner_col
data = _filter_to_cs_agents(data, owner_col_temp)

if agents:
    data = data[data[owner_col].isin(agents)]
if pipelines:
    data = data[data["Pipeline"].isin(pipelines)]
if len(data) == 0:
    return _no_data_figure(meta.get("title"), "Agent", "Tickets")
```

#### 3.4 Fix `pipeline_response_time_heatmap` (line 2127)
Replace lines 2151-2159 with:

```python
data = df.copy()

# Normalize pipeline names
data = _normalize_pipeline_names(data)

# CRITICAL: Filter to CS agents only and normalize names
owner_col_temp = owner_col
data = _filter_to_cs_agents(data, owner_col_temp)

if agents:
    data = data[data[owner_col].isin(agents)]
if pipelines:
    data = data[data["Pipeline"].isin(pipelines)]

vals = _safe_hour_series(data["First Response Time (Hours)"])
data = data.assign(val=vals)
data = data[data["val"].notna() & (data["val"] > 0)]
```

#### 3.5 Fix `agent_ticket_volume_distribution` (line 991)
Replace lines 1007-1017 with:

```python
owner_col = _detect_owner_column(df)
if owner_col is None:
    return _no_data_figure(meta.get("title"), "Agent", "Tickets")

# Use weekday tickets per notes
data = df[df["Weekend_Ticket"] == False].copy() if "Weekend_Ticket" in df.columns else df.copy()

# CRITICAL: Filter to CS agents only and normalize names
data = _filter_to_cs_agents(data, owner_col)

if agents:
    data = data[data[owner_col].isin(agents)]
if len(data) == 0:
    return _no_data_figure(meta.get("title"), "Agent", "Tickets")
```

### Fix 4: Debug Missing Data Issues

For widgets showing no data, add debug logging. Check if Firestore data has required columns:

**Required columns for tickets:**
- `Create date` (datetime)
- `First Response Time (Hours)` (numeric)
- `Weekend_Ticket` (boolean)
- `Case Owner` or `Ticket owner` (string)
- `Pipeline` (string)

**Required columns for chats:**
- `chat_creation_date_adt` (datetime)
- `agent_type` (string: 'bot' or 'human')
- `rating_value` (numeric 1-5)
- `bot_transfer` (boolean)
- `duration_minutes` (numeric)

## Testing Checklist

After applying fixes:

1. ✅ `agent_response_time_comparison` - Should show only 4 CS agents
2. ✅ `pipeline_response_time_heatmap` - Should show only 4 CS agents with pipeline names (not IDs)
3. ✅ `performance_vs_volume` - Should show only 4 CS agents, no "None" or test users
4. ✅ `pipeline_distribution_by_agent` - Should show only 4 CS agents with pipeline names
5. ✅ `agent_ticket_volume_distribution` - Should show only 4 CS agents
6. ⚠️ `daily_chat_trends_performance` - Check if data loads (may need column fixes)
7. ⚠️ `weekly_response_breakdown` - Check if data loads for both weekday/weekend views

## Deployment

1. Apply all fixes to `widgets/registry.py`
2. Commit changes
3. Deploy to Cloud Run: `make PROJECT_ID=<project> REGION=<region> all`
4. Test all affected widgets
5. Check Cloud Run logs for any errors

## Pipeline ID Mapping

If pipeline IDs don't match, update the mapping in `_get_pipeline_display_name()`. To find correct mappings, check Firestore data or HubSpot pipeline settings.