#!/usr/bin/env python3
"""
Common utilities for unified analytics application
Shared functions for date handling, argument parsing, and output management
"""

import argparse
import base64
import os
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Union, Dict, Any
import matplotlib.pyplot as plt
import pandas as pd
import pytz

# Import Plotly for interactive charts
try:
    import plotly.graph_objects as go
    from chart_components import (
        ChartFactory, ChartType, ChartConfig, InteractivityConfig,
        ChartPresets, auto_detect_chart_type, validate_chart_data
    )
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --------------------------------------------------
# Date and Time Utilities
# --------------------------------------------------

def parse_date_string(date_str: str) -> datetime:
    """Convert DDMMYYYY string to datetime object"""
    try:
        return datetime.strptime(date_str, "%d%m%Y")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected DDMMYYYY.")

def validate_monday(date_obj: datetime) -> None:
    """Ensure date is a Monday for weekly analysis"""
    if date_obj.weekday() != 0:
        raise ValueError(
            f"{date_obj:%d/%m/%Y} is not a Monday. Use --week with a Monday."
        )

def get_date_range(args: argparse.Namespace, use_timezone: bool = False) -> Tuple[Optional[datetime], Optional[datetime], str]:
    """
    Get date range based on command line arguments
    
    Args:
        args: Parsed command line arguments
        use_timezone: Whether to apply Eastern timezone (for ticket data)
    
    Returns:
        Tuple of (start_date, end_date, label)
    """
    if use_timezone:
        # CRITICAL: Must use US/Eastern to match ticket_processor.py, NOT Canada/Atlantic!
        eastern = pytz.timezone("US/Eastern")
    
    if args.week:
        start = parse_date_string(args.week)
        validate_monday(start)
        
        if use_timezone:
            # CRITICAL: Start at midnight, not 6AM - matches app.py fix
            start_dt = eastern.localize(start.replace(hour=0, minute=0, second=0))
            end_dt = start_dt + timedelta(days=7, seconds=-1)
        else:
            start_dt = start
            end_dt = start + timedelta(days=6)
        
        label = f"Week of {start:%B %d, %Y}"
        
    elif args.day:
        day = parse_date_string(args.day)
        
        if use_timezone:
            start_dt = eastern.localize(day.replace(hour=0, minute=0, second=0))
            end_dt = eastern.localize(day.replace(hour=23, minute=59, second=59))
        else:
            start_dt = end_dt = day
            
        label = f"Day of {day:%B %d, %Y}"
        
    elif args.custom:
        start_str, end_str = args.custom.split("-")
        start_dt = parse_date_string(start_str)
        end_dt = parse_date_string(end_str)
        
        if end_dt < start_dt:
            raise ValueError("End date must be after start date.")
            
        if use_timezone:
            start_dt = eastern.localize(start_dt.replace(hour=0, minute=0, second=0))
            end_dt = eastern.localize(end_dt.replace(hour=23, minute=59, second=59))
            
        label = f"Custom range {start_dt:%B %d, %Y} – {end_dt:%B %d, %Y}"
        
    else:
        start_dt = end_dt = None
        label = "All data"
    
    return start_dt, end_dt, label

# --------------------------------------------------
# Argument Parsing
# --------------------------------------------------

