#!/usr/bin/env python3
"""
Widgets Registry
================
Phase 1: Real, data-driven widgets with parameter schema and reuse of existing processors.

- REGISTRY maps widget names to callables and metadata
- @register(name, title=...) decorator to register widgets
- get_widget_and_meta(name) helper to retrieve builder and metadata
- Includes demo widget: demo_timeseries (kept from Phase 0)
- Adds real widgets:
  * weekly_response_time_trends
  * volume_daily_historic
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Dict, Tuple, Any, Optional, List
from pathlib import Path

import math
import pandas as pd
import plotly.graph_objects as go
import pytz

# Data processors
from ticket_processor import TicketDataProcessor
from chat_processor import ChatDataProcessor

# Central registry of widgets
# Structure: { name: { "build": callable, "meta": { "title": str, "params": {...}, "examples": [...] } } }
REGISTRY: Dict[str, Dict[str, Any]] = {}


def register(name: str, title: Optional[str] = None) -> Callable[[Callable[[Dict[str, Any]], go.Figure]], Callable[[Dict[str, Any]], go.Figure]]:
    """
    Decorator to register a widget builder function.

    Args:
        name: Unique widget name (used in URL paths)
        title: Optional human-friendly title (defaults to title-cased name)

    Returns:
        The original function, unmodified
    """
    def _decorator(func: Callable[[Dict[str, Any]], go.Figure]) -> Callable[[Dict[str, Any]], go.Figure]:
        meta = {
            "title": title or name.replace("_", " ").title()
        }
        REGISTRY[name] = {
            "build": func,
            "meta": meta,
        }
        return func
    return _decorator


def get_widget_and_meta(name: str) -> Tuple[Callable[[Dict[str, Any]], go.Figure], Dict[str, Any]]:
    """
    Retrieve the registered widget builder and metadata.

    Args:
        name: Registered widget name

    Returns:
        (builder_callable, metadata_dict)

    Raises:
        KeyError if the widget name is not registered
    """
    entry = REGISTRY[name]  # Will raise KeyError if missing
    return entry["build"], entry["meta"]


# --------------------------------------------------------------------
# Param helpers (simple and lightweight by design)
# --------------------------------------------------------------------
_BOOL_TRUE = {"true", "1", "yes", "y", "on"}
_BOOL_FALSE = {"false", "0", "no", "n", "off"}

def coerce_bool(val: Any, default: bool = True) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    return default


def normalize_params(raw: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize and validate raw params against schema.
    Supports:
      - enum with allowed values and default
      - bool with default
    """
    params: Dict[str, Any] = {}
    for key, spec in (schema or {}).items():
        typ = spec.get("type")
        if typ == "enum":
            default = spec.get("default")
            values = set(spec.get("values", []))
            chosen = raw.get(key, default)
            if chosen not in values:
                chosen = default
            params[key] = chosen
        elif typ == "bool":
            default = bool(spec.get("default", True))
            params[key] = coerce_bool(raw.get(key), default)
        else:
            # passthrough
            params[key] = raw.get(key, spec.get("default"))
    return params


def compute_range_bounds(range_value: str, source: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Compute timezone-aware [start, end] datetimes from 'range' like '7d', '52w', '26w', '12w', '8w', '4w', 'ytd', or 'all'.
    'source' determines timezone:
      - tickets -> US/Eastern
      - chats   -> Canada/Atlantic
    
    Note: 'd' suffix means BUSINESS DAYS (weekdays only), not calendar days
    Note: '13w' is special - mapped to quarterly view (4 quarters)
    """
    tz = pytz.timezone("US/Eastern") if source == "tickets" else pytz.timezone("Canada/Atlantic")
    now = datetime.now(tz)
    if not range_value or range_value == "all":
        return None, None
    try:
        if range_value == "ytd":
            # Year to date - from January 1st of current year
            start = tz.localize(datetime(now.year, 1, 1, 0, 0, 0))
            end = now
            return start, end
        elif range_value == "13w":
            # Quarterly view - show 4 quarters (current + 3 previous)
            # Go back to start of quarter from 3 quarters ago
            current_quarter = (now.month - 1) // 3 + 1  # 1-4
            quarters_back = 3
            
            # Calculate start date (beginning of quarter from 3 quarters ago)
            start_quarter = current_quarter - quarters_back
            start_year = now.year
            while start_quarter < 1:
                start_quarter += 4
                start_year -= 1
            
            start_month = (start_quarter - 1) * 3 + 1  # Q1=1, Q2=4, Q3=7, Q4=10
            start = tz.localize(datetime(start_year, start_month, 1, 0, 0, 0))
            end = now
            return start, end
        elif range_value.endswith("d"):
            # Business days (e.g., "7d" for last 7 business days)
            business_days = int(range_value[:-1])
            # Start counting from yesterday (to ensure we get full days of data)
            current = now - timedelta(days=1)
            days_counted = 0
            # Count backwards to get business days
            while days_counted < business_days:
                # Skip weekends (Saturday=5, Sunday=6)
                if current.weekday() < 5:  # Monday=0 through Friday=4
                    days_counted += 1
                    if days_counted == business_days:
                        break
                current = current - timedelta(days=1)
            # Normalize to start of day
            start = tz.localize(current.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)) if current.tzinfo is None else current.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
            return start, end
        elif range_value.endswith("w"):
            weeks = int(range_value[:-1])
            start = now - timedelta(weeks=weeks)
            # normalize to start of day
            start = tz.localize(start.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)) if start.tzinfo is None else start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
            return start, end
        # fallback
        return None, None
    except Exception:
        return None, None


def _no_data_figure(title: str, x_title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin=dict(l=40, r=20, t=50, b=40),
        template="plotly_dark",
        showlegend=False,
        annotations=[
            dict(
                text="No data for selected range/params",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14)
            )
        ]
    )
    return fig


def _find_latest_processed_data(source: str) -> Optional[Path]:
    """
    Find the latest processed data file from the main app's results folder.
    
    Args:
        source: 'tickets' or 'chats'
        
    Returns:
        Path to the latest processed CSV file, or None if not found
    """
    try:
        results_dir = Path("results")
        if not results_dir.exists():
            return None
        
        # Look for the most recent results directory
        result_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        if not result_dirs:
            return None
        
        # Sort by directory name (timestamp format YYYY-MM-DD_HH-MM-SS)
        result_dirs.sort(reverse=True)
        
        # Check recent directories for processed data
        for result_dir in result_dirs[:5]:  # Check last 5 runs
            if source == "tickets":
                processed_file = result_dir / "tickets_transformed.csv"
            else:  # chats
                processed_file = result_dir / "chats_transformed.csv"
            
            if processed_file.exists():
                return processed_file
        
        return None
    except Exception:
        return None


def _load_processed_dataframe(source: str, start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Optional[pd.DataFrame]:
    """
    Load processed data from the main app's results, with date filtering.
    
    Args:
        source: 'tickets' or 'chats'
        start_dt: Optional start datetime for filtering
        end_dt: Optional end datetime for filtering
        
    Returns:
        Filtered DataFrame or None if no processed data found
    """
    try:
        processed_file = _find_latest_processed_data(source)
        if processed_file is None:
            return None
        
        # Load processed data
        df = pd.read_csv(processed_file)
        if len(df) == 0:
            return None
        
        # Apply date filtering if requested
        if start_dt is not None or end_dt is not None:
            if source == "tickets":
                date_col = "Create date"
            else:  # chats
                date_col = "chat_creation_date_adt"
            
            if date_col not in df.columns:
                return df  # Return unfiltered if date column missing
            
            # Convert date column to datetime
            df[date_col] = pd.to_datetime(df[date_col])
            
            # Apply filters
            if start_dt is not None:
                df = df[df[date_col] >= start_dt]
            if end_dt is not None:
                df = df[df[date_col] <= end_dt]
        
        return df.copy()
    except Exception:
        return None


def _load_source_dataframe(source: str, start_dt: Optional[datetime], end_dt: Optional[datetime], range_val: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Load and process data for the given source with enhanced integration and caching.

    Priority:
    1. Cache check (fastest)
    2. Firestore (primary data source - real-time)
    3. Google Sheets (fallback - batch updates)
    4. Processed data from main app results directory
    5. Fallback to processing raw CSV files

    Returns the filtered DataFrame (copy) or None on failure.
    """
    # Generate cache key - include range_val to prevent different ranges from sharing cache
    cache_key = f"data:{source}:{range_val}:{start_dt}:{end_dt}"
    
    # Priority 0: Check cache first
    try:
        from cache_manager import CacheManager
        cache = CacheManager()
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            print(f"✅ Using cached {source} data (fastest)")
            return cached_data
    except Exception as e:
        print(f"⚠️ Cache check failed: {e}")
    
    # Priority 1: Try Firestore (primary real-time source)
    try:
        from firestore_db import FirestoreDatabase
        from ticket_processor import TicketDataProcessor
        
        print(f"🔍 DEBUG: Attempting to load {source} from Firestore (range: {range_val}, start: {start_dt}, end: {end_dt})")
        db = FirestoreDatabase()
        if source == "tickets":
            df = db.get_tickets(start_date=start_dt, end_date=end_dt)
            print(f"🔍 DEBUG: Firestore returned {len(df) if df is not None else 0} ticket records")
            
            if df is not None and not df.empty:
                print(f"🔍 DEBUG: Ticket columns from Firestore: {df.columns.tolist()}")
                
                # Apply pipeline name mapping if needed
                df = _apply_pipeline_mapping(df)
                
                # Recalculate response times since Firestore may have stale calculations
                processor = TicketDataProcessor()
                df = processor._calc_first_response(df)
                
                # Ensure required columns exist for widgets
                df = _ensure_ticket_columns(df)
                
                print(f"✅ Using Firestore {source} data (real-time primary source, response times recalculated)")
                # Cache the result
                try:
                    cache.set(cache_key, df.copy(), ttl=300)
                except:
                    pass
                return df.copy()
            else:
                print(f"⚠️ Firestore returned empty DataFrame for tickets")
        elif source == "chats":
            df = db.get_chats(start_date=start_dt, end_date=end_dt)
            print(f"🔍 DEBUG: Firestore returned {len(df) if df is not None else 0} chat records")
            
            if df is not None and not df.empty:
                print(f"🔍 DEBUG: Chat columns from Firestore: {df.columns.tolist()}")
                
                # CRITICAL: Deduplicate by chat_id to prevent duplicate records
                if 'chat_id' in df.columns:
                    original_count = len(df)
                    df = df.drop_duplicates(subset=['chat_id'], keep='first')
                    if original_count != len(df):
                        print(f"⚠️ Removed {original_count - len(df)} duplicate chat records from Firestore")
                
                # Ensure required columns exist for chat widgets
                df = _ensure_chat_columns(df)
                
                print(f"✅ Using Firestore {source} data (real-time primary source, {len(df)} unique chats)")
                # Cache the result
                try:
                    cache.set(cache_key, df.copy(), ttl=300)
                except:
                    pass
                return df.copy()
            else:
                print(f"⚠️ Firestore returned empty DataFrame for chats")
    except Exception as e:
        print(f"⚠️ Firestore unavailable: {e}, trying Google Sheets fallback")
        import traceback
        traceback.print_exc()
    
    # Priority 2: Try Google Sheets (fallback batch source)
    try:
        from google_sheets_data_source import get_sheets_data_source

        sheets_ds = get_sheets_data_source()
        if sheets_ds is not None:
            if source == "tickets":
                df = sheets_ds.get_tickets_filtered(start_date=start_dt, end_date=end_dt)
                if df is not None and not df.empty:
                    print(f"✅ Using Google Sheets {source} data (batch fallback)")
                    # Cache the result
                    try:
                        cache.set(cache_key, df.copy(), ttl=300)
                    except:
                        pass
                    return df.copy()
            elif source == "chats":
                df = sheets_ds.get_chats_filtered(start_date=start_dt, end_date=end_dt)
                if df is not None and not df.empty:
                    print(f"✅ Using Google Sheets {source} data (batch fallback)")
                    # Cache the result
                    try:
                        cache.set(cache_key, df.copy(), ttl=300)
                    except:
                        pass
                    return df.copy()
    except Exception as e:
        print(f"⚠️ Google Sheets unavailable: {e}, trying local data fallback")

    # Priority 3: Try processed data from main app
    processed_df = _load_processed_dataframe(source, start_dt, end_dt)
    if processed_df is not None:
        print(f"✅ Using processed {source} data from results directory")
        # Cache the result
        try:
            cache.set(cache_key, processed_df, ttl=300)
        except:
            pass
        return processed_df

    # Priority 4: Fallback to raw data processing
    try:
        if source == "tickets":
            data_dir = Path("tickets")
            files = list(data_dir.glob("*.csv"))
            if not files:
                return None
            proc = TicketDataProcessor()
            proc.load_data(files)
            proc.process_data()
            df_filtered, _, _ = proc.filter_date_range(start_dt, end_dt)
            print(f"⚙️ Processed raw {source} CSV data (final fallback)")
            # Cache the result
            try:
                cache.set(cache_key, df_filtered.copy(), ttl=300)
            except:
                pass
            return df_filtered.copy()
        elif source == "chats":
            data_dir = Path("chats")
            files = list(data_dir.glob("*.csv"))
            if not files:
                return None
            proc = ChatDataProcessor()
            proc.load_data(files)
            proc.process_data()
            df_filtered, _, _ = proc.filter_date_range(start_dt, end_dt)
            print(f"⚙️ Processed raw {source} CSV data (final fallback)")
            # Cache the result
            try:
                cache.set(cache_key, df_filtered.copy(), ttl=300)
            except:
                pass
            return df_filtered.copy()
        else:
            return None
    except Exception:
        return None


# --------------------------------------------------------------------
# Demo widget (Phase 0): simple synthetic time series using Plotly
# --------------------------------------------------------------------

@register("demo_timeseries", title="Demo Timeseries")
def demo_timeseries(params: Optional[Dict[str, Any]] = None) -> go.Figure:
    """
    Demo timeseries widget.

    - Generates 30 days of synthetic values
    - Returns a Plotly Figure configured for standalone embedding
    """
    today = datetime.utcnow().date()
    start = today - timedelta(days=29)
    dates = [start + timedelta(days=i) for i in range(30)]
    # Simple synthetic series with a gentle trend + periodic variation
    values = [20 + i * 0.8 + 5 * math.sin(i / 3.0) for i in range(30)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode="lines+markers",
        name="Value",
        line=dict(width=2),
        marker=dict(size=6)
    ))

    fig.update_layout(
        title="Demo Timeseries",
        xaxis_title="Date",
        yaxis_title="Value",
        margin=dict(l=40, r=20, t=50, b=40),
        template="plotly_dark",  # Default; route can override theme
        showlegend=False
    )

    # Height is commonly managed by container CSS; keep figure height flexible
    return fig


