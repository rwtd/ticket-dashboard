# Ticket Dashboard - Analytics Platform

A comprehensive support analytics platform with ticket analysis, chat analytics, Google Sheets integration, and AI-powered insights.

## 🚀 Quick Start

### Web UI (Recommended)
```bash
pip install -r requirements.txt
python start_ui.py
# Navigate to http://localhost:5000
```

### Command Line
```bash
# Basic analysis
python ticket_analytics.py

# Specific periods
python ticket_analytics.py --week 22072025
python ticket_analytics.py --day 22072025
python ticket_analytics.py --custom 15072025-22072025
```

## 📊 Analytics Types

- **📋 Tickets**: Response times, agent performance, weekend detection, pipeline breakdown
- **💬 Chats**: Bot satisfaction, human agent analysis, transfer rates, volume trends  
- **🎯 Combined**: Unified ticket + chat analysis (auto-selected when both present)
- **🤖 AI-Powered**: Natural language data exploration with Google Gemini

## ✨ Key Features

- **Web Interface**: Drag-and-drop uploads, interactive charts, real-time processing
- **Google Sheets**: Rolling 365-day sync with calculated fields and upsert functionality
- **Export Options**: PNG, PDF, Google Docs with high-quality visualizations
- **Agent Standardization**: Automatic pseudonym → real name mapping
- **Automated Monitoring**: File watching with automatic Google Sheets sync
- **Comprehensive Logging**: Processing runs tracked with metrics extraction

## 🔧 Data Processing

### Agent Name Mapping
- `Shan`/`Shan D` → `Bhushan`
- `Chris`/`Chris S` → `Francis`
- `Nora`/`Nora N` → `Nova`
- `Gillie`/`Girly E` → `Girly`

### Data Transformations
- **Tickets**: CDT→ADT timezone conversion, weekend flagging, SPAM filtering
- **Chats**: UTC→ADT conversion, bot/human classification, transfer detection

## 📁 Directory Structure

```
ticket-dashboard/
├── Core Application
│   ├── app.py                          # Flask web interface
│   ├── start_ui.py                     # UI launcher
│   ├── ticket_analytics.py             # CLI orchestrator
│   ├── ticket_processor.py             # Ticket processing
│   └── chat_processor.py               # Chat processing
├── Integration & Export
│   ├── google_sheets_exporter.py       # Google Sheets sync
│   ├── auto_sync_monitor.py            # File monitoring
│   ├── processing_logger.py            # Logging system
│   └── export_utils.py                 # Export functionality
├── Analysis Modules
│   ├── agent_performance_analyzer.py   # Cross-agent analysis
│   └── individual_agent_analyzer.py    # Individual benchmarking
├── AI Components
│   └── customer-support-ai-analyst/    # TypeScript/React AI widget
├── Data Directories
│   ├── tickets/                        # Support ticket CSVs
│   ├── chats/                          # LiveChat CSVs
│   ├── uploads/                        # User uploads
│   └── results/                        # Generated reports
└── Configuration
    └── config/
        ├── schedule.yaml               # Agent schedules
        └── chat-config.yaml            # Chat configuration
```

## 📋 Requirements

**Core**: Python 3.8+, pandas, matplotlib, plotly, Flask, pytz
**Export**: selenium, reportlab, google-api-python-client, pillow  
**Optional**: PyYAML, watchdog, seaborn

```bash
pip install -r requirements.txt
```

## 📖 Complete Documentation

For detailed setup instructions, Google Sheets integration, automation, troubleshooting, and advanced usage examples, see **[SETUP_GUIDE.md](SETUP_GUIDE.md)**.

## 🎯 Output

Results are saved in timestamped directories with dashboards, summaries, processed data, and export files:

```
results/YYYY-MM-DD_HH-MM-SS/
├── index.html                          # Navigation dashboard
├── *_analytics_dashboard.html          # Analysis dashboards
├── *_analytics_summary.txt             # Text summaries
├── *_transformed.csv                   # Processed data
└── exports/                            # PNG, PDF, Google Docs
```

Ready for production use with automated monitoring, Google Sheets integration, and AI-powered analysis!