def create_argument_parser() -> argparse.ArgumentParser:
    """Create unified argument parser"""
    parser = argparse.ArgumentParser(
        description="Unified Analytics Tool - Support Tickets & Chat Data Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unified_analytics.py                           # Auto-detect and analyze all data
  python unified_analytics.py --source tickets         # Analyze only ticket data
  python unified_analytics.py --source chats           # Analyze only chat data
  python unified_analytics.py --week 22072025          # Weekly analysis
  python unified_analytics.py --day 22072025           # Daily analysis
  python unified_analytics.py --custom 15072025-22072025  # Custom date range
  
Data Sources:
  - Place ticket CSV files in: ./tickets/
  - Place chat CSV files in: ./chats/
  - Results saved to: ./results/YYYY-MM-DD_HH-MM-SS/
        """
    )
    
    # Data source selection
    parser.add_argument(
        '--source', 
        choices=['tickets', 'chats', 'both', 'auto'],
        default='auto',
        help='Data source to analyze (default: auto-detect)'
    )
    
    # Date range options (mutually exclusive)
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument('--week', metavar='DDMMYYYY', help='Weekly analysis starting from Monday')
    date_group.add_argument('--day', metavar='DDMMYYYY', help='Daily analysis for specific date')
    date_group.add_argument('--custom', metavar='DDMMYYYY-DDMMYYYY', help='Custom date range')
    
    # Optional features
    parser.add_argument('--include-delayed-table', action='store_true', 
                       help='Include delayed response table in ticket analysis')
    parser.add_argument('--include-industry', action='store_true', 
                       help='Include industry breakdown in chat analysis')
    parser.add_argument('--combined-dashboard', action='store_true',
                       help='Create combined dashboard when analyzing both sources')
    
    # Output options
    parser.add_argument('--output-dir', default='results',
                       help='Output directory for results (default: results)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress non-error output')
    
    # Shift configuration option
    parser.add_argument('--schedule-file', default='config/schedule.yaml',
                        help='Path to YAML schedule configuration file (default: config/schedule.yaml)')
    
    # Google Sheets integration options
    parser.add_argument('--export-to-sheets', action='store_true',
                       help='Export processed data to Google Sheets (requires credentials.json)')
    parser.add_argument('--sheets-id', 
                       help='Existing Google Sheets ID to update (creates new if not provided)')
    parser.add_argument('--credentials-path', default='credentials.json',
                       help='Path to Google API credentials file (default: credentials.json)')
    
    return parser

# --------------------------------------------------
# File Detection and Management
# --------------------------------------------------

def detect_data_sources(base_dir: Path) -> dict:
    """
    Detect available data sources in the directory structure
    
    Returns:
        Dict with 'tickets' and 'chats' keys containing file lists
    """
    sources = {
        'tickets': [],
        'chats': []
    }
    
    # Check for ticket files (both .csv and .processed files)
    tickets_dir = base_dir / "tickets"
    if tickets_dir.exists():
        # Include both regular CSV files and processed files
        ticket_patterns = ["*.csv", "*.csv.processed"]
        for pattern in ticket_patterns:
            sources['tickets'].extend(tickets_dir.glob(pattern))
    
    # Check for chat files
    chats_dir = base_dir / "chats"
    if chats_dir.exists():
        # Look for specific LiveChat file patterns
        chat_patterns = [
            "*agents_performance*.csv",
            "*chat_rating*.csv",
            "*total_chats*.csv",
            "*chat_engagement*.csv",
            "*chat_duration*.csv",
            "*tags_usage*.csv",
            "*prechat*.csv",
            "*chats_report*.csv"
        ]
        
        for pattern in chat_patterns:
            sources['chats'].extend(chats_dir.glob(pattern))
    
    return sources

def create_output_directory(base_dir: Path, output_dir: str = "results") -> Path:
    """Create timestamped output directory"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = base_dir / output_dir / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

# --------------------------------------------------
# Dashboard Utilities
# --------------------------------------------------

def fig_to_html(fig, style_class: str = "chart") -> str:
    """Convert matplotlib figure to HTML img tag"""
    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    uri = base64.b64encode(buf.read()).decode()
    return f'<div class="{style_class}"><img src="data:image/png;base64,{uri}" style="max-width:100%;height:auto;"></div>'

def create_metric_card(value: Union[int, float, str], label: str, color_class: str = "metric-card", goal_text: str = "") -> str:
    """Create HTML metric card with optional goal text"""
    goal_html = f'<div class="metric-goal">{goal_text}</div>' if goal_text else ''
    return f'''
    <div class="{color_class}">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        {goal_html}
    </div>
    '''

def get_dashboard_css() -> str:
    """Get common CSS styles for dashboards optimized for 1920x1024 viewport"""
    return """
    body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:linear-gradient(135deg,#0c0c0c 0%,#1a1a2e 50%,#16213e 100%);margin:0;padding:8px;color:#e0e0e0;min-height:100vh;overflow-y:auto;overflow-x:hidden}
    h1{text-align:center;color:#ffffff;margin-bottom:8px;text-shadow:2px 2px 4px rgba(0,0,0,0.5);font-size:2.0em}
    h2{text-align:center;color:#00d4aa;font-size:1.4em;margin:8px 0 6px 0;text-shadow:1px 1px 2px rgba(0,0,0,0.3)}
    h3{color:#ff6b6b;margin:8px 0 6px 0;font-size:1.2em}
    .section{margin:8px 0;padding:12px;background:linear-gradient(145deg,#1e1e2e,#252538);border-radius:8px;box-shadow:0 4px 8px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.1)}
    .date-range{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);color:#000;padding:4px 12px;border-radius:15px;font-weight:bold;display:inline-block;margin:4px 0;box-shadow:0 2px 4px rgba(0,0,0,0.2);font-size:1.0em}
    table{font-size:12px;margin:0 auto;border-collapse:collapse;box-shadow:0 4px 8px rgba(0,0,0,0.2);background:#2a2a3e;border-radius:6px;overflow:hidden;width:100%}
    th{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:8px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;font-size:11px}
    td{padding:6px 8px;border-bottom:1px solid #404040;color:#e0e0e0;font-size:12px}
    tr:nth-child(even){background-color:rgba(255,255,255,0.02)}
    tr:hover{background-color:rgba(0,212,170,0.1);transition:all 0.2s ease}
    .chart{text-align:center;margin:8px 0;background:rgba(255,255,255,0.05);padding:8px;border-radius:6px;border:1px solid rgba(255,255,255,0.1)}
    .metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:8px 0}
    .metric-card{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:12px;border-radius:8px;text-align:center;box-shadow:0 3px 6px rgba(0,0,0,0.3);transition:all 0.2s ease}
    .metric-card:hover{transform:translateY(-2px);box-shadow:0 6px 12px rgba(0,0,0,0.4)}
    .ticket-card{background:linear-gradient(135deg,#ff6b6b 0%,#ff8e53 100%);color:white;padding:12px;border-radius:8px;text-align:center;box-shadow:0 3px 6px rgba(0,0,0,0.3);transition:all 0.2s ease}
    .ticket-card:hover{transform:translateY(-2px);box-shadow:0 6px 12px rgba(255,107,107,0.4)}
    .chat-card{background:linear-gradient(135deg,#4ecdc4 0%,#44a08d 100%);color:white;padding:18px;border-radius:12px;text-align:center;box-shadow:0 6px 15px rgba(0,0,0,0.4),0 0 20px rgba(78,205,196,0.3);transition:all 0.3s ease;border:2px solid rgba(78,205,196,0.5);transform:scale(1.02)}
    .chat-card:hover{transform:scale(1.05) translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,0.5),0 0 30px rgba(78,205,196,0.5)}
    .chat-card .metric-value{font-size:2.4em;text-shadow:2px 2px 4px rgba(0,0,0,0.5)}
    .chat-card .metric-label{font-size:1.0em;font-weight:bold}
    .weekend-card{background:linear-gradient(135deg,#ffeaa7 0%,#fab1a0 100%);color:#2d3436;padding:12px;border-radius:8px;text-align:center;box-shadow:0 3px 6px rgba(0,0,0,0.3);transition:all 0.2s ease}
    .weekend-card:hover{transform:translateY(-2px);box-shadow:0 6px 12px rgba(255,234,167,0.4)}
    .bot-wynn-card{background:linear-gradient(135deg,#a29bfe 0%,#6c5ce7 100%);color:white;padding:12px;border-radius:8px;text-align:center;box-shadow:0 3px 6px rgba(0,0,0,0.3);transition:all 0.2s ease}
    .bot-wynn-card:hover{transform:translateY(-2px);box-shadow:0 6px 12px rgba(162,155,254,0.4)}
    .bot-support-card{background:linear-gradient(135deg,#fd79a8 0%,#e17055 100%);color:white;padding:12px;border-radius:8px;text-align:center;box-shadow:0 3px 6px rgba(0,0,0,0.3);transition:all 0.2s ease}
    .bot-support-card:hover{transform:translateY(-2px);box-shadow:0 6px 12px rgba(253,121,168,0.4)}
    .transfer-card{background:linear-gradient(135deg,#fd79a8 0%,#e17055 100%);color:white;padding:18px;border-radius:12px;text-align:center;box-shadow:0 6px 15px rgba(0,0,0,0.4),0 0 20px rgba(253,121,168,0.3);transition:all 0.3s ease;border:2px solid rgba(253,121,168,0.5);transform:scale(1.02)}
    .transfer-card:hover{transform:scale(1.05) translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,0.5),0 0 30px rgba(253,121,168,0.5)}
    .transfer-card .metric-value{font-size:2.4em;text-shadow:2px 2px 4px rgba(0,0,0,0.5)}
    .transfer-card .metric-label{font-size:1.0em;font-weight:bold}
    .satisfaction-card{background:linear-gradient(135deg,#a29bfe 0%,#6c5ce7 100%);color:white;padding:18px;border-radius:12px;text-align:center;box-shadow:0 6px 15px rgba(0,0,0,0.4),0 0 20px rgba(162,155,254,0.3);transition:all 0.3s ease;border:2px solid rgba(162,155,254,0.5);transform:scale(1.02)}
    .satisfaction-card:hover{transform:scale(1.05) translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,0.5),0 0 30px rgba(162,155,254,0.5)}
    .satisfaction-card .metric-value{font-size:2.4em;text-shadow:2px 2px 4px rgba(0,0,0,0.5)}
    .satisfaction-card .metric-label{font-size:1.0em;font-weight:bold}
    .success-card{background:linear-gradient(135deg,#00d4aa 0%,#36d1dc 100%);color:white;padding:12px;border-radius:8px;text-align:center;box-shadow:0 3px 6px rgba(0,0,0,0.3);transition:all 0.2s ease}
    .success-card:hover{transform:translateY(-2px);box-shadow:0 6px 12px rgba(0,212,170,0.4)}
    .response-card-prominent{background:linear-gradient(135deg,#00d4aa 0%,#36d1dc 100%);color:white;padding:18px;border-radius:12px;text-align:center;box-shadow:0 6px 15px rgba(0,0,0,0.4),0 0 20px rgba(0,212,170,0.3);transition:all 0.3s ease;border:2px solid rgba(0,212,170,0.5);transform:scale(1.05)}
    .response-card-prominent:hover{transform:scale(1.08) translateY(-3px);box-shadow:0 8px 20px rgba(0,0,0,0.5),0 0 30px rgba(0,212,170,0.5)}
    .response-card-prominent .metric-value{font-size:2.8em;text-shadow:2px 2px 4px rgba(0,0,0,0.5)}
    .response-card-prominent .metric-label{font-size:1.0em;font-weight:bold}
    .chat-card-ultra{background:linear-gradient(135deg,#4ecdc4 0%,#44a08d 100%,#00d4aa 150%);color:white;padding:24px;border-radius:16px;text-align:center;box-shadow:0 8px 25px rgba(0,0,0,0.5),0 0 30px rgba(78,205,196,0.4),inset 0 1px 0 rgba(255,255,255,0.2);transition:all 0.4s ease;border:3px solid rgba(78,205,196,0.7);transform:scale(1.03);position:relative;overflow:hidden}
    .chat-card-ultra:before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:linear-gradient(45deg,transparent,rgba(255,255,255,0.1),transparent);animation:shimmer 3s infinite;pointer-events:none}
    .chat-card-ultra:hover{transform:scale(1.06) translateY(-4px);box-shadow:0 12px 30px rgba(0,0,0,0.6),0 0 40px rgba(78,205,196,0.6)}
    .chat-card-ultra .metric-value{font-size:2.8em;text-shadow:2px 2px 6px rgba(0,0,0,0.6);font-weight:900}
    .chat-card-ultra .metric-label{font-size:1.1em;font-weight:bold;text-transform:uppercase;letter-spacing:1px}
    @keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
    .transfer-card-ultra{background:linear-gradient(135deg,#fd79a8 0%,#e17055 100%,#ff6b6b 150%);color:white;padding:24px;border-radius:16px;text-align:center;box-shadow:0 8px 25px rgba(0,0,0,0.5),0 0 30px rgba(253,121,168,0.4),inset 0 1px 0 rgba(255,255,255,0.2);transition:all 0.4s ease;border:3px solid rgba(253,121,168,0.7);transform:scale(1.03);position:relative;overflow:hidden}
    .transfer-card-ultra:before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:linear-gradient(45deg,transparent,rgba(255,255,255,0.1),transparent);animation:shimmer 3s infinite;pointer-events:none}
    .transfer-card-ultra:hover{transform:scale(1.06) translateY(-4px);box-shadow:0 12px 30px rgba(0,0,0,0.6),0 0 40px rgba(253,121,168,0.6)}
    .transfer-card-ultra .metric-value{font-size:2.8em;text-shadow:2px 2px 6px rgba(0,0,0,0.6);font-weight:900}
    .transfer-card-ultra .metric-label{font-size:1.1em;font-weight:bold;text-transform:uppercase;letter-spacing:1px}
    .satisfaction-card-ultra{background:linear-gradient(135deg,#a29bfe 0%,#6c5ce7 100%,#667eea 150%);color:white;padding:24px;border-radius:16px;text-align:center;box-shadow:0 8px 25px rgba(0,0,0,0.5),0 0 30px rgba(162,155,254,0.4),inset 0 1px 0 rgba(255,255,255,0.2);transition:all 0.4s ease;border:3px solid rgba(162,155,254,0.7);transform:scale(1.03);position:relative;overflow:hidden}
    .satisfaction-card-ultra:before{content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:linear-gradient(45deg,transparent,rgba(255,255,255,0.1),transparent);animation:shimmer 3s infinite;pointer-events:none}
    .satisfaction-card-ultra:hover{transform:scale(1.06) translateY(-4px);box-shadow:0 12px 30px rgba(0,0,0,0.6),0 0 40px rgba(162,155,254,0.6)}
    .satisfaction-card-ultra .metric-value{font-size:2.8em;text-shadow:2px 2px 6px rgba(0,0,0,0.6);font-weight:900}
    .satisfaction-card-ultra .metric-label{font-size:1.1em;font-weight:bold;text-transform:uppercase;letter-spacing:1px}
    .metric-value{font-size:2.0em;font-weight:bold;margin:6px 0;text-shadow:1px 1px 2px rgba(0,0,0,0.3)}
    .metric-label{font-size:0.9em;opacity:0.9;text-transform:uppercase;letter-spacing:0.5px}
    .metric-goal{font-size:0.8em;opacity:0.8;font-style:italic;margin-top:4px;color:rgba(255,255,255,0.7)}
    .data-source-badge{display:inline-block;padding:4px 12px;border-radius:15px;font-size:0.9em;margin:0 3px;font-weight:bold;text-transform:uppercase;letter-spacing:0.5px;box-shadow:0 2px 4px rgba(0,0,0,0.2)}
    .ticket-badge{background:linear-gradient(45deg,#ff6b6b,#ff8e53);color:white}
    .chat-badge{background:linear-gradient(45deg,#4ecdc4,#44a08d);color:white}
    .combined-badge{background:linear-gradient(45deg,#ff6b6b,#4ecdc4);color:white}
    .production-badge{background:linear-gradient(45deg,#00d4aa,#667eea);color:white}
    .trend-section{background:linear-gradient(145deg,#2d3436,#636e72);border-radius:8px;padding:12px;margin:8px 0;border:2px solid rgba(0,212,170,0.3)}
    .breakdown-table{width:100%;max-width:100%}
    .interactive-chart{background:rgba(255,255,255,0.03);border-radius:6px;padding:8px;margin:6px 0}
    .table-container{max-height:180px;overflow-y:auto}
    .performance-table{width:100%;font-size:11px}
    .performance-table th{padding:6px 4px}
    .performance-table td{padding:4px 6px}
    .badge{padding:2px 6px;border-radius:10px;font-size:9px;font-weight:bold;text-transform:uppercase}
    .bot-badge{background:#6c5ce7;color:white}
    .human-badge{background:#00d4aa;color:white}
    .compact-section{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start}
    .main-grid{display:grid;grid-template-columns:2fr 1fr;gap:12px;min-height:calc(100vh - 120px);overflow:visible}
    .left-panel{display:flex;flex-direction:column;gap:8px}
    .right-panel{display:flex;flex-direction:column;gap:8px}
    .chat-chart-container{width:100%;overflow-x:auto}
    .calc-control{display:inline-block;margin-right:15px;color:#e0e0e0;font-size:0.85em}
    .calc-control input[type="radio"]{margin-right:5px}
    .calculation-controls{background:rgba(102,126,234,0.1);padding:8px;border-radius:6px;border:1px solid rgba(102,126,234,0.3)}
    """

# --------------------------------------------------
# Output Management
# --------------------------------------------------

def save_summary_file(output_dir: Path, filename: str, content: str) -> None:
    """Save text summary file"""
    summary_path = output_dir / filename
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ {filename}")

def save_dashboard_file(output_dir: Path, filename: str, html_content: str) -> None:
    """Save HTML dashboard file"""
    dashboard_path = output_dir / filename
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ {filename}")

def save_csv_file(output_dir: Path, filename: str, dataframe: pd.DataFrame) -> None:
    """Save processed CSV file"""
    csv_path = output_dir / filename
    dataframe.to_csv(csv_path, index=False)
    print(f"✅ {filename}")

# --------------------------------------------------
# Logging and Output
# --------------------------------------------------

def print_separator(char: str = "─", length: int = 60) -> None:
    """Print separator line"""
    print(char * length)

def print_analysis_header(label: str, date_range: Optional[str] = None) -> None:
    """Print formatted analysis header"""
    print_separator()
    print(f"🔍 {label}")
    if date_range:
        print(f"   {date_range}")
    print_separator()

def print_data_source_summary(sources: dict) -> None:
    """Print summary of detected data sources"""
    ticket_count = len(sources.get('tickets', []))
    chat_count = len(sources.get('chats', []))
    
    if ticket_count > 0:
        print(f"📋 Found {ticket_count} ticket CSV file(s)")
    if chat_count > 0:
        print(f"💬 Found {chat_count} chat CSV file(s)")
    
    if ticket_count == 0 and chat_count == 0:
        raise FileNotFoundError("No CSV files found in ./tickets/ or ./chats/ directories")

# --------------------------------------------------
# Feature Flag System
# --------------------------------------------------

def get_chart_mode() -> str:
    """
    Get current chart rendering mode from environment variable.
    
    Returns:
        'interactive' for Plotly charts, 'static' for matplotlib charts
    """
    return os.getenv('CHART_MODE', 'static').lower()

def is_interactive_mode() -> bool:
    """Check if interactive chart mode is enabled"""
    return get_chart_mode() == 'interactive' and PLOTLY_AVAILABLE

def set_chart_mode(mode: str) -> None:
    """
    Set chart rendering mode.
    
    Args:
        mode: 'interactive' or 'static'
    """
    if mode not in ['interactive', 'static']:
        raise ValueError("Chart mode must be 'interactive' or 'static'")
    os.environ['CHART_MODE'] = mode

# --------------------------------------------------
# Interactive Chart Rendering
# --------------------------------------------------

def create_interactive_chart(
    data: pd.DataFrame,
    chart_type: Optional['ChartType'] = None,
    title: str = "Chart",
    config: Optional['ChartConfig'] = None,
    **kwargs
) -> str:
    """
    Create interactive Plotly chart and return HTML.
    
    Args:
        data: Source data for the chart
        chart_type: Type of chart to create (auto-detected if None)
        title: Chart title
        config: Chart configuration (uses dashboard preset if None)
        **kwargs: Chart-specific parameters
        
    Returns:
        HTML string containing the interactive chart
        
    Raises:
        ImportError: If Plotly is not available
        ValueError: If data is invalid or chart type unsupported
    """
    if not PLOTLY_AVAILABLE:
        raise ImportError(
            "Plotly is not available. Install it with: pip install plotly>=5.0.0"
        )
    
    # Auto-detect chart type if not specified
    if chart_type is None:
        chart_type = auto_detect_chart_type(data)
    
    # Use dashboard preset if no config provided
    if config is None:
        config = ChartPresets.dashboard_chart()
    
    # Create interactivity config based on chart mode
    interactivity = kwargs.pop('interactivity', ChartPresets.full_interactivity())
    
    # Validate data
    required_columns = kwargs.get('required_columns', [])
    if required_columns:
        validate_chart_data(data, required_columns)
    
    # Create and render chart
    chart = ChartFactory.create_chart(chart_type, title, config, interactivity)
    chart.render(data, **kwargs)
    
    # Return HTML with dashboard integration styling
    return chart.to_html(include_plotlyjs="cdn")

def plotly_fig_to_html(
    fig: 'go.Figure',
    style_class: str = "chart",
    include_plotlyjs: Union[bool, str] = "cdn"
) -> str:
    """
    Convert Plotly figure to HTML for dashboard integration.
    
    Args:
        fig: Plotly figure object
        style_class: CSS class for the container div
        include_plotlyjs: How to include Plotly.js ('cdn', 'inline', True, False)
        
    Returns:
        HTML string with styled container
    """
    if not PLOTLY_AVAILABLE:
        raise ImportError("Plotly is not available")
    
    # Convert figure to HTML
    html = fig.to_html(
        include_plotlyjs=include_plotlyjs,
        config={
            "displayModeBar": True,
            "responsive": True,
            "displaylogo": False
        }
    )
    
    # Wrap in styled container for dashboard integration
    return f'<div class="{style_class} interactive-chart">{html}</div>'

def chart_to_html(
    fig_or_data,
    chart_type: Optional['ChartType'] = None,
    title: str = "Chart",
    style_class: str = "chart",
    force_static: bool = False,
    **kwargs
) -> str:
    """
    Universal chart rendering function with automatic mode detection.
    
    This function serves as a smart wrapper that can handle both matplotlib
    figures and pandas DataFrames, automatically choosing between static
    and interactive rendering based on configuration and availability.
    
    Args:
        fig_or_data: Either a matplotlib figure or pandas DataFrame
        chart_type: Type of chart to create (for DataFrame input)
        title: Chart title (for DataFrame input)
        style_class: CSS class for the container
        force_static: Force static rendering even in interactive mode
        **kwargs: Additional chart parameters
        
    Returns:
        HTML string containing the chart
    """
    # Force static rendering if requested or if Plotly unavailable
    if force_static or not PLOTLY_AVAILABLE:
        if hasattr(fig_or_data, 'savefig'):  # matplotlib figure
            return fig_to_html(fig_or_data, style_class)
        else:
            raise ValueError("Static rendering requires matplotlib figure")
    
    # Check if interactive mode is enabled
    if is_interactive_mode():
        if isinstance(fig_or_data, pd.DataFrame):
            # Create interactive chart from DataFrame
            return create_interactive_chart(
                fig_or_data, chart_type, title, style_class=style_class, **kwargs
            )
        elif hasattr(fig_or_data, 'to_html'):  # Plotly figure
            return plotly_fig_to_html(fig_or_data, style_class)
        elif hasattr(fig_or_data, 'savefig'):  # matplotlib figure
            # Fall back to static rendering
            return fig_to_html(fig_or_data, style_class)
        else:
            raise ValueError("Unsupported figure type for interactive rendering")
    
    # Default to static rendering
    if hasattr(fig_or_data, 'savefig'):  # matplotlib figure
        return fig_to_html(fig_or_data, style_class)
    else:
        raise ValueError("Static mode requires matplotlib figure")

# --------------------------------------------------
# Chart Configuration Helpers
# --------------------------------------------------

def get_chart_config_for_context(context: str = "dashboard") -> Optional['ChartConfig']:
    """
    Get appropriate chart configuration for different contexts.
    
    Args:
        context: 'dashboard', 'presentation', 'mobile', or 'api'
        
    Returns:
        Appropriate ChartConfig instance or None if Plotly unavailable
    """
    if not PLOTLY_AVAILABLE:
        return None
    
    config_map = {
        "dashboard": ChartPresets.dashboard_chart,
        "presentation": ChartPresets.presentation_chart,
        "mobile": ChartPresets.mobile_chart,
        "api": ChartPresets.dashboard_chart  # Default for API usage
    }
    
    config_func = config_map.get(context, ChartPresets.dashboard_chart)
    return config_func()

def get_interactivity_config_for_context(context: str = "dashboard") -> Optional['InteractivityConfig']:
    """
    Get appropriate interactivity configuration for different contexts.
    
    Args:
        context: 'dashboard', 'presentation', 'mobile', or 'minimal'
        
    Returns:
        Appropriate InteractivityConfig instance or None if Plotly unavailable
    """
    if not PLOTLY_AVAILABLE:
        return None
    
    if context in ["mobile", "minimal", "presentation"]:
        return ChartPresets.minimal_interactivity()
    else:
        return ChartPresets.full_interactivity()

# --------------------------------------------------
# Convenience Chart Creation Functions
# --------------------------------------------------

def create_time_series_chart(
    data: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str = "Time Series Analysis",
    color_column: Optional[str] = None,
    **kwargs
) -> str:
    """
    Convenience function for creating time series charts.
    
    Args:
        data: DataFrame with time series data
        x_column: Name of the datetime column
        y_column: Name of the value column
        title: Chart title
        color_column: Optional column for grouping/coloring
        **kwargs: Additional chart parameters
        
    Returns:
        HTML string containing the chart
    """
    if is_interactive_mode():
        return create_interactive_chart(
            data=data,
            chart_type=ChartType.TIME_SERIES,
            title=title,
            x_column=x_column,
            y_column=y_column,
            color_column=color_column,
            **kwargs
        )
    else:
        # Fallback to matplotlib implementation would go here
        # For now, raise an error to indicate this needs implementation
        raise NotImplementedError(
            "Static time series charts not yet implemented. "
            "Enable interactive mode with set_chart_mode('interactive')"
        )

def create_bar_chart(
    data: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str = "Bar Chart Analysis",
    orientation: str = "v",
    color_column: Optional[str] = None,
    **kwargs
) -> str:
    """
    Convenience function for creating bar charts.
    
    Args:
        data: DataFrame with categorical data
        x_column: Name of the category column
        y_column: Name of the value column
        title: Chart title
        orientation: 'v' for vertical, 'h' for horizontal
        color_column: Optional column for grouping/coloring
        **kwargs: Additional chart parameters
        
    Returns:
        HTML string containing the chart
    """
    if is_interactive_mode():
        return create_interactive_chart(
            data=data,
            chart_type=ChartType.BAR,
            title=title,
            x_column=x_column,
            y_column=y_column,
            orientation=orientation,
            color_column=color_column,
            **kwargs
        )
    else:
        # Fallback to matplotlib implementation would go here
        raise NotImplementedError(
            "Static bar charts not yet implemented. "
            "Enable interactive mode with set_chart_mode('interactive')"
        )

def create_pie_chart(
    data: pd.DataFrame,
    values_column: str,
    names_column: str,
    title: str = "Distribution Analysis",
    **kwargs
) -> str:
    """
    Convenience function for creating pie charts.
    
    Args:
        data: DataFrame with categorical data
        values_column: Name of the values column
        names_column: Name of the labels column
        title: Chart title
        **kwargs: Additional chart parameters
        
    Returns:
        HTML string containing the chart
    """
    if is_interactive_mode():
        return create_interactive_chart(
            data=data,
            chart_type=ChartType.PIE,
            title=title,
            values_column=values_column,
            names_column=names_column,
            **kwargs
        )
    else:
        # Fallback to matplotlib implementation would go here
        raise NotImplementedError(
            "Static pie charts not yet implemented. "
            "Enable interactive mode with set_chart_mode('interactive')"
        )

# --------------------------------------------------
# Backward Compatibility Wrapper
# --------------------------------------------------

def render_chart_with_fallback(
    data: pd.DataFrame,
    chart_type: str,
    title: str,
    fallback_func: callable = None,
    **kwargs
) -> str:
    """
    Render chart with automatic fallback to matplotlib if Plotly fails.
    
    Args:
        data: Source data
        chart_type: Type of chart ('time_series', 'bar', 'pie')
        title: Chart title
        fallback_func: Function to call if interactive rendering fails
        **kwargs: Chart parameters
        
    Returns:
        HTML string containing the chart
    """
    # Try interactive rendering first if enabled
    if is_interactive_mode():
        try:
            chart_type_map = {
                'time_series': ChartType.TIME_SERIES,
                'bar': ChartType.BAR,
                'pie': ChartType.PIE,
                'multi_series': ChartType.MULTI_SERIES
            }
            
            plotly_chart_type = chart_type_map.get(chart_type)
            if plotly_chart_type:
                return create_interactive_chart(
                    data=data,
                    chart_type=plotly_chart_type,
                    title=title,
                    **kwargs
                )
        except Exception as e:
            print(f"Warning: Interactive chart rendering failed: {e}")
            print("Falling back to static rendering...")
    
    # Fallback to provided function or raise error
    if fallback_func:
        fig = fallback_func(data, title, **kwargs)
        return fig_to_html(fig)
    else:
        raise NotImplementedError(
            f"No fallback implementation available for {chart_type} charts. "
            "Provide a fallback_func parameter or implement static version."
        )