# --------------------------------------------------------------------
# Real widget: weekly_response_time_trends
# --------------------------------------------------------------------

# REMOVED: weekly_response_time_trends - replaced by weekly_response_breakdown with view parameter


# --------------------------------------------------------------------
# Real widget: volume_daily_historic
# --------------------------------------------------------------------

@register("volume_daily_historic", title="Historic Daily Volume")
def volume_daily_historic(params: Dict[str, Any]) -> go.Figure:
    """
    Plot daily volume counts over time for either tickets or chats.
    Params:
      - source: tickets|chats
      - range: all|52w|26w|12w|8w|4w
      - include_weekends: bool
    """
    meta = REGISTRY["volume_daily_historic"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)
    source = p.get("source", "tickets")
    range_val = p.get("range", "26w")
    include_weekends = bool(p.get("include_weekends", True))

    # Compute date range and load data
    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe(source, start_dt, end_dt, range_val)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Date", "Count")

    try:
        if source == "tickets":
            if "Create date" not in df.columns:
                return _no_data_figure(meta.get("title"), "Date", "Count")
            date_series = df["Create date"].dt.tz_localize(None).dt.date
        else:
            if "chat_creation_date_adt" not in df.columns:
                return _no_data_figure(meta.get("title"), "Date", "Count")
            date_series = df["chat_creation_date_adt"].dt.tz_localize(None).dt.date

        daily = pd.DataFrame({"day": date_series})
        if not include_weekends:
            # Remove Saturday (5) and Sunday (6)
            weekdays = pd.to_datetime(daily["day"]).dt.weekday
            daily = daily[(weekdays != 5) & (weekdays != 6)]

        if len(daily) == 0:
            return _no_data_figure(meta.get("title"), "Date", "Count")

        counts = daily.groupby("day").size().reset_index(name="count").sort_values("day")

        if len(counts) == 0:
            return _no_data_figure(meta.get("title"), "Date", "Count")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=counts["day"],
            y=counts["count"],
            name="Daily Volume",
            marker_color="rgba(78, 205, 196, 0.8)"
        ))

        title = "Historic Daily Volume"
        details = f"{source.title()}"
        if not include_weekends:
            details += ", Weekdays Only"
        if range_val and range_val != "all":
            details += f", {range_val}"
        fig.update_layout(
            title=f"{title} ({details})",
            xaxis_title="Date",
            yaxis_title="Count",
            margin=dict(l=40, r=20, t=50, b=40),
            template="plotly_dark",
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Date", "Count")


# --------------------------------------------------------------------
# Widget metadata: schema and examples
# --------------------------------------------------------------------

# REMOVED: weekly_response_time_trends metadata

# volume_daily_historic schema
REGISTRY["volume_daily_historic"]["meta"].update({
    "description": "Historic daily volume counts for tickets or chats.",
    "params": {
        "source": {"type": "enum", "values": ["tickets", "chats"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "include_weekends": {"type": "bool", "default": True},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Tickets, 8w, weekdays only", "query": "source=tickets&range=8w&include_weekends=false"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "Chats, YTD", "query": "source=chats&range=ytd"}
    ]
})

# --------------------------------------------------------------------
# Phase 2 widgets and helpers
# --------------------------------------------------------------------

from plotly.subplots import make_subplots  # local import for subplots


def _parse_list(val: Any) -> Optional[List[str]]:
    """
    Lightweight parser for CSV-style list params.
    Accepts:
      - "a,b,c" -> ["a","b","c"]
      - ["a","b"] -> ["a","b"]
    Returns None for empty/invalid.
    """
    if val is None:
        return None
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def _detect_owner_column(df: pd.DataFrame) -> Optional[str]:
    for col in ["Case Owner", "Ticket owner", "Owner", "Assigned Agent"]:
        if col in df.columns:
            return col
    return None


def _safe_hour_series(series: pd.Series) -> pd.Series:
    """Coerce numeric to hours; non-numeric and NaN are dropped later by callers."""
    return pd.to_numeric(series, errors="coerce")


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


def _get_pipeline_display_name(pipeline_name: str) -> str:
    """
    Normalize pipeline names to shorter display names.
    Firestore stores full names like 'Support Pipeline', we want just 'Support'
    """
    if pd.isna(pipeline_name):
        return "Unknown"
    
    name_str = str(pipeline_name).strip()
    
    # Normalize long names to short names
    pipeline_mapping = {
        'Support Pipeline': 'Support',
        'Enterprise and VIP Tickets': 'Enterprise/VIP',
        'Dev Tickets': 'Dev',
        'Live Chat ': 'Live Chat',
        'Support': 'Support',
        # Add more as discovered
    }
    
    return pipeline_mapping.get(name_str, name_str)


def _normalize_pipeline_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize pipeline names to shorter display names"""
    if 'Pipeline' in df.columns:
        df = df.copy()
        df['Pipeline'] = df['Pipeline'].apply(_get_pipeline_display_name)
    return df


def _apply_pipeline_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply HubSpot pipeline ID to name mapping if needed.
    This addresses the issue where widgets show pipeline IDs instead of names.
    """
    if 'Pipeline' not in df.columns:
        print("🔍 DEBUG: _apply_pipeline_mapping - No Pipeline column in dataframe")
        return df
    
    try:
        # Check if Pipeline column contains numeric IDs (needs mapping)
        sample_values = df['Pipeline'].dropna().head(5)
        print(f"🔍 DEBUG: _apply_pipeline_mapping - Sample pipeline values: {sample_values.tolist()}")
        
        if sample_values.empty:
            print("⚠️ DEBUG: _apply_pipeline_mapping - Pipeline column is empty")
            return df
        
        # If we have numeric pipeline IDs, try to map them to names
        if all(str(val).isdigit() for val in sample_values):
            print("⚠️ Pipeline column contains IDs, attempting to map to names...")
            
            # Try to get HubSpot API mapping
            try:
                import os
                from hubspot_fetcher import HubSpotTicketFetcher
                
                api_key = os.environ.get('HUBSPOT_API_KEY')
                print(f"🔍 DEBUG: HUBSPOT_API_KEY present: {bool(api_key)}")
                
                if api_key:
                    fetcher = HubSpotTicketFetcher(api_key)
                    pipeline_mapping = fetcher.fetch_pipelines()
                    print(f"🔍 DEBUG: Pipeline mapping retrieved: {len(pipeline_mapping) if pipeline_mapping else 0} entries")
                    
                    if pipeline_mapping:
                        # Apply mapping
                        df = df.copy()
                        df['Pipeline'] = df['Pipeline'].astype(str).map(pipeline_mapping).fillna(df['Pipeline'])
                        print(f"✅ Mapped {len(pipeline_mapping)} pipeline IDs to names")
                    else:
                        print("⚠️ No pipeline mappings retrieved from HubSpot")
                else:
                    print("⚠️ HUBSPOT_API_KEY not available, using fallback mapping")
                    # Fallback static mapping for common pipelines
                    fallback_mapping = {
                        '95947431': 'SPAM',  # Auto-exclude this one
                        # Add other known mappings here as discovered
                    }
                    df = df.copy()
                    df['Pipeline'] = df['Pipeline'].astype(str).map(fallback_mapping).fillna(df['Pipeline'])
                    print(f"🔍 DEBUG: Applied fallback mapping to {len(df)} rows")
                    
            except Exception as e:
                print(f"⚠️ Failed to apply pipeline mapping: {e}")
                import traceback
                traceback.print_exc()
                # Continue without mapping - better to show IDs than fail
        
        # Apply display name normalization (long names to short names)
        df = _normalize_pipeline_names(df)
        
        # Filter out SPAM pipeline after mapping
        if 'Pipeline' in df.columns:
            df = df[df['Pipeline'] != 'SPAM'].copy()
            
    except Exception as e:
        print(f"⚠️ Error in pipeline mapping: {e}")
    
    return df


def _ensure_ticket_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure required columns exist for ticket widgets with proper defaults.
    This addresses empty chart issues due to missing columns.
    """
    if df.empty:
        print("🔍 DEBUG: _ensure_ticket_columns - DataFrame is empty")
        return df
    
    try:
        print(f"🔍 DEBUG: _ensure_ticket_columns - Starting with {len(df)} records")
        print(f"🔍 DEBUG: Available columns: {df.columns.tolist()}")
        
        df = df.copy()
        
        # Ensure Weekend_Ticket column exists
        if 'Weekend_Ticket' not in df.columns and 'Create date' in df.columns:
            print("🔍 DEBUG: Adding Weekend_Ticket column...")
            from ticket_processor import TicketDataProcessor
            processor = TicketDataProcessor()
            df = processor._add_weekend_flag(df)
            print("✅ Added Weekend_Ticket column for ticket widgets")
        elif 'Weekend_Ticket' not in df.columns:
            print("⚠️ WARNING: Cannot add Weekend_Ticket - 'Create date' column missing")
        
        # Ensure First Response Time (Hours) column exists and is numeric
        if 'First Response Time (Hours)' in df.columns:
            before_count = df['First Response Time (Hours)'].notna().sum()
            df['First Response Time (Hours)'] = pd.to_numeric(df['First Response Time (Hours)'], errors='coerce')
            after_count = df['First Response Time (Hours)'].notna().sum()
            print(f"🔍 DEBUG: Response time conversion: {before_count} -> {after_count} valid values")
        
        # Ensure Create date is datetime
        if 'Create date' in df.columns:
            print(f"🔍 DEBUG: Current timezone: {df['Create date'].dt.tz}")
            df['Create date'] = pd.to_datetime(df['Create date'], errors='coerce')
            # Convert to US/Eastern timezone for consistency
            if df['Create date'].dt.tz is None:
                df['Create date'] = df['Create date'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
                print("🔍 DEBUG: Converted from naive to US/Eastern")
            elif str(df['Create date'].dt.tz) != 'US/Eastern':
                df['Create date'] = df['Create date'].dt.tz_convert('US/Eastern')
                print(f"🔍 DEBUG: Converted from {df['Create date'].dt.tz} to US/Eastern")
        
        print(f"✅ Ensured ticket columns for {len(df)} records")
        
    except Exception as e:
        print(f"⚠️ Error ensuring ticket columns: {e}")
        import traceback
        traceback.print_exc()
    
    return df


def _ensure_chat_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure required columns exist for chat widgets with proper defaults.
    This addresses empty chart issues due to missing columns.
    """
    if df.empty:
        print("🔍 DEBUG: _ensure_chat_columns - DataFrame is empty")
        return df
    
    try:
        print(f"🔍 DEBUG: _ensure_chat_columns - Starting with {len(df)} records")
        print(f"🔍 DEBUG: Available columns: {df.columns.tolist()}")
        
        df = df.copy()
        
        # Ensure chat_creation_date_adt is datetime
        if 'chat_creation_date_adt' in df.columns:
            before_count = df['chat_creation_date_adt'].notna().sum()
            df['chat_creation_date_adt'] = pd.to_datetime(df['chat_creation_date_adt'], errors='coerce')
            after_count = df['chat_creation_date_adt'].notna().sum()
            print(f"🔍 DEBUG: Date conversion: {before_count} -> {after_count} valid dates")
        
        # Ensure rating_value exists and is numeric (for satisfaction widgets)
        if 'rating_value' not in df.columns and 'rate_raw' in df.columns:
            print("🔍 DEBUG: Converting rate_raw to rating_value...")
            # Convert rate_raw ('good'/'bad') to rating_value (5/1)
            df['rating_value'] = df['rate_raw'].apply(
                lambda x: 5 if str(x).lower() == 'good' else (1 if str(x).lower() == 'bad' else None)
            )
            print(f"✅ Added rating_value column from rate_raw ({df['rating_value'].notna().sum()} valid ratings)")
        
        # Ensure has_rating column exists
        if 'has_rating' not in df.columns and 'rating_value' in df.columns:
            df['has_rating'] = df['rating_value'].notna()
            print(f"✅ Added has_rating column ({df['has_rating'].sum()} chats with ratings)")
        
        # Ensure bot_transfer column exists and is boolean
        if 'bot_transfer' in df.columns:
            df['bot_transfer'] = df['bot_transfer'].astype(bool)
            print(f"🔍 DEBUG: bot_transfer: {df['bot_transfer'].sum()} transfers")
        
        # Ensure duration_minutes is numeric
        if 'duration_minutes' in df.columns:
            before_count = df['duration_minutes'].notna().sum()
            df['duration_minutes'] = pd.to_numeric(df['duration_minutes'], errors='coerce')
            after_count = df['duration_minutes'].notna().sum()
            print(f"🔍 DEBUG: Duration conversion: {before_count} -> {after_count} valid values")
        
        # Ensure agent_type column exists (critical for filtering)
        if 'agent_type' not in df.columns:
            print("⚠️ WARNING: agent_type column missing, attempting to infer...")
            # Try to infer from other columns
            if 'display_agent' in df.columns:
                # Simple heuristic: if display_agent contains "AI" or "Bot", it's bot
                df['agent_type'] = df['display_agent'].apply(
                    lambda x: 'bot' if any(term in str(x).lower() for term in ['ai', 'bot', 'wynn']) else 'human'
                )
                bot_count = (df['agent_type'] == 'bot').sum()
                human_count = (df['agent_type'] == 'human').sum()
                print(f"✅ Inferred agent_type from display_agent ({bot_count} bot, {human_count} human)")
        
        print(f"✅ Ensured chat columns for {len(df)} records")
        
    except Exception as e:
        print(f"⚠️ Error ensuring chat columns: {e}")
        import traceback
        traceback.print_exc()
    
    return df


# --------------------------------------------------------------------
# 1) tickets_by_pipeline
# --------------------------------------------------------------------
@register("tickets_by_pipeline", title="Tickets by Pipeline")
def tickets_by_pipeline(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["tickets_by_pipeline"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)
    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    pipelines = _parse_list(p.get("pipelines"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    if df is None or len(df) == 0 or "Pipeline" not in df.columns:
        return _no_data_figure(meta.get("title"), "Pipeline", "Tickets")

    try:
        data = df.copy()
        if pipelines:
            data = data[data["Pipeline"].isin(pipelines)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Pipeline", "Tickets")

        counts = data["Pipeline"].value_counts().sort_values(ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=counts.index.tolist(),
            x=counts.values.tolist(),
            orientation="h",
            marker_color="rgba(102, 126, 234, 0.85)",
            name="Tickets"
        ))
        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Tickets",
            yaxis_title="Pipeline",
            margin=dict(l=140, r=20, t=50, b=40),
            template="plotly_dark",
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Pipeline", "Tickets")


REGISTRY["tickets_by_pipeline"]["meta"].update({
    "description": "Horizontal bar showing ticket counts per Pipeline.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "pipelines": {"type": "list[string]", "default": None},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 8w", "query": "range=8w"},
        {"label": "Filter pipelines", "query": "pipelines=Support,Live%20Chat%20"}
    ]
})

# --------------------------------------------------------------------
# 2) weekday_weekend_distribution
# --------------------------------------------------------------------
@register("weekday_weekend_distribution", title="Weekday vs Weekend Distribution")
def weekday_weekend_distribution(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["weekday_weekend_distribution"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    if df is None or len(df) == 0 or "Weekend_Ticket" not in df.columns:
        return _no_data_figure(meta.get("title"), "Category", "Count")

    try:
        counts = df["Weekend_Ticket"].value_counts()
        labels = ["Weekday" if not k else "Weekend" for k in counts.index]
        values = counts.values

        if len(values) == 0:
            return _no_data_figure(meta.get("title"), "Category", "Count")

        # Calculate timeframe for display
        timeframe_map = {
            "7d": "7 Business Days",
            "8w": "8 Weeks",
            "12w": "12 Weeks",
            "13w": "Quarterly",
            "ytd": "Year to Date",
            "4w": "4 Weeks",
            "26w": "26 Weeks",
            "52w": "52 Weeks",
            "all": "All Time"
        }
        timeframe_label = timeframe_map.get(range_val, "12 Weeks")
        
        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            marker=dict(colors=["rgba(78,205,196,0.95)", "rgba(255,107,107,0.95)"]),
            textfont=dict(size=18, color='white'),  # More prominent labels
            textposition='inside',
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>'
        ))
        fig.update_layout(
            title=dict(
                text=f"{meta.get('title')}<br><sub>{timeframe_label}</sub>",
                font=dict(size=18),
                x=0.5,
                xanchor='center'
            ),
            template="plotly_dark",
            margin=dict(l=40, r=40, t=80, b=40),
            showlegend=True,
            legend=dict(
                font=dict(size=16, color='white'),  # More prominent legend
                orientation='h',
                yanchor='bottom',
                y=-0.15,
                xanchor='center',
                x=0.5
            )
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Category", "Count")


REGISTRY["weekday_weekend_distribution"]["meta"].update({
    "description": "Donut chart comparing weekday vs weekend ticket share.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"}
    ]
})

# --------------------------------------------------------------------
# 3) weekly_response_breakdown
# --------------------------------------------------------------------
@register("weekly_response_breakdown", title="Weekly Response Breakdown")
def weekly_response_breakdown(params: Dict[str, Any]) -> go.Figure:
    """
    Weekly response breakdown with separate scaling for weekday vs weekend.
    Shows ONLY weekday OR weekend at a time to avoid scale conflicts.
    
    Params:
      - view: weekday|weekend (default: weekday)
      - stat: median|mean
      - range: all|ytd|13w|12w|8w
      - show_trend: bool
    """
    meta = REGISTRY["weekly_response_breakdown"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    view = p.get("view", "weekday")  # NEW: weekday or weekend view
    stat = p.get("stat", "median")
    range_val = p.get("range", "12w")
    show_trend = bool(p.get("show_trend", True))

    start_dt, end_dt = compute_range_bounds(range_val, "tickets")
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    y_title = f"{stat.title()} Response Time (Hours)"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)

    try:
        if "Create date" not in df.columns or "First Response Time (Hours)" not in df.columns or "Weekend_Ticket" not in df.columns:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        # Filter to selected view ONLY (weekday OR weekend, never both)
        if view == "weekend":
            df = df[df["Weekend_Ticket"] == True].copy()
            view_label = "Weekend"
            bar_color = "rgba(255, 234, 167, 0.85)"
            trend_color = "rgba(255, 193, 7, 0.9)"
        else:  # weekday (default)
            df = df[df["Weekend_Ticket"] == False].copy()
            view_label = "Weekday"
            bar_color = "rgba(78, 205, 196, 0.85)"
            trend_color = "rgba(0, 212, 170, 0.9)"

        if len(df) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", f"No {view_label} Data")

        # Prepare aggregation - DAILY for 7d range, QUARTERLY for 13w (quarterly button), WEEKLY for others
        if range_val == "13w":
            # Quarterly aggregation (13w = "Quarterly" button)
            dfw = df.copy()
            # Calculate quarter: Q1=Jan-Mar(1-3), Q2=Apr-Jun(4-6), Q3=Jul-Sep(7-9), Q4=Oct-Dec(10-12)
            dfw["quarter"] = dfw["Create date"].dt.quarter
            dfw["year"] = dfw["Create date"].dt.year
            dfw["quarter_label"] = "Q" + dfw["quarter"].astype(str) + " " + dfw["year"].astype(str)
            
            vals = _safe_hour_series(dfw["First Response Time (Hours)"])
            dfw = dfw.assign(val=vals)
            dfw = dfw[dfw["val"].notna() & (dfw["val"] > 0)]

            if len(dfw) == 0:
                return _no_data_figure(meta.get("title"), "Quarter", y_title)

            agg = "median" if stat == "median" else "mean"
            quarterly = dfw.groupby(["year", "quarter", "quarter_label"])[["val"]].agg(agg).reset_index()
            quarterly = quarterly.sort_values(["year", "quarter"])
            quarterly = quarterly.rename(columns={"val": "response_time"})
            
            # Keep only last 4 quarters (current + 3 previous)
            quarterly = quarterly.tail(4)
            
            if len(quarterly) == 0:
                return _no_data_figure(meta.get("title"), "Quarter", y_title)
            
            # Use quarterly data
            time_data = quarterly
            time_col = "quarter_label"
            x_title = "Quarter"
        elif range_val == "7d":
            # Daily aggregation for 7-day view - WEEKDAYS ONLY (no weekend gaps)
            date_col = df["Create date"].dt.tz_localize(None).dt.date
            dfw = df.copy()
            dfw["date"] = date_col
            dfw["weekday"] = pd.to_datetime(dfw["date"]).dt.weekday
            
            # Filter to weekdays only (Monday=0 through Friday=4)
            dfw = dfw[dfw["weekday"] < 5].copy()
            
            vals = _safe_hour_series(dfw["First Response Time (Hours)"])
            dfw = dfw.assign(val=vals)
            dfw = dfw[dfw["val"].notna() & (dfw["val"] > 0)]

            if len(dfw) == 0:
                return _no_data_figure(meta.get("title"), "Date", y_title)

            agg = "median" if stat == "median" else "mean"
            daily = dfw.groupby("date")["val"].agg(agg).reset_index(name="response_time")
            daily = daily.sort_values("date")
            
            if len(daily) == 0:
                return _no_data_figure(meta.get("title"), "Date", y_title)
            
            # Use daily data (weekdays only - no gaps)
            time_data = daily
            time_col = "date"
            x_title = "Date"
        else:
            # Weekly aggregation for other ranges
            week_start = df["Create date"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
            dfw = df.copy()
            dfw["week_start"] = week_start
            vals = _safe_hour_series(dfw["First Response Time (Hours)"])
            dfw = dfw.assign(val=vals)
            dfw = dfw[dfw["val"].notna() & (dfw["val"] > 0)]

            if len(dfw) == 0:
                return _no_data_figure(meta.get("title"), "Week Starting", y_title)

            agg = "median" if stat == "median" else "mean"
            weekly = dfw.groupby("week_start")["val"].agg(agg).reset_index(name="response_time")
            weekly = weekly.sort_values("week_start")

            if len(weekly) == 0:
                return _no_data_figure(meta.get("title"), "Week Starting", y_title)
            
            # Use weekly data
            time_data = weekly
            time_col = "week_start"
            x_title = "Week Starting"

        # Create figure with single view
        fig = go.Figure()
        
        # Add bars for selected view only
        fig.add_trace(go.Bar(
            x=time_data[time_col],
            y=time_data["response_time"],
            name=f"{view_label} {stat.title()}",
            marker_color=bar_color,
            text=[f"{val:.2f}h" for val in time_data["response_time"]],
            textposition='outside'
        ))

        # Add trend line if requested
        if show_trend and len(time_data) > 1:
            import numpy as np
            x_values = np.arange(len(time_data))
            y_values = time_data["response_time"].values
            z = np.polyfit(x_values, y_values, 1)
            trend_line = np.poly1d(z)(x_values)

            fig.add_trace(go.Scatter(
                x=time_data[time_col],
                y=trend_line,
                mode="lines",
                name=f"{view_label} Trend",
                line=dict(color=trend_color, width=3, dash="dot"),
                hovertemplate=f"<b>{view_label} Trend</b><br>{x_title}: %{{x|%Y-%m-%d}}<br>%{{y:.2f}} hours<extra></extra>"
            ))

        # Update layout with view-specific title
        xaxis_config = dict(
            gridcolor='rgba(102, 126, 234, 0.2)',
            showgrid=True
        )
        
        # For 7-day view, use categorical x-axis to prevent weekend gaps
        if range_val == "7d":
            xaxis_config['type'] = 'category'
            xaxis_config['categoryorder'] = 'array'
            xaxis_config['categoryarray'] = [str(d) for d in time_data[time_col]]
        
        # Make Weekend/Weekday SUPER prominent in title with better spacing
        if view == "weekend":
            title_html = f"<b>{meta.get('title')}</b><br><br><span style='font-size:28px; color:#FFC107; line-height:1.6;'>🌅 WEEKEND</span><br>Only ({stat.title()})"
        else:
            title_html = f"<b>{meta.get('title')}</b><br><br><span style='font-size:28px; color:#4ECDC4; line-height:1.6;'>📊 WEEKDAY</span><br>Only ({stat.title()})"
        
        fig.update_layout(
            title=dict(
                text=title_html,
                font=dict(size=16),
                x=0.5,
                xanchor='center'
            ),
            xaxis_title=x_title,
            yaxis_title=y_title,
            margin=dict(l=40, r=20, t=100, b=40),  # Increased top margin for taller title
            template="plotly_dark",
            showlegend=True,
            xaxis=xaxis_config,
            yaxis=dict(gridcolor='rgba(102, 126, 234, 0.2)', showgrid=True)
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)


REGISTRY["weekly_response_breakdown"]["meta"].update({
    "description": "Weekly response-time bars with SEPARATE scaling for weekday vs weekend. Toggle between views to avoid scale conflicts.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "view": {"type": "enum", "values": ["weekday", "weekend"], "default": "weekday"},
        "stat": {"type": "enum", "values": ["median", "mean"], "default": "median"},
        "range": {"type": "enum", "values": ["7d", "all", "ytd", "13w", "12w", "8w"], "default": "12w"},
        "show_trend": {"type": "bool", "default": True}
    },
    "examples": [
        {"label": "Default (Weekday)", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Weekend view", "query": "view=weekend"},
        {"label": "Weekday, 8w range", "query": "view=weekday&range=8w"},
        {"label": "Weekend, mean, no trend", "query": "view=weekend&stat=mean&show_trend=false"}
    ]
})

# --------------------------------------------------------------------
# 4) agent_ticket_volume_distribution
# --------------------------------------------------------------------
@register("agent_ticket_volume_distribution", title="Agent Ticket Volume Distribution")
def agent_ticket_volume_distribution(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["agent_ticket_volume_distribution"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")

    try:
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

        counts = data.groupby(owner_col).size().reset_index(name="count").sort_values("count", ascending=False)
        labels = counts[owner_col].tolist()
        values = counts["count"].tolist()

        # Plotly's default color sequence (same as pie chart)
        plotly_colors = [
            '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
            '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
        ]
        # Assign colors to match between bar and pie
        bar_colors = [plotly_colors[i % len(plotly_colors)] for i in range(len(labels))]

        # Calculate timeframe for display
        if range_val == "7d":
            days_span = 7
            timeframe_label = "Last 7 Business Days"
        elif range_val == "8w":
            days_span = 56
            timeframe_label = "Last 8 Weeks"
        elif range_val == "12w":
            days_span = 84
            timeframe_label = "Last 12 Weeks"
        elif range_val == "13w":
            days_span = 91
            timeframe_label = "Last Quarter"
        elif range_val == "ytd":
            days_span = "YTD"
            timeframe_label = "Year to Date"
        elif range_val == "all":
            days_span = "All"
            timeframe_label = "All Time"
        else:
            days_span = 84
            timeframe_label = "Last 12 Weeks"

        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.65, 0.35],
            specs=[[{"type": "bar"}, {"type": "pie"}]],
            subplot_titles=(
                f"<b>Volume (Bar)</b>",
                f"<b>Share (Pie)</b>"
            )
        )

        # Bar chart with matching colors
        fig.add_trace(go.Bar(
            x=labels,
            y=values,
            marker=dict(color=bar_colors),
            name="Tickets",
            text=[f"{v}" for v in values],
            textposition='outside',
            textfont=dict(size=14, color='white')
        ), row=1, col=1)
        
        # Pie chart with same color sequence
        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            name="Share",
            marker=dict(colors=bar_colors),  # Use same colors as bar chart
            textfont=dict(size=16, color='white'),
            textposition='inside',
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Tickets: %{value}<br>%{percent}<extra></extra>'
        ), row=1, col=2)

        fig.update_layout(
            title=dict(
                text=f"{meta.get('title')}<br><sub>{timeframe_label} (Weekdays Only)</sub>",
                font=dict(size=18),
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Agent",
            yaxis_title="Tickets",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=80, b=40),
            showlegend=False,
            font=dict(size=14)
        )
        
        # Update subplot title fonts
        for annotation in fig['layout']['annotations']:
            annotation['font'] = dict(size=16, color='white')
        
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")


REGISTRY["agent_ticket_volume_distribution"]["meta"].update({
    "description": "Agent ticket volumes (bar) with share (pie).",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "Filter to two agents", "query": "agents=Nova,Girly"}
    ]
})

