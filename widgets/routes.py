#!/usr/bin/env python3
"""
Widgets Blueprint Routes (Phase 0)
- GET /widgets -> list all registered widgets
- GET /widget/<name> -> HTML page suitable for iframe embedding
- GET /widget/<name>.json -> JSON figure data (fig.to_dict())
- GET /metrics -> HTML metric cards for embedding
"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from datetime import datetime, timedelta
import pytz

from flask import Blueprint, render_template, request, abort, make_response, jsonify
import pandas as pd

from .registry import REGISTRY, get_widget_and_meta, normalize_params
from google_sheets_data_source import get_tickets_data, get_chats_data
from common_utils import create_metric_card, get_dashboard_css
from livechat_ratings_fetcher import get_ratings_data

widgets_bp = Blueprint("widgets", __name__)

def _parse_widget_params(name: str, args) -> Dict[str, Any]:
    """
    Normalize query args according to a widget's declared schema.
    Unknown/invalid values fall back to defaults.
    Theme/width/height are handled by the HTML route, not passed to the builder.
    """
    entry = REGISTRY.get(name)
    if not entry:
        return {}
    meta = entry.get("meta", {})
    schema = meta.get("params", {}) or {}

    # Build raw param dict; ignore common presentation params
    raw = {}
    try:
        raw = args.to_dict(flat=True)
    except Exception:
        try:
            raw = dict(args)  # fallback if already a dict-like
        except Exception:
            raw = {}

    # Remove presentation-only params if present
    for k in ("theme", "width", "height"):
        raw.pop(k, None)

    return normalize_params(raw, schema)

def _apply_widget_headers(response):
    """
    Apply minimal framing/CSP headers for widget responses.
    Global app.after_request also sets these, but we include here for extra safety.
    """
    xfo = os.environ.get("WIDGETS_XFO", "SAMEORIGIN")
    frame_ancestors = os.environ.get("WIDGETS_FRAME_ANCESTORS", "'self' https://*.hubspot.com")
    script_src = os.environ.get(
        "WIDGETS_SCRIPT_SRC",
        "'self' 'unsafe-inline' 'unsafe-eval' https://cdn.plot.ly data: blob:"
    )
    response.headers["X-Frame-Options"] = xfo
    directives = []
    if frame_ancestors:
        directives.append(f"frame-ancestors {frame_ancestors}")
    if script_src:
        directives.append(f"script-src {script_src}")
    if directives:
        response.headers["Content-Security-Policy"] = "; ".join(directives)
    return response


@widgets_bp.route("/widgets", methods=["GET"])
def widgets_index():
    """List all registered widgets with links to HTML/JSON and example params (if provided)."""
    items: List[Dict[str, Any]] = []
    for name, entry in REGISTRY.items():
        meta = entry.get("meta", {}) if isinstance(entry, dict) else {}
        title = meta.get("title", name.replace("_", " ").title())
        base_html = f"/widget/{name}"
        base_json = f"/widget/{name}.json"

        # Build example links if meta["examples"] is present:
        examples_meta = meta.get("examples", []) or []
        example_links: List[Dict[str, str]] = []
        for ex in examples_meta:
            label = ex.get("label", "Example")
            query = (ex.get("query") or "").replace("&", "&")  # sanitize if stored HTML-encoded
            if query and not query.startswith("?"):
                html_url = f"{base_html}?{query}"
                json_url = f"{base_json}?{query}"
            elif query:
                html_url = f"{base_html}{query}"
                json_url = f"{base_json}{query}"
            else:
                html_url = base_html
                json_url = base_json
            example_links.append({"label": label, "html_url": html_url, "json_url": json_url})

        items.append(
            {
                "name": name,
                "title": title,
                "html_url": base_html,
                "json_url": base_json,
                "examples": example_links,
            }
        )

    resp = make_response(render_template("widgets/index.html", widgets=items))
    return _apply_widget_headers(resp)


@widgets_bp.route("/widget/<name>", methods=["GET"])
def render_widget_html(name: str):
    """
    Render a single widget as a minimal HTML snippet suitable for iframe embedding.
    Query params:
      - theme: dark (default) | light
      - width: integer px (optional; defaults to 100% via CSS)
      - height: integer px (optional; default 420)
    """
    # Parse and lightly validate params
    theme = (request.args.get("theme", "dark") or "dark").lower()
    theme = "light" if theme == "light" else "dark"

    width_raw = request.args.get("width")
    height_raw = request.args.get("height")

    width_css = "100%"  # default
    if width_raw:
        try:
            width_css = f"{int(width_raw)}px"
        except (TypeError, ValueError):
            width_css = "100%"

    height_css = "420px"
    if height_raw:
        try:
            height_css = f"{int(height_raw)}px"
        except (TypeError, ValueError):
            height_css = "420px"

    # Resolve widget
    try:
        builder, meta = get_widget_and_meta(name)
    except KeyError:
        abort(404, f"Unknown widget: {name}")

    # Parse chart-specific params per widget schema then build the figure
    chart_params = _parse_widget_params(name, request.args)
    fig = builder(chart_params if chart_params is not None else {})

    # Apply theme at layout level (simple and safe)
    if theme == "light":
        fig.update_layout(template="plotly_white")
    else:
        fig.update_layout(template="plotly_dark")

    # Server-side embed using CDN for plotly
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    # Use interactive template for widgets that need time range buttons
    interactive_widgets = [
        "weekly_response_breakdown",
        "weekday_weekend_distribution",
        "agent_ticket_volume_distribution",
        "agent_response_time_comparison",
        "pipeline_response_time_heatmap",
        "performance_vs_volume",
        "pipeline_distribution_by_agent",
        "historic_weekly_volume",
        "volume_daily_historic",
        "chat_weekly_volume_breakdown",
        "weekly_bot_satisfaction",
        "bot_volume_duration",
        "human_volume_duration"
    ]
    template_name = "widgets/interactive_widget_base.html" if name in interactive_widgets else "widgets/widget_base.html"

    # Render template
    resp = make_response(
        render_template(
            template_name,
            chart_html=chart_html,
            theme=theme,
            width=width_css,
            height=height_css,
            title=meta.get("title", name.replace("_", " ").title()),
        )
    )
    return _apply_widget_headers(resp)


@widgets_bp.route("/widget/<name>.json", methods=["GET"])
def render_widget_json(name: str):
    """
    Return the widget's Plotly figure data as JSON (fig.to_dict()).
    """
    try:
        builder, meta = get_widget_and_meta(name)
    except KeyError:
        abort(404, f"Unknown widget: {name}")

    chart_params = _parse_widget_params(name, request.args)
    fig = builder(chart_params if chart_params is not None else {})
    resp = jsonify(fig.to_dict())
    return _apply_widget_headers(resp)


@widgets_bp.route("/metrics", methods=["GET"])
def render_metrics():
    """
    Render HTML metric cards for embedding.
    Query params:
      - type: tickets | chats | all (default: all)
      - range: 7d | 30d | 90d (default: 90d for tickets, 30d for chats)
      - theme: dark | light (default: dark)
    """
    # Parse query parameters
    metrics_type = request.args.get("type", "all").lower()
    range_param = request.args.get("range", "")
    theme = request.args.get("theme", "dark").lower()
    
    # Validate parameters
    if metrics_type not in ["tickets", "chats", "all"]:
        metrics_type = "all"
    if theme not in ["dark", "light"]:
        theme = "dark"
    
    # Default ranges
    if not range_param:
        range_param = "90d" if metrics_type in ["tickets", "all"] else "30d"
    
    # Parse range parameter
    range_days = 90  # default
    if range_param.endswith("d"):
        try:
            range_days = int(range_param[:-1])
        except ValueError:
            range_days = 90
    elif range_param.endswith("w"):
        try:
            range_days = int(range_param[:-1]) * 7
        except ValueError:
            range_days = 90
    elif range_param == "quarterly" or range_param == "13w":
        range_days = 91  # ~13 weeks (1 quarter)
    elif range_param == "8w":
        range_days = 56  # 8 weeks
    
    # Calculate date range
    eastern = pytz.timezone("US/Eastern")
    end_date = datetime.now(eastern)
    start_date = end_date - timedelta(days=range_days)
    
    # Build metric cards HTML
    cards_html = []
    
    # Format timeframe label
    if range_param in ["13w", "quarterly"]:
        timeframe_label = "Last 13 Weeks"
    elif range_param.endswith("w"):
        weeks = int(range_param[:-1])
        timeframe_label = f"Last {weeks} Weeks"
    elif range_param.endswith("d"):
        days = int(range_param[:-1])
        timeframe_label = f"Last {days} Days"
    else:
        timeframe_label = f"Last {range_days} Days"
    
    try:
        # Tickets metrics
        if metrics_type in ["tickets", "all"]:
            tickets_df = get_tickets_data()
            if tickets_df is not None and len(tickets_df) > 0:
                ticket_cards = _build_ticket_metrics(tickets_df, start_date, end_date, range_days)
                if ticket_cards:
                    cards_html.append(f'<div class="metrics-section"><h2 style="color: #ff6b6b;">📋 Ticket Metrics ({timeframe_label})</h2><div class="metric-grid">{ticket_cards}</div></div>')
        
        # Chat metrics
        if metrics_type in ["chats", "all"]:
            chats_df = get_chats_data()
            if chats_df is not None and len(chats_df) > 0:
                chat_cards = _build_chat_metrics(chats_df, start_date, end_date, range_days)
                if chat_cards:
                    cards_html.append(f'<div class="metrics-section"><h2 style="color: #4ecdc4;">💬 Chat Metrics ({timeframe_label})</h2><div class="metric-grid">{chat_cards}</div></div>')
    
    except Exception as e:
        print(f"Error loading metrics: {e}")
        cards_html.append(f'<div class="section"><p style="color: #ff6b6b;">Error loading metrics: {str(e)}</p></div>')
    
    # Build complete HTML
    css = get_dashboard_css()
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Metrics</title>
    <style>
        {css}
        .metrics-section {{
            margin-bottom: 30px;
        }}
        .metrics-section h2 {{
            margin-bottom: 15px;
        }}
    </style>
</head>
<body>
    {''.join(cards_html) if cards_html else '<div class="section"><p>No metrics available for the selected timeframe.</p></div>'}
</body>
</html>
    """
    
    resp = make_response(html_content)
    return _apply_widget_headers(resp)


