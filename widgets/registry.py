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
    Compute timezone-aware [start, end] datetimes from 'range' like '52w', '26w', '12w', '8w', '4w', or 'all'.
    'source' determines timezone:
      - tickets -> US/Eastern
      - chats   -> Canada/Atlantic
    """
    tz = pytz.timezone("US/Eastern") if source == "tickets" else pytz.timezone("Canada/Atlantic")
    now = datetime.now(tz)
    if not range_value or range_value == "all":
        return None, None
    try:
        if range_value.endswith("w"):
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


def _load_source_dataframe(source: str, start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Optional[pd.DataFrame]:
    """
    Load and process data for the given source with enhanced integration.

    Priority:
    1. Google Sheets (primary data source - always up-to-date)
    2. Processed data from main app results directory
    3. Fallback to processing raw CSV files

    Returns the filtered DataFrame (copy) or None on failure.
    """
    # Priority 1: Try Google Sheets (primary source)
    try:
        from google_sheets_data_source import get_sheets_data_source

        sheets_ds = get_sheets_data_source()
        if sheets_ds is not None:
            if source == "tickets":
                df = sheets_ds.get_tickets_filtered(start_date=start_dt, end_date=end_dt)
                if df is not None and not df.empty:
                    print(f"✅ Using Google Sheets {source} data (primary source)")
                    return df.copy()
            elif source == "chats":
                df = sheets_ds.get_chats_filtered(start_date=start_dt, end_date=end_dt)
                if df is not None and not df.empty:
                    print(f"✅ Using Google Sheets {source} data (primary source)")
                    return df.copy()
    except Exception as e:
        print(f"⚠️  Google Sheets unavailable: {e}, falling back to local data")

    # Priority 2: Try processed data from main app
    processed_df = _load_processed_dataframe(source, start_dt, end_dt)
    if processed_df is not None:
        print(f"✅ Using processed {source} data from results directory")
        return processed_df

    # Priority 3: Fallback to raw data processing
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
            print(f"⚙️ Processed raw {source} CSV data (fallback)")
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
            print(f"⚙️ Processed raw {source} CSV data (fallback)")
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

@register("weekly_response_time_trends", title="Weekly Response Time Trends")
def weekly_response_time_trends(params: Dict[str, Any]) -> go.Figure:
    """
    Plot weekly response time trend for either tickets or chats.
    Params:
      - source: tickets|chats
      - stat: median|mean
      - range: all|52w|26w|12w|8w|4w
    """
    meta = REGISTRY["weekly_response_time_trends"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)
    source = p.get("source", "tickets")
    stat = p.get("stat", "median")
    range_val = p.get("range", "12w")

    # Compute date range and load data
    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe(source, start_dt, end_dt)

    y_title = "Response Time (Hours)"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)

    # Prepare weekly aggregation
    try:
        if source == "tickets":
            # Ensure required columns exist
            if "Create date" not in df.columns or "First Response Time (Hours)" not in df.columns:
                return _no_data_figure(meta.get("title"), "Week Starting", y_title)

            # Week start (Monday) naive timestamps
            week_start = df["Create date"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
            values = df["First Response Time (Hours)"].astype(float)
            data = pd.DataFrame({"week_start": week_start, "value": values})
            data = data[data["value"].notna() & (data["value"] > 0)]
        else:  # chats
            if "chat_creation_date_adt" not in df.columns or "first_response_time" not in df.columns:
                return _no_data_figure(meta.get("title"), "Week Starting", y_title)
            week_start = df["chat_creation_date_adt"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
            # Convert to hours (first_response_time expected to be seconds or minutes; treat as seconds -> hours)
            vals_hours = pd.to_numeric(df["first_response_time"], errors="coerce") / 3600.0
            data = pd.DataFrame({"week_start": week_start, "value": vals_hours})
            data = data[data["value"].notna() & (data["value"] > 0)]

        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        agg_func = "median" if stat == "median" else "mean"
        weekly = data.groupby("week_start")["value"].agg(agg_func).reset_index()
        weekly = weekly.sort_values("week_start")

        if len(weekly) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weekly["week_start"],
            y=weekly["value"],
            mode="lines+markers",
            name=f"{stat.title()}",
            line=dict(width=2),
            marker=dict(size=6)
        ))

        title = f"Weekly Response Time Trends ({source.title()}, {stat.title()})"
        fig.update_layout(
            title=title,
            xaxis_title="Week Starting",
            yaxis_title=y_title,
            margin=dict(l=40, r=20, t=50, b=40),
            template="plotly_dark",
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)


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
    df = _load_source_dataframe(source, start_dt, end_dt)

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

# weekly_response_time_trends schema
REGISTRY["weekly_response_time_trends"]["meta"].update({
    "description": "Weekly response time trends using ticket or chat data. Stat toggle median|mean.",
    "params": {
        "source": {"type": "enum", "values": ["tickets", "chats"], "default": "tickets"},
        "stat": {"type": "enum", "values": ["median", "mean"], "default": "median"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Tickets, median, 12w", "query": "source=tickets&stat=median&range=12w"},
        {"label": "Chats, mean, 26w", "query": "source=chats&stat=mean&range=26w"}
    ]
})

# volume_daily_historic schema
REGISTRY["volume_daily_historic"]["meta"].update({
    "description": "Historic daily volume counts for tickets or chats.",
    "params": {
        "source": {"type": "enum", "values": ["tickets", "chats"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "26w"},
        "include_weekends": {"type": "bool", "default": True},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Tickets, 8w, weekdays only", "query": "source=tickets&range=8w&include_weekends=false"},
        {"label": "Chats, 52w", "query": "source=chats&range=52w"}
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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    if df is None or len(df) == 0 or "Weekend_Ticket" not in df.columns:
        return _no_data_figure(meta.get("title"), "Category", "Count")

    try:
        counts = df["Weekend_Ticket"].value_counts()
        labels = ["Weekday" if not k else "Weekend" for k in counts.index]
        values = counts.values

        if len(values) == 0:
            return _no_data_figure(meta.get("title"), "Category", "Count")

        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            hole=0.35,
            marker=dict(colors=["rgba(78,205,196,0.85)", "rgba(255,107,107,0.85)"])
        ))
        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Category", "Count")


REGISTRY["weekday_weekend_distribution"]["meta"].update({
    "description": "Donut chart comparing weekday vs weekend ticket share.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 4w", "query": "range=4w"}
    ]
})

# --------------------------------------------------------------------
# 3) weekly_response_breakdown
# --------------------------------------------------------------------
@register("weekly_response_breakdown", title="Weekly Response Breakdown")
def weekly_response_breakdown(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["weekly_response_breakdown"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    stat = p.get("stat", "median")
    range_val = p.get("range", "all")
    include_weekend_series = bool(p.get("include_weekend_series", False))
    show_trend = bool(p.get("show_trend", True))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    y_title = f"{stat.title()} Response Time (Hours)"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)

    try:
        if "Create date" not in df.columns or "First Response Time (Hours)" not in df.columns or "Weekend_Ticket" not in df.columns:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        # Prepare weekly labels
        week_start = df["Create date"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
        dfw = df.copy()
        dfw["week_start"] = week_start
        vals = _safe_hour_series(dfw["First Response Time (Hours)"])
        dfw = dfw.assign(val=vals)
        dfw = dfw[dfw["val"].notna() & (dfw["val"] > 0)]

        if len(dfw) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        agg = "median" if stat == "median" else "mean"
        weekly_all = dfw.groupby("week_start")["val"].agg(agg).reset_index(name="All")
        weekly_weekday = dfw[dfw["Weekend_Ticket"] == False].groupby("week_start")["val"].agg(agg).reset_index(name="Weekday")
        result = weekly_all.merge(weekly_weekday, on="week_start", how="outer")

        if include_weekend_series:
            weekly_weekend = dfw[dfw["Weekend_Ticket"] == True].groupby("week_start")["val"].agg(agg).reset_index(name="Weekend")
            result = result.merge(weekly_weekend, on="week_start", how="outer")

        result = result.sort_values("week_start").fillna(pd.NA)

        if len(result) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", y_title)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=result["week_start"], y=result["All"], name="All Tickets", marker_color="rgba(78,205,196,0.85)"))
        fig.add_trace(go.Bar(x=result["week_start"], y=result["Weekday"], name="Weekday", marker_color="rgba(255,107,107,0.85)"))

        if include_weekend_series and "Weekend" in result.columns:
            fig.add_trace(go.Bar(x=result["week_start"], y=result["Weekend"], name="Weekend", marker_color="rgba(255,234,167,0.85)"))

        # Trend lines
        if show_trend and len(result) > 1:
            import numpy as np
            x = np.arange(len(result))
            if result["All"].notna().sum() > 1:
                y_all = pd.to_numeric(result["All"], errors="coerce")
                m, b = np.polyfit(x[y_all.notna()], y_all.dropna(), 1)
                fig.add_trace(go.Scatter(x=result["week_start"], y=m * x + b, mode="lines", name="Trend (All)", line=dict(color="rgba(102,126,234,1)", dash="dash")))
            if result["Weekday"].notna().sum() > 1:
                y_wd = pd.to_numeric(result["Weekday"], errors="coerce")
                m, b = np.polyfit(x[y_wd.notna()], y_wd.dropna(), 1)
                fig.add_trace(go.Scatter(x=result["week_start"], y=m * x + b, mode="lines", name="Trend (Weekday)", line=dict(color="rgba(255,107,107,1)", dash="dot")))
            if include_weekend_series and "Weekend" in result.columns and result["Weekend"].notna().sum() > 1:
                y_we = pd.to_numeric(result["Weekend"], errors="coerce")
                m, b = np.polyfit(x[y_we.notna()], y_we.dropna(), 1)
                fig.add_trace(go.Scatter(x=result["week_start"], y=m * x + b, mode="lines", name="Trend (Weekend)", line=dict(color="rgba(255,234,167,1)", dash="dashdot")))

        fig.update_layout(
            title=f"{meta.get('title')} ({stat.title()})",
            xaxis_title="Week Starting",
            yaxis_title=y_title,
            barmode="group",
            margin=dict(l=40, r=20, t=50, b=40),
            template="plotly_dark",
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", y_title)


REGISTRY["weekly_response_breakdown"]["meta"].update({
    "description": "Weekly response-time bars with All vs Weekday vs optional Weekend series, with optional trend lines and stat toggle.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "stat": {"type": "enum", "values": ["median", "mean"], "default": "median"},
        "range": {"type": "enum", "values": ["all", "12w", "8w"], "default": "all"},
        "include_weekend_series": {"type": "bool", "default": False},
        "show_trend": {"type": "bool", "default": True}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "8w, include weekend", "query": "range=8w&include_weekend_series=true"},
        {"label": "Mean with trends off", "query": "stat=mean&show_trend=false"}
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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        # Use weekday tickets per notes
        data = df[df["Weekend_Ticket"] == False].copy() if "Weekend_Ticket" in df.columns else df.copy()
        if agents:
            data = data[data[owner_col].isin(agents)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        counts = data.groupby(owner_col).size().reset_index(name="count").sort_values("count", ascending=False)
        labels = counts[owner_col].tolist()
        values = counts["count"].tolist()

        fig = make_subplots(rows=1, cols=2, column_widths=[0.65, 0.35], specs=[[{"type": "bar"}, {"type": "pie"}]], subplot_titles=("Volume (Bar)", "Share (Pie)"))

        fig.add_trace(go.Bar(x=labels, y=values, marker_color="rgba(78,205,196,0.85)", name="Tickets"), row=1, col=1)
        fig.add_trace(go.Pie(labels=labels, values=values, hole=0.35, name="Share"), row=1, col=2)

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Agent",
            yaxis_title="Tickets",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=60, b=40),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")


REGISTRY["agent_ticket_volume_distribution"]["meta"].update({
    "description": "Agent ticket volumes (bar) with share (pie).",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 26w", "query": "range=26w"},
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
    stat = p.get("stat", "both")  # median|mean|both
    agents = _parse_list(p.get("agents"))
    exclude_pipelines = _parse_list(p.get("exclude_pipelines")) or ["Live Chat "]

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    y_title = "Response Time (Hours)"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", y_title)

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "First Response Time (Hours)" not in df.columns:
            return _no_data_figure(meta.get("title"), "Agent", y_title)

        data = df.copy()
        if exclude_pipelines and "Pipeline" in data.columns:
            data = data[~data["Pipeline"].isin(exclude_pipelines)]
        if agents:
            data = data[data[owner_col].isin(agents)]

        vals = _safe_hour_series(data["First Response Time (Hours)"])
        data = data.assign(val=vals)
        data = data[data["val"].notna() & (data["val"] > 0)]

        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", y_title)

        by_agent = data.groupby(owner_col)["val"].agg(["mean", "median"]).reset_index()
        labels = by_agent[owner_col].tolist()

        fig = go.Figure()
        if stat in ("both", "mean"):
            fig.add_trace(go.Bar(x=labels, y=by_agent["mean"].tolist(), name="Average", marker_color="rgba(102,126,234,0.85)"))
        if stat in ("both", "median"):
            fig.add_trace(go.Bar(x=labels, y=by_agent["median"].tolist(), name="Median", marker_color="rgba(255,107,107,0.85)"))

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Agent",
            yaxis_title=y_title,
            barmode="group",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", y_title)


REGISTRY["agent_response_time_comparison"]["meta"].update({
    "description": "Grouped bars comparing Average vs Median response time per agent (excludes specified pipelines for response durations).",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "stat": {"type": "enum", "values": ["median", "mean", "both"], "default": "both"},
        "agents": {"type": "list[string]", "default": None},
        "exclude_pipelines": {"type": "list[string]", "default": ["Live Chat "]}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Median only", "query": "stat=median"},
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
    series = _parse_list(p.get("series")) or ["total", "bot", "human", "trend"]

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt)

    if df is None or len(df) == 0 or "chat_creation_date_adt" not in df.columns or "agent_type" not in df.columns:
        return _no_data_figure(meta.get("title"), "Week Starting", "Chats")

    try:
        week = df["chat_creation_date_adt"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
        data = df.copy()
        data["week_start"] = week

        weekly_total = data.groupby("week_start").size().reset_index(name="Total")
        weekly_bot = data[data["agent_type"] == "bot"].groupby("week_start").size().reset_index(name="Bot")
        weekly_human = data[data["agent_type"] == "human"].groupby("week_start").size().reset_index(name="Human")

        result = weekly_total.merge(weekly_bot, on="week_start", how="left").merge(weekly_human, on="week_start", how="left").fillna(0)
        result = result.sort_values("week_start")

        if len(result) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", "Chats")

        fig = go.Figure()
        if "total" in series:
            fig.add_trace(go.Bar(x=result["week_start"], y=result["Total"], name="Total", marker_color="rgba(78,205,196,0.85)"))
        if "bot" in series:
            fig.add_trace(go.Bar(x=result["week_start"], y=result["Bot"], name="Bot", marker_color="rgba(162,155,254,0.85)"))
        if "human" in series:
            fig.add_trace(go.Bar(x=result["week_start"], y=result["Human"], name="Human", marker_color="rgba(255,107,107,0.85)"))

        if "trend" in series and len(result) > 1 and "total" in series:
            import numpy as np
            x = np.arange(len(result))
            y = pd.to_numeric(result["Total"], errors="coerce")
            if y.notna().sum() > 1:
                m, b = np.polyfit(x[y.notna()], y.dropna(), 1)
                fig.add_trace(go.Scatter(x=result["week_start"], y=m * x + b, mode="lines", name="Total Trend", line=dict(color="rgba(0,212,170,1)", width=3)))

        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Week Starting",
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
    "description": "Weekly total chats with bot and human breakdown bars and total trend line.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "series": {"type": "list[enum]", "values": ["total", "bot", "human", "trend"], "default": ["total", "bot", "human", "trend"]}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Last 26w, total+trend only", "query": "range=26w&series=total,trend"}
    ]
})

# --------------------------------------------------------------------
# 8) weekly_bot_satisfaction
# --------------------------------------------------------------------
@register("weekly_bot_satisfaction", title="Weekly Bot Satisfaction")
def weekly_bot_satisfaction(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["weekly_bot_satisfaction"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt)

    if df is None or len(df) == 0 or "chat_creation_date_adt" not in df.columns or "agent_type" not in df.columns or "rating_value" not in df.columns or "has_rating" not in df.columns:
        return _no_data_figure(meta.get("title"), "Week Starting", "Satisfaction (%)")

    try:
        rated = df[(df["agent_type"] == "bot") & (df["has_rating"] == True)].copy()
        if len(rated) == 0:
            return _no_data_figure(meta.get("title"), "Week Starting", "Satisfaction (%)")
        rated["week_start"] = rated["chat_creation_date_adt"].dt.tz_localize(None).dt.to_period("W-MON").dt.start_time
        # Convert 1–5 scale to 0–100%
        rated["satisfaction_pct"] = pd.to_numeric(rated["rating_value"], errors="coerce").map(lambda v: None if pd.isna(v) else (v - 1) / 4 * 100)
        weekly = rated.groupby("week_start")["satisfaction_pct"].mean().reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(x=weekly["week_start"], y=weekly["satisfaction_pct"], name="Bot Satisfaction (%)", marker_color="rgba(162,155,254,0.85)"))
        fig.update_layout(
            title=meta.get("title"),
            xaxis_title="Week Starting",
            yaxis_title="Satisfaction Rate (%)",
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=False,
            yaxis=dict(range=[0, 100])
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Week Starting", "Satisfaction (%)")


REGISTRY["weekly_bot_satisfaction"]["meta"].update({
    "description": "Weekly satisfaction rate (%) for bot-handled chats.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "52w", "query": "range=52w"}
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
    bots = _parse_list(p.get("bots"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt)

    if df is None or len(df) == 0 or "agent_type" not in df.columns or "display_agent" not in df.columns or "duration_minutes" not in df.columns or "chat_creation_date_adt" not in df.columns:
        return _no_data_figure(meta.get("title"), "Bot", "Value")

    try:
        data = df[df["agent_type"] == "bot"].copy()
        if bots:
            data = data[data["display_agent"].isin(bots)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Bot", "Value")

        stats = data.groupby("display_agent").agg(total_chats=("display_agent", "size"), avg_duration=("duration_minutes", "mean")).reset_index()
        stats = stats.sort_values("total_chats", ascending=False)
        labels = stats["display_agent"].tolist()

        fig = make_subplots(rows=1, cols=2, subplot_titles=("Volume", "Avg Duration (min)"))
        fig.add_trace(go.Bar(x=labels, y=stats["total_chats"], name="Volume", marker_color="rgba(162,155,254,0.85)"), row=1, col=1)
        fig.add_trace(go.Bar(x=labels, y=stats["avg_duration"], name="Duration", marker_color="rgba(78,205,196,0.85)"), row=1, col=2)
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
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "bots": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
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
    agents = _parse_list(p.get("agents"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt)

    if df is None or len(df) == 0 or "agent_type" not in df.columns or "primary_agent" not in df.columns or "duration_minutes" not in df.columns:
        return _no_data_figure(meta.get("title"), "Agent", "Value")

    try:
        # For simplicity, count by primary agent; secondary contributions may be minimal for this view
        data = df[df["agent_type"] == "human"].copy()
        if agents:
            data = data[data["primary_agent"].isin(agents)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Value")

        stats = data.groupby("primary_agent").agg(total_chats=("primary_agent", "size"), avg_duration=("duration_minutes", "mean")).reset_index()
        stats = stats.sort_values("total_chats", ascending=False)
        labels = stats["primary_agent"].tolist()

        fig = make_subplots(rows=1, cols=2, subplot_titles=("Volume", "Avg Duration (min)"))
        fig.add_trace(go.Bar(x=labels, y=stats["total_chats"], name="Volume", marker_color="rgba(255,107,107,0.85)"), row=1, col=1)
        fig.add_trace(go.Bar(x=labels, y=stats["avg_duration"], name="Duration", marker_color="rgba(253,121,168,0.85)"), row=1, col=2)
        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            margin=dict(l=40, r=20, t=60, b=40),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Value")


REGISTRY["human_volume_duration"]["meta"].update({
    "description": "Side-by-side bars for human chat volumes and average duration per agent.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Filter agents", "query": "agents=Nova,Girly"}
    ]
})

# --------------------------------------------------------------------
# 11) bot_performance_comparison
# --------------------------------------------------------------------
@register("bot_performance_comparison", title="Bot Performance Comparison")
def bot_performance_comparison(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["bot_performance_comparison"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "chats")
    range_val = p.get("range", "12w")
    bots = _parse_list(p.get("bots"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("chats", start_dt, end_dt)

    if df is None or len(df) == 0 or "agent_type" not in df.columns or "display_agent" not in df.columns:
        return _no_data_figure(meta.get("title"), "Bot", "Value")

    try:
        data = df[df["agent_type"] == "bot"].copy()
        if bots:
            data = data[data["display_agent"].isin(bots)]
        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Bot", "Value")

        # Compute stats
        rated = data[data["has_rating"] == True].copy() if "has_rating" in data.columns else data.iloc[0:0].copy()
        # 1–5 -> 0–100%
        if "rating_value" in rated.columns:
            rated["sat_pct"] = pd.to_numeric(rated["rating_value"], errors="coerce").map(lambda v: None if pd.isna(v) else (v - 1) / 4 * 100)
        else:
            rated["sat_pct"] = pd.Series(dtype=float)

        vol = data.groupby("display_agent").size().reset_index(name="total")
        sat = rated.groupby("display_agent")["sat_pct"].mean().reset_index()
        merged = vol.merge(sat, on="display_agent", how="left").fillna({"sat_pct": 0})
        merged = merged.sort_values("total", ascending=False)

        labels = merged["display_agent"].tolist()
        volumes = merged["total"].tolist()
        sats = merged["sat_pct"].tolist()

        fig = make_subplots(rows=1, cols=2, column_widths=[0.65, 0.35], specs=[[{"secondary_y": True}, {"type": "pie"}]], subplot_titles=("Volume vs Satisfaction", "Distribution"))

        # Volume bars
        fig.add_trace(go.Bar(x=labels, y=volumes, name="Volume", marker_color="rgba(162,155,254,0.85)"), row=1, col=1)
        # Satisfaction line on secondary y
        fig.add_trace(go.Scatter(x=labels, y=sats, mode="lines+markers", name="Satisfaction (%)", line=dict(color="rgba(255,234,167,1)", width=3)), row=1, col=1, secondary_y=True)
        # Pie
        fig.add_trace(go.Pie(labels=labels, values=volumes, hole=0.35, name="Share"), row=1, col=2)

        fig.update_yaxes(title_text="Chats", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Satisfaction (%)", row=1, col=1, secondary_y=True, range=[0, 100])
        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            margin=dict(l=40, r=20, t=60, b=40),
            showlegend=False
        )
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Bot", "Value")


REGISTRY["bot_performance_comparison"]["meta"].update({
    "description": "Composite chart – bot volume (bars), satisfaction rate (line, secondary axis), and pie distribution.",
    "params": {
        "source": {"type": "enum", "values": ["chats"], "default": "chats"},
        "range": {"type": "enum", "values": ["all", "52w", "26w", "12w", "8w", "4w"], "default": "12w"},
        "bots": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "Filter bots", "query": "bots=Agent%20Scrape"}
    ]
})

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
    df = _load_source_dataframe("chats", start_dt, end_dt)

    if df is None or len(df) == 0 or "chat_creation_date_adt" not in df.columns:
        return _no_data_figure(meta.get("title"), "Date", "Count")

    try:
        daily = df.copy()
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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

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
@register("performance_vs_volume", title="Agent Performance vs Volume")
def performance_vs_volume(params: Dict[str, Any]) -> go.Figure:
    meta = REGISTRY["performance_vs_volume"]["meta"]
    schema = meta.get("params", {})
    p = normalize_params(params or {}, schema)

    source = p.get("source", "tickets")
    range_val = p.get("range", "12w")
    agents = _parse_list(p.get("agents"))

    start_dt, end_dt = compute_range_bounds(range_val, source)
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", "Value")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "First Response Time (Hours)" not in df.columns:
            return _no_data_figure(meta.get("title"), "Agent", "Value")

        data = df.copy()
        if agents:
            data = data[data[owner_col].isin(agents)]

        vals = _safe_hour_series(data["First Response Time (Hours)"])
        data = data.assign(val=vals)
        data = data[data["val"].notna() & (data["val"] > 0)]

        if len(data) == 0:
            return _no_data_figure(meta.get("title"), "Agent", "Value")

        stats = data.groupby(owner_col).agg(
            median_response=("val", "median"),
            total_tickets=(owner_col, "size"),
        ).reset_index()
        stats = stats.sort_values("total_tickets", ascending=False)
        labels = stats[owner_col].tolist()

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=labels,
                y=stats["median_response"],
                name="Median Response (h)",
                marker_color="rgba(255,107,107,0.85)",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=stats["total_tickets"],
                mode="lines+markers",
                name="Total Tickets",
                line=dict(color="rgba(102,126,234,1)", width=3),
            ),
            secondary_y=True,
        )

        fig.update_layout(
            title=meta.get("title"),
            template="plotly_dark",
            margin=dict(l=40, r=20, t=50, b=40),
            showlegend=True,
        )
        fig.update_xaxes(title_text="Agent")
        fig.update_yaxes(title_text="Median Response (h)", secondary_y=False)
        fig.update_yaxes(title_text="Total Tickets", secondary_y=True)
        return fig
    except Exception:
        return _no_data_figure(meta.get("title"), "Agent", "Value")


REGISTRY["performance_vs_volume"]["meta"].update({
    "description": "Dual-axis chart – median response time (bars) vs total tickets (line) per agent.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "12w", "8w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Agent", "Tickets")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "Pipeline" not in df.columns:
            return _no_data_figure(meta.get("title"), "Agent", "Tickets")

        data = df.copy()
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
    "description": "Stacked bars of ticket counts by pipeline per agent.",
    "params": {
        "source": {"type": "enum", "values": ["tickets"], "default": "tickets"},
        "range": {"type": "enum", "values": ["all", "12w", "8w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "pipelines": {"type": "list[string]", "default": None}
    },
    "examples": [
        {"label": "Default", "query": ""},
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
    df = _load_source_dataframe("tickets", start_dt, end_dt)

    y_title = "Agent"
    if df is None or len(df) == 0:
        return _no_data_figure(meta.get("title"), "Pipeline", "Hours")

    try:
        owner_col = _detect_owner_column(df)
        if owner_col is None or "Pipeline" not in df.columns or "First Response Time (Hours)" not in df.columns:
            return _no_data_figure(meta.get("title"), "Pipeline", "Hours")

        data = df.copy()
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
        "range": {"type": "enum", "values": ["all", "12w", "8w"], "default": "12w"},
        "agents": {"type": "list[string]", "default": None},
        "pipelines": {"type": "list[string]", "default": None},
        "stat": {"type": "enum", "values": ["median"], "default": "median"}
    },
    "examples": [
        {"label": "Default", "query": ""},
        {"label": "8w, subset", "query": "range=8w&agents=Nova,Girly&pipelines=Support,Sales"}
    ]
})