# --------------------------------------------------------------------
# 5) agent_response_time_comparison
# --------------------------------------------------------------------
@register("agent_response_time_comparison", title="Agent Response Time Comparison")
def agent_response_time_comparison(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["agent_response_time_comparison"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    stat = p.get("stat", "median")  # median only (removed mean/both options)
    agents = _parse_list(p.get("agents"))
    exclude_pipelines = _parse_list(p.get("exclude_pipelines")) or ["Live Chat "]

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    y_title = "Response Time (Hours)"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", y_title)

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "First Response Time (Hours)" not in df.columns:
            return _no_data_figure(meta.get("title"), "Agent", y_title)

        data = df.copy()
        
        # CRITICAL: Filter to CS agents only and normalize names
        data = _filter_to_cs_agents(data, owner_col)
        
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", y_title)
        
        if exclude_pipelines and "Pipeline" in data.columns:
            data = data[~data["Pipeline"].isin(exclude_pipelines)]
        if agents:
            data = data[data[owner_col].isin(agents)]

        vals = _safe_hour_series(data["First Response Time (Hours)"])
        data = data.assign(val=vals)
        data = data[data["val"].notna() & (data["val"] > 0)]

        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", y_title)

        by_agent = data.groupby(owner_col)["val"].agg(["median"]).reset_index()
        labels = by_agent[owner_col].tolist()
        values = by_agent["median"].tolist()

        # Plotly's default color sequence (matches pie charts)
        plotly_colors = [
            '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
            '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
        ]
        
        # Assign colors cycling through the palette
        bar_colors = [plotly_colors[i % len(plotly_colors)] for i in range(len(labels))]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, 
            y=values, 
            name="Median Response Time",
            text=[f"{val:.2f}h" for val in values],  # 2 decimal places
            textposition='outside',
            textfont=dict(size=12, color='white'),
            marker=dict(color=bar_colors)
        ))

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Agent",
            yaxis_title=y_title,
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", y_title)