def _build_ticket_metrics(df: pd.DataFrame, start_date: datetime, end_date: datetime, range_days: int) -> str:
    """Build ticket metric cards HTML"""
    try:
        # Filter by date range
        if 'Create date' in df.columns:
            df['Create date'] = pd.to_datetime(df['Create date'], errors='coerce')
            mask = (df['Create date'] >= start_date) & (df['Create date'] <= end_date)
            df = df[mask]
        
        if len(df) == 0:
            return ""
        
        # Filter out manager tickets (only support team)
        support_agents = ['Bhushan', 'Girly', 'Nova', 'Francis']
        owner_col = 'Case Owner' if 'Case Owner' in df.columns else 'Ticket owner'
        if owner_col in df.columns:
            df = df[df[owner_col].isin(support_agents)]
        
        # Calculate metrics
        total_tickets = len(df)
        
        # Weekend/weekday split
        weekend_tickets = df['Weekend_Ticket'].sum() if 'Weekend_Ticket' in df.columns else 0
        weekday_tickets = total_tickets - weekend_tickets
        
        # Response time (weekday only, excluding LiveChat)
        if 'Weekend_Ticket' in df.columns and 'Pipeline' in df.columns and 'First Response Time (Hours)' in df.columns:
            weekday_df = df[df['Weekend_Ticket'] == False]
            weekday_non_livechat = weekday_df[weekday_df['Pipeline'] != 'Live Chat']
            median_response = weekday_non_livechat['First Response Time (Hours)'].median()
        else:
            median_response = None
        
        # Daily averages
        daily_avg_total = total_tickets / range_days if range_days > 0 else 0
        daily_avg_weekday = weekday_tickets / range_days if range_days > 0 else 0
        daily_avg_weekend = weekend_tickets / range_days if range_days > 0 else 0
        
        # Build cards
        cards = []
        
        if median_response is not None and pd.notna(median_response):
            cards.append(create_metric_card(
                f"{median_response:.3f}h",
                "⚡ Median Response (Weekday)",
                "satisfaction-card-ultra"
            ))
        
        cards.append(create_metric_card(
            total_tickets,
            f"Total Tickets",
            "transfer-card-ultra",
            f"{daily_avg_total:.1f} per day"
        ))
        
        cards.append(create_metric_card(
            weekday_tickets,
            "Weekday Tickets",
            "satisfaction-card-ultra",
            f"{daily_avg_weekday:.1f} per day"
        ))
        
        cards.append(create_metric_card(
            weekend_tickets,
            "Weekend Tickets",
            "transfer-card-ultra",
            f"{daily_avg_weekend:.1f} per day"
        ))
        
        return ''.join(cards)
    
    except Exception as e:
        print(f"Error building ticket metrics: {e}")
        return ""