REGISTRY["agent_response_time_comparison"]["meta"].update({
    "description": "Median response time per agent (excludes specified pipelines for response durations).",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "exclude_pipelines": {"type": "list[string]", "default": ["Live Chat "]}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "Exclude Live Chat and filter agents", "query": "exclude_pipelines=Live%20Chat%20&agents=Nova,Girly"}
    ]
})

# --------------------------------------------------------------------
# 7) chat_weekly_volume_breakdown
# --------------------------------------------------------------------
@register("chat_weekly_volume_breakdown", title="Chat Weekly Volume Breakdown")
def chat_weekly_volume_breakdown(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["chat_weekly_volume_breakdown"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")
    # 7d doesn't make sense for weekly chat data, treat as 8w
    if range_val == "7d":
        range_val = "8w"
    series = _parse_list(p.get("series")) or ["total", "bot", "human", "trend"]

    start_dt, end_dt = compute_range_bounds(range_val, "chats")
    df = _load_source_dataframe("chats", start_dt, end_dt, range_val)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", "Chats")
    
    # Find the date column dynamically (might be chat_creation_date_adt or similar)
    date_col = None
    for col in df.columns:
        if 'chat' in col.lower() and 'date' in col.lower():
            date_col = col
            break
    
    if date_col is None or "agent_type" not in df.columns:
        return _no_data_figure(meta.get("title"), "Week Starting", "Chats")

    try:
        data = df.copy()
        
        # CRITICAL: Deduplicate by chat_id to prevent repeating patterns from duplicate Firestore records
        if 'chat_id' in data.columns:
            original_count = len(data)
            data = data.drop_duplicates(subset=['chat_id'], keep='first')
            deduped_count = len(data)
            if original_count != deduped_count:
                print(f"⚠️ Removed {original_count - deduped_count} duplicate chat records ({original_count} -> {deduped_count})")
        
        # Group by quarter for 13w (quarterly), otherwise by week
        if range_val == "13w":
            # Quarterly grouping
            data["quarter"] = pd.to_datetime(data[date_col]).dt.quarter
            data["year"] = pd.to_datetime(data[date_col]).dt.year
            data["period_label"] = "Q" + data["quarter"].astype(str) + " " + data["year"].astype(str)
            
            quarterly_total = data.groupby(["year", "quarter", "period_label"]).size().reset_index(name="Total")
            quarterly_bot = data[data["agent_type"] == "bot"].groupby(["year", "quarter", "period_label"]).size().reset_index(name="Bot")
            quarterly_human = data[data["agent_type"] == "human"].groupby(["year", "quarter", "period_label"]).size().reset_index(name="Human")
            
            result = quarterly_total.merge(quarterly_bot, on=["year", "quarter", "period_label"], how="left").merge(quarterly_human, on=["year", "quarter", "period_label"], how="left").fillna(0)
            result = result.sort_values(["year", "quarter"])
            # Keep only last 4 quarters
            result = result.tail(4)
            time_col = "period_label"
            x_title = "Quarter"
        else:
            # Weekly grouping
            week = pd.to_datetime(data[date_col]).dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
            data["week_start"] = week
            
            weekly_total = data.groupby("week_start").size().reset_index(name="Total")
            weekly_bot = data[data["agent_type"] == "bot"].groupby("week_start").size().reset_index(name="Bot")
            weekly_human = data[data["agent_type"] == "human"].groupby("week_start").size().reset_index(name="Human")
            
            result = weekly_total.merge(weekly_bot, on="week_start", how="left").merge(weekly_human, on="week_start", how="left").fillna(0)
            result = result.sort_values("week_start")
            time_col = "week_start"
            x_title = "Week Starting"

        if len(result) == 0:
            return _no_data_figure(meta.get("title"), x_title, "Chats")

        fig = go.Figure()
        if "total" in series:
            fig.add_trace(go.Bar(x=result[time_col], y=result["Total"], name="Total", marker_color="rgba(78,205,196,0.85)"))
        if "bot" in series:
            fig.add_trace(go.Bar(x=result[time_col], y=result["Bot"], name="Bot", marker_color="rgba(162,155,254,0.85)"))
        if "human" in series:
            fig.add_trace(go.Bar(x=result[time_col], y=result["Human"], name="Human", marker_color="rgba(255,107,107,0.85)"))

        if "trend" in series and len(result) > 1 and "total" in series:
            import numpy as np
            x = np.arange(len(result))
            y = pd.to_numeric(result["Total"], errors="coerce")
            if y.notna().sum() > 1:
                m, b = np.polyfit(x[y.notna()], y.dropna(), 1)
                fig.add_trace(go.Scatter(x=result[time_col], y=m * x + b, mode="lines", name="Total Trend", line=dict(color="rgba(0,212,170,1)", width=3)))

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title=x_title,
            yaxis_title="Chats",
            barmode="group",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", "Chats")


REGISTRY["chat_weekly_volume_breakdown"]["meta"].update({
    "description": "Weekly/Quarterly total chats with bot and human breakdown bars and total trend line.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "series": {"type": "list[enum]", "values": ["total", "bot", "human", "trend"], "default": ["total", "bot", "human", "trend"]}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly (4 quarters)", "query": "range=13w"},
        {"label": "Year to date", "query": "range=ytd"},
        {"label": "8w, total+trend only", "query": "range=8w&series=total,trend"}
    ]
})

# --------------------------------------------------------------------
# 8) weekly_bot_satisfaction
# --------------------------------------------------------------------
@register("weekly_bot_satisfaction", title="Weekly Bot Satisfaction")
def weekly_bot_satisfaction(params: Dict[str, Any]) -> go.Figure:
    """
    Bot satisfaction using LiveChat Reports API.
    
    The Reports API provides daily aggregates of good/bad ratings.
    - 7d: Shows last 7 days (daily bars)
    - 13w: Shows last 4 quarters (quarterly bars)
    - Other ranges: Weekly bars
    """
    meta = REGISTRY["weekly_bot_satisfaction"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")

    start_dt, end_dt = compute_range_bounds(range_val, source)
    
    if start_dt is None:
        start_dt = datetime.now(pytz.UTC) - timedelta(weeks=12)
    if end_dt is None:
        end_dt = datetime.now(pytz.UTC)

    try:
        # Import the ratings fetcher
        import os
        from livechat_ratings_fetcher import LiveChatRatingsFetcher
        
        # Get credentials
        pat = os.environ.get('LIVECHAT_PAT')
        if not pat:
            print("ERROR: LIVECHAT_PAT environment variable not set")
            return _no_data_figure(meta.get("title"), "Date", "Satisfaction (%)")
        
        if ':' in pat:
            username, password = pat.split(':', 1)
        else:
            username, password = pat, ''
        
        # Fetch ratings from Reports API
        fetcher = LiveChatRatingsFetcher(username, password)
        ratings_data = fetcher.fetch_ratings(
            from_date=start_dt.replace(tzinfo=None),
            to_date=end_dt.replace(tzinfo=None),
            distribution="day"
        )
        
        if not ratings_data or 'records' not in ratings_data:
            print("No ratings data returned from Reports API")
            return _no_data_figure(meta.get("title"), "Date", "Satisfaction (%)")
        
        # Convert daily ratings to DataFrame
        records = ratings_data['records']
        daily_data = []
        for date_str, data in records.items():
            good = data.get('good', 0)
            bad = data.get('bad', 0)
            total = good + bad
            
            if total > 0:
                # Calculate satisfaction rate: good / (good + bad) * 100
                satisfaction_pct = (good / total) * 100
                daily_data.append({
                    'date': pd.to_datetime(date_str),
                    'good': good,
                    'bad': bad,
                    'total': total,
                    'satisfaction_pct': satisfaction_pct
                })
        
        if not daily_data:
            print("No rated chats found in the specified period")
            return _no_data_figure(meta.get("title"), "Date", "Satisfaction (%)")
        
        # Create DataFrame
        df = pd.DataFrame(daily_data)
        df = df.sort_values('date')
        
        # Aggregate based on range_val
        if range_val == "7d":
            # Daily view - last 7 days (already have daily data, just take last 7)
            result = df.tail(7).copy()
            result['period_label'] = result['date'].dt.strftime('%b %d')
            result['total_ratings'] = result['total']  # Add total_ratings column for consistency
            x_col = 'period_label'
            x_title = 'Date'
            title_suffix = '(Last 7 Days)'
        elif range_val == "13w":
            # Quarterly view - last 4 quarters
            df['quarter'] = df['date'].dt.quarter
            df['year'] = df['date'].dt.year
            df['quarter_label'] = 'Q' + df['quarter'].astype(str) + ' ' + df['year'].astype(str)
            
            quarterly = df.groupby(['year', 'quarter', 'quarter_label']).apply(
                lambda x: pd.Series({
                    'satisfaction_pct': (x['good'].sum() / x['total'].sum() * 100) if x['total'].sum() > 0 else 0,
                    'total_ratings': x['total'].sum()
                })
            ).reset_index()
            quarterly = quarterly.sort_values(['year', 'quarter'])
            result = quarterly.tail(4)  # Last 4 quarters
            x_col = 'quarter_label'
            x_title = 'Quarter'
            title_suffix = '(Last 4 Quarters)'
        else:
            # Weekly view (default)
            df['week_start'] = df['date'].dt.to_period('W-MON').dt.start_time
            
            weekly = df.groupby('week_start').apply(
                lambda x: pd.Series({
                    'satisfaction_pct': (x['good'].sum() / x['total'].sum() * 100) if x['total'].sum() > 0 else 0,
                    'total_ratings': x['total'].sum()
                })
            ).reset_index()
            result = weekly
            x_col = 'week_start'
            x_title = 'Week Starting'
            title_suffix = f'({range_val.upper()})'
        
        if len(result) == 0:
            return _no_data_figure(meta.get("title"), x_title, "Satisfaction (%)")
        
        print(f"Successfully created chart with {len(result)} periods of ratings data")
        print(f"Total ratings: {result['total_ratings'].sum() if 'total_ratings' in result.columns else 'N/A'}")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=result[x_col],
            y=result["satisfaction_pct"],
            name="Bot Satisfaction (%)",
            marker_color="rgba(162,155,254,0.85)",
            text=[f"{val:.1f}%" for val in result["satisfaction_pct"]],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Satisfaction: %{y:.1f}%<br><extra></extra>'
        ))
        fig.update_layout(
            title=f"{meta.get('title')} {title_suffix}",
            xaxis_title=x_title,
            yaxis_title="Satisfaction Rate (%)",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=False,
            yaxis=dict(range=[0, 100])
        )
        return fig
    except Exception as e:
        print(f"ERROR in weekly_bot_satisfaction: {e}")
        import traceback
        traceback.print_exc()
        return _no_data_figure(meta.get("title"), "Date", "Satisfaction (%)")