def _build_chat_metrics(df: pd.DataFrame, start_date: datetime, end_date: datetime, range_days: int) -> str:
    """Build chat metric cards HTML"""
    try:
        # Filter by date range
        if 'chat_creation_date_adt' in df.columns:
            df['chat_creation_date_adt'] = pd.to_datetime(df['chat_creation_date_adt'], errors='coerce')
            mask = (df['chat_creation_date_adt'] >= start_date) & (df['chat_creation_date_adt'] <= end_date)
            df = df[mask]
        
        if len(df) == 0:
            return ""
        
        # Calculate metrics
        total_chats = len(df)
        daily_avg = total_chats / range_days if range_days > 0 else 0
        
        # Transfer metrics
        if 'bot_transfer' in df.columns:
            total_transfers = df['bot_transfer'].sum()
            transfer_rate = (total_transfers / total_chats * 100) if total_chats > 0 else 0
            bot_only = total_chats - total_transfers
            bot_resolution = (bot_only / total_chats * 100) if total_chats > 0 else 0
        else:
            transfer_rate = 0
            bot_resolution = 0
            total_transfers = 0
        
        # Satisfaction metrics from LiveChat Reports API
        try:
            ratings_data = get_ratings_data(days=range_days)
            if ratings_data and 'records' in ratings_data:
                # Process Reports API data (dictionary format)
                total_good = 0
                total_bad = 0
                for date_str, data in ratings_data['records'].items():
                    total_good += data.get('good', 0)
                    total_bad += data.get('bad', 0)
                
                total_rated = total_good + total_bad
                satisfaction_rate = (total_good / total_rated * 100) if total_rated > 0 else 0
                print(f"✅ Using Reports API satisfaction data: {total_good} good / {total_rated} total = {satisfaction_rate:.1f}%")
            else:
                # Fallback to CSV data if Reports API fails
                print("⚠️ Reports API returned no data, falling back to CSV")
                if 'rating_value' in df.columns and 'has_rating' in df.columns:
                    rated_chats = df[df['has_rating'] == True]
                    if len(rated_chats) > 0:
                        good_ratings = len(rated_chats[rated_chats['rating_value'] == 5])
                        satisfaction_rate = (good_ratings / len(rated_chats) * 100)
                    else:
                        satisfaction_rate = 0
                else:
                    satisfaction_rate = 0
        except Exception as e:
            print(f"❌ Error fetching ratings from Reports API: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to CSV data
            if 'rating_value' in df.columns and 'has_rating' in df.columns:
                rated_chats = df[df['has_rating'] == True]
                if len(rated_chats) > 0:
                    good_ratings = len(rated_chats[rated_chats['rating_value'] == 5])
                    satisfaction_rate = (good_ratings / len(rated_chats) * 100)
                else:
                    satisfaction_rate = 0
            else:
                satisfaction_rate = 0
        
        # Build cards
        cards = []
        
        cards.append(create_metric_card(
            total_chats,
            "Total Chats",
            "transfer-card-ultra",
            f"{daily_avg:.1f} per day"
        ))
        
        cards.append(create_metric_card(
            f"{transfer_rate:.1f}%",
            "Bot Transfer Rate",
            "transfer-card-ultra",
            "Goal: < 30%"
        ))
        
        cards.append(create_metric_card(
            f"{satisfaction_rate:.1f}%",
            "Satisfaction Rate",
            "satisfaction-card-ultra",
            "Goal: > 70%"
        ))
        
        cards.append(create_metric_card(
            f"{bot_resolution:.1f}%",
            "Bot Resolution",
            "satisfaction-card-ultra",
            "Goal: > 70%"
        ))
        
        return ''.join(cards)
    
    except Exception as e:
        print(f"Error building chat metrics: {e}")
        return ""