REGISTRY["weekly_bot_satisfaction"]["meta"].update({
    "description": "Bot satisfaction rate - daily (7d), quarterly (13w), or weekly views.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["7d", "all", "52w", "26w", "13w", "12w", "8w", "4w"], "default": "12w"},
    },
    "examples": [
        {"label": "Default (12w)", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Quarterly (4 quarters)", "query": "range=13w"},
        {"label": "52 weeks", "query": "range=52w"}
    ]
})

# --------------------------------------------------------------------
# 9) bot_volume_duration
# --------------------------------------------------------------------
@register("bot_volume_duration", title="Bot Volume & Duration")
def bot_volume_duration(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["bot_volume_duration"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")
    # 7d doesn't make sense for bot volume/duration, treat as 8w
    if range_val == "7d":
        range_val = "8w"
    bots = _parse_list(p.get("bots"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt, range_val)

    if df is None or len(df) == 0 or "agent_type" not in df.columns or "display_agent" not in df.columns or "duration_minutes" not in df.columns or "chat_creation_date_adt" not in df.columns:
        return _no_data_figure(meta.get("title"), "Bot", "Value")

    try:
        # CRITICAL: Deduplicate by chat_id
        if 'chat_id' in df.columns:
            df = df.drop_duplicates(subset=['chat_id'], keep='first')
        
        data = df[df["agent_type"] == "bot"].copy()
        if bots:
            data = data[data["display_agent"].isin(bots)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Bot", "Value")

        stats = data.groupby("display_agent").agg(total_chats=("display_agent", "size"), avg_duration=("duration_minutes", "mean")).reset_index()
        stats = stats.sort_values("total_chats", ascending=False)
        labels = stats["display_agent"].tolist()

        fig = make_subplots(rows=1, cols=2, subplot_titles=("Volume", "Avg Duration (min)"))
        fig.add_trace(go.Bar(
            x=labels, 
            y=stats["total_chats"], 
            name="Volume", 
            marker_color="rgba(162,155,254,0.85)",
            text=[f"{v}" for v in stats["total_chats"]],
            textposition='outside',
            textfont=dict(size=12, color='white')
        ), row=1, col=1)
        fig.add_trace(go.Bar(
            x=labels, 
            y=stats["avg_duration"], 
            name="Duration", 
            marker_color="rgba(78,205,196,0.85)",
            text=[f"{v:.1f}" for v in stats["avg_duration"]],
            textposition='outside',
            textfont=dict(size=12, color='white')
        ), row=1, col=2)
        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            margin=dict(l=40, r=20, t=60, b=40),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Bot", "Value")


REGISTRY["bot_volume_duration"]["meta"].update({
    "description": "Side-by-side bars for bot chat volumes and average duration per bot.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "bots": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "Filter bots", "query": "bots=Wynn%20AI,Agent%20Scrape"}
    ]
})

# --------------------------------------------------------------------
# 10) human_volume_duration
# --------------------------------------------------------------------
@register("human_volume_duration", title="Human Agent Volume & Duration")
def human_volume_duration(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["human_volume_duration"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")
    # 7d doesn't make sense for human volume/duration, treat as 8w
    if range_val == "7d":
        range_val = "8w"
    agents = _parse_list(p.get("agents"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt, range_val)

    print(f"DEBUG human_volume_duration: Loaded {len(df) if df is not None else 0} total chat records for range {range_val}")
    
    if df is None or len(df) == 0:
        print("DEBUG: No data loaded")
        return _no_data_figure(meta.get("title"), "Agent", "Value")
    
    print(f"DEBUG: Columns in df: {df.columns.tolist()}")
    
    if "agent_type" not in df.columns or "primary_agent" not in df.columns or "duration_minutes" not in df.columns:
        print(f"DEBUG: Missing required columns")
        return _no_data_figure(meta.get("title"), "Agent", "Value")

    try:
        # CRITICAL: Deduplicate by chat_id
        if 'chat_id' in df.columns:
            df = df.drop_duplicates(subset=['chat_id'], keep='first')
        
        data = df.copy()
        
        # Name mapping for all variations
        name_mapping = {
            # Girly variations
            "gillie": "Girly",
            "gillie e": "Girly",
            "girly": "Girly",
            "girly e": "Girly",
            # Nova variations
            "nora": "Nova",
            "nora n": "Nova",
            "nova": "Nova",
            # Bhushan variations
            "shan": "Bhushan",
            "shan d": "Bhushan",
            "bhushan": "Bhushan",
            # Francis variations
            "chris": "Francis",
            "chris s": "Francis",
            "francis": "Francis"
        }
        
        # The human agent names are in the 'human_agents' column!
        # This column can contain comma-separated values like "Chris,Gillie" or single values like "Shan"
        if 'human_agents' not in data.columns:
            return _no_data_figure(meta.get("title"), "Agent", "Value")
        
        # Filter to rows that have human agents
        data = data[data['human_agents'].notna() & (data['human_agents'] != '')].copy()
        
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Value")
        
        # Explode the human_agents column (split comma-separated values into separate rows)
        # This way "Chris,Gillie" becomes two rows: one for Chris, one for Gillie
        data['human_agent_list'] = data['human_agents'].str.split(',')
        data = data.explode('human_agent_list')
        data['human_agent_lower'] = data['human_agent_list'].str.lower().str.strip()
        
        # Filter to only our 4 real human agents
        data = data[data['human_agent_lower'].isin(name_mapping.keys())].copy()
        
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Value")
        
        # Map to display names
        data['display_name'] = data['human_agent_lower'].map(name_mapping)
        
        if agents:
            # If filtering by agents, use real names
            data = data[data["display_name"].isin(agents)]
        if len(data) == 0:
            print("DEBUG: No data after filtering")
            return _no_data_figure(meta.get("title"), "Agent", "Value")

        # Fix aggregation - use size() which counts rows per group
        stats = data.groupby("display_name", as_index=False).agg({
            "duration_minutes": ["count", "mean"]
        })
        stats.columns = ["display_name", "total_chats", "avg_duration"]
        stats = stats.sort_values("total_chats", ascending=False)
        print(f"DEBUG: Final stats:\n{stats}")
        labels = stats["display_name"].tolist()

        # Create completely separate charts stacked vertically for independent scaling
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Chat Volume by Agent", "Avg Duration (min) by Agent"),
            vertical_spacing=0.25  # Increased from 0.15 for more breathing room
        )
        
        # Top chart: Volume
        fig.add_trace(go.Bar(
            x=labels,
            y=stats["total_chats"],
            name="Volume",
            marker_color="rgba(255,107,107,0.85)",
            text=[f"{v}" for v in stats["total_chats"]],
            textposition='outside',
            textfont=dict(size=12, color='white')
        ), row=1, col=1)
        
        # Bottom chart: Duration
        fig.add_trace(go.Bar(
            x=labels,
            y=stats["avg_duration"],
            name="Avg Duration",
            marker_color="rgba(253,121,168,0.85)",
            text=[f"{v:.1f}" for v in stats["avg_duration"]],
            textposition='outside',
            textfont=dict(size=12, color='white')
        ), row=2, col=1)
        
        # Set Y-axis labels
        fig.update_yaxes(title_text="Chats", row=1, col=1)
        fig.update_yaxes(title_text="Minutes", row=2, col=1)
        fig.update_xaxes(title_text="Agent", row=2, col=1)
        
        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            height=600,  # Taller to accommodate two charts
            margin=dict(l=40, r=20, t=80, b=40),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Value")


REGISTRY["human_volume_duration"]["meta"].update({
    "description": "Side-by-side bars for human chat volumes and average duration per agent.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "Filter agents", "query": "agents=Nova,Girly"}
    ]
})

# REMOVED: bot_performance_comparison - useless composite chart

# --------------------------------------------------------------------
# 12) daily_chat_trends_performance
# --------------------------------------------------------------------
@register("daily_chat_trends_performance", title="Daily Chat Trends & Performance")
def daily_chat_trends_performance(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["daily_chat_trends_performance"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt, range_val)

    if df is None or len(df) == 0 or "chat_creation_date_adt" not in df.columns:
        return _no_data_figure(meta.get("title"), "Date", "Count")

    try:
        # CRITICAL: Deduplicate by chat_id
        if 'chat_id' in df.columns:
            df = df.drop_duplicates(subset=['chat_id'], keep='first')
        
        daily = df.copy()
        
        # Calculate rating_value from rate_raw if missing (Firestore doesn't have it)
        if 'rating_value' not in daily.columns and 'rate_raw' in daily.columns:
            # rate_raw is 'good' or 'bad' - convert to numeric (5 for good, 1 for bad)
            daily['rating_value'] = daily['rate_raw'].apply(
                lambda x: 5 if str(x).lower() == 'good' else (1 if str(x).lower() == 'bad' else None)
            )
        
        daily["date"] = daily["chat_creation_date_adt"].dt.date
        agg = daily.groupby("date").agg(
            chat_count=("date", "size"),
            avg_satisfaction=("rating_value", "mean"),
            transfers=("bot_transfer", "sum")
        ).reset_index()
        agg["satisfaction_pct"] = (pd.to_numeric(agg["avg_satisfaction"], errors="coerce") * 20).fillna(0.0)
        agg["transfer_rate"] = (pd.to_numeric(agg["transfers"], errors="coerce") / agg["chat_count"]) * 100

        if len(agg) == 0:
            return _no_data_figure(meta.get("title"), "Date", "Count")

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=agg["date"], y=agg["chat_count"], name="Daily Chat Volume", marker_color="rgba(78,205,196,0.85)"), secondary_y=False)
        fig.add_trace(go.Scatter(x=agg["date"], y=agg["satisfaction_pct"], mode="lines+markers", name="Satisfaction (%)", line=dict(color="rgba(255,234,167,1)", width=2)), secondary_y=True)
        fig.add_trace(go.Scatter(x=agg["date"], y=agg["transfer_rate"], mode="lines+markers", name="Transfer Rate (%)", line=dict(color="rgba(255,107,107,1)", width=2, dash="dot")), secondary_y=True)

        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Chats", secondary_y=False)
        fig.update_yaxes(title_text="Percentage (%)", secondary_y=True, range=[0, 100])
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Date", "Count")


REGISTRY["daily_chat_trends_performance"]["meta"].update({
    "description": "Daily chat volume (bars) with satisfaction and transfer-rate lines (secondary axis).",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "8w", "query": "range=8w"}
    ]
})

# --------------------------------------------------------------------
# 13) agent_weekly_response_by_agent
# --------------------------------------------------------------------
@register("agent_weekly_response_by_agent", title="Agent Weekly Response (Per Agent)")
def agent_weekly_response_by_agent(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["agent_weekly_response_by_agent"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))
    stat = p.get("stat", "median")

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    y_title = "Median Response Time (Hours)"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "Create date" not in df.columns or "First Response Time (Hours)" not in df.columns:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        data = df.copy()
        if agents:
            data = data[data[owner_col].isin(agents)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        data["week_start"] = data["Create date"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
        data["val"] = _safe_hour_series(data["First Response Time (Hours)"])
        data = data[data["val"].notna() & (data["val"] > 0)]

        agg = "median"
        grouped = data.groupby(["week_start", owner_col])["val"].agg(agg).reset_index()
        grouped = grouped.sort_values("week_start")

        if len(grouped) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        fig = go.Figure()
        for agent, g in grouped.groupby(owner_col):
            fig.add_trace(go.Scatter(x=g["week_start"], y=g["val"], mode="lines+markers", name=str(agent)))

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Week Starting",
            yaxis_title=y_title,
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)


REGISTRY["agent_weekly_response_by_agent"]["meta"].update({
    "description": "Weekly median response times per agent (multi-line).",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "12w", "8w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "stat": {"type": "enum", "values": ["median"], "default": "median"}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "8w, subset of agents", "query": "range=8w&agents=Nova,Girly"}
    ]
})

# --------------------------------------------------------------------
# 14) agent_weekly_ticket_volume_by_agent
# --------------------------------------------------------------------
@register("agent_weekly_ticket_volume_by_agent", title="Agent Weekly Ticket Volume (Per Agent)")
def agent_weekly_ticket_volume_by_agent(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["agent_weekly_ticket_volume_by_agent"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", "Tickets")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "Create date" not in df.columns:
            return _no_data_figure(meta.get("title"), "Week Starting", "Tickets")

        data = df.copy()
        if agents:
            data = data[data[owner_col].isin(agents)]
        data["week_start"] = data["Create date"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time

        grouped = data.groupby(["week_start", owner_col]).size().reset_index(name="count")
        grouped = grouped.sort_values("week_start")
        if len(grouped) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", "Tickets")

        fig = go.Figure()
        for agent, g in grouped.groupby(owner_col):
            fig.add_trace(go.Scatter(x=g["week_start"], y=g["count"], mode="lines+markers", name=str(agent)))
        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Week Starting",
            yaxis_title="Tickets",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", "Tickets")


REGISTRY["agent_weekly_ticket_volume_by_agent"]["meta"].update({
    "description": "Weekly ticket counts per agent (multi-line).",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "12w", "8w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "All weeks", "query": "range=all"}
    ]
})

# --------------------------------------------------------------------
# 15) performance_vs_volume
# --------------------------------------------------------------------
@register("performance_vs_volume", title="Agent Volume Comparison")
def performance_vs_volume(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["performance_vs_volume"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        data = df.copy()
        
        # CRITICAL: Filter to CS agents only and normalize names
        data = _filter_to_cs_agents(data, owner_col)
        
        if agents:
            data = data[data[owner_col].isin(agents)]

        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        # Simple volume counts by agent
        volume_stats = data.groupby(owner_col).size().reset_index(name='total_tickets')
        volume_stats = volume_stats.sort_values("total_tickets", ascending=False)

        # Use Plotly's default color sequence (matches pie charts and other widgets)
        plotly_colors = [
            '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
            '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
        ]
        n_agents = len(volume_stats)
        colors = [plotly_colors[i % len(plotly_colors)] for i in range(n_agents)]

        labels = volume_stats[owner_col].tolist()
        values = volume_stats['total_tickets'].tolist()

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=values,
            name="Ticket Volume",
            marker=dict(color=colors),
            text=[f"{v}" for v in values],
            textposition='outside',
            textfont=dict(size=12, color='white'),
            hovertemplate='<b>%{x}</b><br>Tickets: %{y}<br><extra></extra>',
        ))

        fig.update_layout(
            title="Agent Volume Comparison",
            xaxis_title="Agent",
            yaxis_title="Total Tickets",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=False,
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")


REGISTRY["performance_vs_volume"]["meta"].update({
    "description": "Agent volume comparison with Plotly colors, ranked by ticket count. Filters out test users.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "8w subset", "query": "range=8w&agents=Nova,Girly"}
    ]
})

# --------------------------------------------------------------------
# 16) pipeline_distribution_by_agent
# --------------------------------------------------------------------
@register("pipeline_distribution_by_agent", title="Pipeline Distribution by Agent")
def pipeline_distribution_by_agent(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["pipeline_distribution_by_agent"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))
    pipelines = _parse_list(p.get("pipelines"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "Pipeline" not in df.columns:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        data = df.copy()
        
        # Normalize pipeline names
        data = _normalize_pipeline_names(data)
        
        # CRITICAL: Filter to CS agents only and normalize names
        data = _filter_to_cs_agents(data, owner_col)
        
        if agents:
            data = data[data[owner_col].isin(agents)]
        if pipelines:
            data = data[data["Pipeline"].isin(pipelines)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        grouped = data.groupby([owner_col, "Pipeline"]).size().reset_index(name="count")
        # Pivot to get pipelines as columns for stacked bars
        pivot = grouped.pivot(index=owner_col, columns="Pipeline", values="count").fillna(0)
        # Sort agents by total tickets desc
        pivot["__total__"] = pivot.sum(axis=1)
        pivot = pivot.sort_values("__total__", ascending=False)
        pipelines_order = [c for c in pivot.columns if c != "__total__"]
        agents_order = pivot.index.tolist()

        fig = go.Figure()
        for i, pipe in enumerate(pipelines_order):
            fig.add_trace(go.Bar(
                x=agents_order,
                y=pivot[pipe].tolist(),
                name=str(pipe),
                marker_color=None  # let plotly choose or customize palette if desired
            ))

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Agent",
            yaxis_title="Tickets",
            barmode="stack",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")


REGISTRY["pipeline_distribution_by_agent"]["meta"].update({
    "description": "Stacked bars of ticket counts by pipeline per agent. Filters out test users.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "pipelines": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "8w filter agents", "query": "range=8w&agents=Nova,Girly"}
    ]
})

# --------------------------------------------------------------------
# 17) pipeline_response_time_heatmap
# --------------------------------------------------------------------
@register("pipeline_response_time_heatmap", title="Response Time Heatmap (Agent × Pipeline)")
def pipeline_response_time_heatmap(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["pipeline_response_time_heatmap"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))
    pipelines = _parse_list(p.get("pipelines"))
    stat = p.get("stat", "median")  # currently only median supported

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)

    y_title = "Agent"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Pipeline", "Hours")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "Pipeline" not in df.columns or "First Response Time (Hours)" not in df.columns:
            return _no_data_figure(meta.get("title"), "Pipeline", "Hours")

        data = df.copy()
        
        # Normalize pipeline names
        data = _normalize_pipeline_names(data)
        
        # CRITICAL: Filter to CS agents only and normalize names
        data = _filter_to_cs_agents(data, owner_col)
        
        if agents:
            data = data[data[owner_col].isin(agents)]
        if pipelines:
            data = data[data["Pipeline"].isin(pipelines)]

        vals = _safe_hour_series(data["First Response Time (Hours)"])
        data = data.assign(val=vals)
        data = data[data["val"].notna() & (data["val"] > 0)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Pipeline", "Hours")

        agg = "median"  # per schema
        table = data.groupby([owner_col, "Pipeline"])["val"].agg(agg).reset_index()
        pivot = table.pivot(index=owner_col, columns="Pipeline", values="val")

        if pivot.empty:
            return _no_data_figure(meta.get("title"), "Pipeline", "Hours")

        # Order agents by overall median response asc, pipelines alphabetical
        pivot = pivot.sort_index(axis=0)
        pivot = pivot.sort_index(axis=1)

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            colorbar=dict(title="Hours"),
            hoverongaps=False
        ))
        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Pipeline",
            yaxis_title="Agent",
            template="plotly_dark",
            margin=dict(l=80, r=20, t=50, b=60),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Pipeline", "Hours")


REGISTRY["pipeline_response_time_heatmap"]["meta"].update({
    "description": "Heatmap of median response time (hours) by agent × pipeline.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "pipelines": {"type": "list[string]", "default": None},
        "stat": {"type": "enum", "values": ["median"], "default": "median"}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "Last 8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "8w, subset", "query": "range=8w&agents=Nova,Girly&pipelines=Support,Sales"}
    ]
})

# Enhanced trend widgets with 3D gradients
# --------------------------------------------------------------------

# REMOVED: weekly_response_trends_weekday and weekly_response_trends_weekend
# Replaced by weekly_response_breakdown with view parameter (weekday/weekend)

@register("historic_weekly_volume", title="Historic Weekly Volume")
def historic_weekly_volume(params: Dict[str, Any]) -> go.Figure:
    """
    Historic weekly ticket volume with time range support.
    
    Params:
      - range: 7d|8w|12w|13w|ytd|all
      - agents: optional list of agents to filter
      - pipelines: optional list of pipelines to filter
    """
    meta = REGISTRY["historic_weekly_volume"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)
    
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))
    pipelines = _parse_list(p.get("pipelines"))
    
    start_dt, end_dt = compute_range_bounds(range_val, "tickets")
    df = _load_source_dataframe("tickets", start_dt, end_dt, range_val)
    
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", "Number of Tickets")
    
    try:
        # Apply filters
        data = df.copy()
        
        if agents:
            owner_col = _detect_owner_column(data)
            if owner_col and owner_col in data.columns:
                data = data[data[owner_col].isin(agents)]
        
        if pipelines and 'Pipeline' in data.columns:
            data = data[data['Pipeline'].isin(pipelines)]
        
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", "Number of Tickets")
        
        # Group by appropriate time period based on range
        if range_val == "7d":
            # Daily grouping for 7 business days
            data['date'] = data['Create date'].dt.date
            data['weekday'] = pd.to_datetime(data['date']).dt.weekday
            # Filter to weekdays only (Monday=0 through Friday=4)
            data = data[data['weekday'] < 5].copy()
            time_counts = data.groupby('date').size().reset_index(name='ticket_count')
            time_counts = time_counts.sort_values('date')
            x_label = 'Date'
            hover_template = '<b>%{x}</b><br>Tickets: %{y}<br><extra></extra>'
            time_col = 'date'
        elif range_val == "13w":
            # Quarterly grouping
            data['quarter'] = data['Create date'].dt.quarter
            data['year'] = data['Create date'].dt.year
            data['quarter_label'] = "Q" + data['quarter'].astype(str) + " " + data['year'].astype(str)
            time_counts = data.groupby(['year', 'quarter', 'quarter_label']).size().reset_index(name='ticket_count')
            time_counts = time_counts.sort_values(['year', 'quarter'])
            # Keep only last 4 quarters
            time_counts = time_counts.tail(4)
            x_label = 'Quarter'
            hover_template = '<b>%{x}</b><br>Tickets: %{y}<br><extra></extra>'
            time_col = 'quarter_label'
        else:
            # Weekly grouping for other ranges
            data['week_start'] = data['Create date'].dt.to_period('W').dt.start_time
            time_counts = data.groupby('week_start').size().reset_index(name='ticket_count')
            time_counts = time_counts.sort_values('week_start')
            x_label = 'Week Starting'
            hover_template = '<b>Week of %{x|%Y-%m-%d}</b><br>Tickets: %{y}<br><extra></extra>'
            time_col = 'week_start'
        
        if time_counts.empty:
            return _no_data_figure(meta.get("title"), x_label, "Number of Tickets")
        
        # Single teal color for all bars
        bar_color = 'rgba(78,205,196,0.85)'
        
        # Create chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=time_counts[time_col],
            y=time_counts['ticket_count'],
            marker=dict(color=bar_color),
            text=[f"{v}" for v in time_counts['ticket_count']],
            textposition='outside',
            textfont=dict(size=12, color='white'),
            hovertemplate=hover_template,
            name='Volume'
        ))
        
        fig.update_layout(
            title=dict(
                text=f'Historic Ticket Volume ({range_val.upper()})',
                font=dict(size=18),
                x=0.5,
                xanchor='center'
            ),
            xaxis=dict(
                title=x_label,
                gridcolor='rgba(102, 126, 234, 0.2)',
                showgrid=True
            ),
            yaxis=dict(
                title='Number of Tickets',
                gridcolor='rgba(102, 126, 234, 0.2)',
                showgrid=True
            ),
            template='plotly_dark',
            height=400,
            margin=dict(l=60, r=40, t=80, b=60),
            showlegend=False
        )
        
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", "Number of Tickets")



# Add metadata for the historic weekly volume widget
REGISTRY["historic_weekly_volume"]["meta"].update({
    "description": "Weekly ticket volume trends with Plotly colors",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["7d", "8w", "12w", "13w", "ytd", "all"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "pipelines": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default (12 weeks)", "query": ""},
        {"label": "Last 7 days", "query": "range=7d"},
        {"label": "8 weeks", "query": "range=8w"},
        {"label": "Quarterly", "query": "range=13w"},
        {"label": "Year to date", "query": "range=ytd"},
        {"label": "All time", "query": "range=all"}
    ]
})