# Ticket Dashboard - Complete Setup Guide

A comprehensive analytics platform for support ticket and chat data analysis with Google Sheets integration, AI-powered analysis, and automated monitoring.

## 🚀 Quick Start

### Web UI (Recommended)

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Start the Web Interface**
```bash
python start_ui.py
```

3. **Access Dashboard**
   - Navigate to `http://localhost:5000` (or 5001 if port conflict)
   - Upload CSV files or use existing data in `tickets/` and `chats/` directories
   - Select analytics type and date ranges
   - Generate reports with export options

### Command Line Interface

```bash
# Basic ticket analysis
python ticket_analytics.py

# Specific time periods
python ticket_analytics.py --week 22072025      # Weekly (Monday-Sunday)
python ticket_analytics.py --day 22072025       # Single day
python ticket_analytics.py --custom 15072025-22072025  # Date range

# Advanced options
python ticket_analytics.py --schedule-file config/schedule.yaml --include-delayed-table
```

## 📊 Analytics Types

### 📋 Ticket Analytics
- **Response Time Analysis**: Track first response times by agent and time period
- **Agent Performance**: Compare volumes and response efficiency (Girly, Nova, Francis, Bhushan)
- **Weekend Detection**: Identify off-hours tickets using configurable schedules
- **Pipeline Breakdown**: Analyze ticket distribution across different pipelines
- **Trend Analysis**: Weekly and daily volume patterns with statistical insights

### 💬 Chat Analytics
- **Bot Performance**: Comprehensive satisfaction analysis for Wynn AI and Agent Scrape (Traject Data Live Chat) bots
- **Human Agent Analysis**: Performance tracking for Girly, Nova, Francis, Bhushan
- **Transfer Analysis**: Bot-to-human escalation rates and patterns with "chatbot-transfer" tag detection
- **Volume Metrics**: Daily/weekly chat trends, hourly distribution, geographic analysis
- **Satisfaction Tracking**: Good/bad rating percentages with trend analysis (excludes "not rated")

### 🎯 Combined Analytics (Default when both data types present)
- **Unified Dashboard**: Simultaneous processing of tickets and chats
- **Cross-Platform Performance**: Agent performance across both support channels
- **Comprehensive Metrics**: Combined volume, response time, and satisfaction analysis

### 🤖 AI-Powered Analysis
- **Natural Language Interface**: Chat with AI to explore your support data
- **Google Gemini Integration**: Advanced AI analysis powered by Gemini API
- **Data Source Flexibility**: Upload CSV files or connect Google Sheets
- **Interactive Exploration**: Ask questions about trends, performance, and insights

## 🔧 Core Configuration

### Agent Schedules (`config/schedule.yaml`)
Defines agent working hours for weekend detection:

```yaml
agents:
  "Girly":
    monday:
      - start: "09:00"
        end: "17:00"
    tuesday:
      - start: "09:00"
        end: "17:00"
    # ... continue for all days
```

### Chat Configuration (`config/chat-config.yaml`)
Bot and agent mappings:

```yaml
bots:
  wynn_ai:
    name: "Wynn AI"
    id: "ce8545b838652bea3889eafd72a6d821"
  support_bot:
    name: "Agent Scrape"
    id: "5626186ef1d50006d82a02372509ec3e"
```

### Chart Modes
```bash
export CHART_MODE=interactive  # Plotly (default)
export CHART_MODE=static       # matplotlib fallback
```

## 🔐 Google Sheets Integration

### Setup Google Cloud Project

1. **Create Project**: Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Enable APIs**: Enable "Google Sheets API" and "Google Drive API"
3. **Create Credentials**: Either service account (automation) or OAuth (interactive)

### Service Account Setup (Recommended)

1. **Create Service Account**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Name: "ticket-dashboard-service"

2. **Generate Key**:
   - Click on service account email
   - "Keys" tab > "Add Key" > "Create new key" > "JSON"
   - Save as `credentials.json` in project root

3. **Share Sheets**: Share your spreadsheet with the service account email (found in `credentials.json`)

### OAuth Setup (Interactive)

1. **Create OAuth Client**:
   - "APIs & Services" > "Credentials"
   - "Create Credentials" > "OAuth 2.0 Client ID"
   - Choose "Desktop Application"
   - Download JSON as `credentials.json`

### Usage Examples

```bash
# Export to new sheet
python ticket_analytics.py --day 02092025 --export-to-sheets

# Update existing sheet
python ticket_analytics.py --day 02092025 --export-to-sheets --sheets-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

# Custom credentials
python ticket_analytics.py --day 02092025 --export-to-sheets --credentials-path "/path/to/credentials.json"
```

### Programmatic Usage

```python
from google_sheets_exporter import GoogleSheetsExporter
import pandas as pd

# Initialize exporter
exporter = GoogleSheetsExporter('credentials.json')

# Load and export data
ticket_df = pd.read_csv('results/latest/tickets_transformed.csv')
spreadsheet_id = exporter.export_data(
    ticket_df=ticket_df,
    spreadsheet_title="My Support Dashboard"
)

print(f"Sheet URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
```

### Google Sheets Features

- **🔄 Rolling 365-day window**: Automatically maintains recent data
- **⚡ Upsert functionality**: Updates existing records, adds new ones
- **📋 Separate sheets**: Tickets and Chats in different tabs
- **🧮 Calculated fields**: Enhanced data with business intelligence fields
- **📊 Logging sheets**: Processing run history and dashboard metrics
- **🔧 Automatic cleanup**: Removes data older than 365 days

### Calculated Fields Added

Both tickets and chats get enhanced with:
- `Day_of_Week_Number/Name` - Weekday analysis
- `Is_Weekend/Is_Weekday` - Business hours analysis
- `FY_Quarter/FY_Year` - Fiscal reporting
- `Month_Number/Name/Year` - Monthly trending
- `Last_Updated` - Data freshness tracking
- `Data_Type` - Source identification

**Tickets specific**:
- `Response_Time_Hours_Clean` - Validated response times
- `Response_Time_Category` - Grouped response time ranges
- `Created_During_Business_Hours` - Business hours flag
- `Ticket_Age_Days` - Aging analysis

**Chats specific**:
- `Hour_of_Day/Time_Period` - Hourly patterns
- `Duration_Minutes/Hours` - Session length analysis

## 🤖 Automated Monitoring

### Real-time File Monitoring

The system includes `auto_sync_monitor.py` for automatic file detection and Google Sheets sync:

```python
from auto_sync_monitor import AutoSyncMonitor

# Start monitoring
monitor = AutoSyncMonitor()
monitor.start_monitoring(use_watchdog=True)
```

### Daily Sync Script

```bash
#!/bin/bash
# daily_sync.sh

YESTERDAY=$(date -d "yesterday" +%d%m%Y)

python ticket_analytics.py \
    --day $YESTERDAY \
    --export-to-sheets \
    --sheets-id "YOUR_SHEET_ID_HERE" \
    --quiet

echo "Daily sync completed: $(date)"
```

### Cron Job Setup

```bash
# Add to crontab (crontab -e)
# Run daily at 6 AM
0 6 * * * /path/to/daily_sync.sh >> /var/log/ticket_sync.log 2>&1
```

## 🔍 Data Processing Logic

### Agent Name Standardization

All analytics use real names consistently:
- `Shan`/`Shan D` → `Bhushan`
- `Chris`/`Chris S` → `Francis`
- `Nora`/`Nora N` → `Nova`
- `Gillie`/`Girly E` → `Girly`

### Ticket Processing Pipeline

1. **Timezone Conversion**: CDT timestamps → ADT (+1 hour)
2. **Agent Name Mapping**: Standardizes names using mapping above
3. **Weekend Flagging**: Uses `config/schedule.yaml` for off-hours detection
4. **SPAM Filtering**: Excludes "SPAM Tickets" pipeline automatically
5. **Response Time Validation**: Filters negative/invalid response times

### Chat Processing Pipeline

1. **Timezone Conversion**: UTC timestamps → ADT for local analysis
2. **Agent Classification**: Auto-detects bots vs humans
   - **Bots**: Wynn AI, Agent Scrape (Traject Data Live Chat)
   - **Humans**: Bhushan, Girly, Francis, Nova
3. **Transfer Detection**: Identifies escalations via "chatbot-transfer" tags
4. **Satisfaction Processing**: Maps ratings ("rated good" → 5, "rated bad" → 1)
5. **Bot Performance Analysis**: Separate metrics for each bot type

## 📈 Export & Visualization

### Export Options
- **🖼️ PNG Export**: Full-page screenshots (1920x1080 optimized)
- **📄 PDF Export**: Professional reports with embedded charts
- **📝 Google Docs Export**: Cloud documents with embedded visualizations
- **📊 CSV Export**: Raw processed data for external analysis

### Chart Features
- **Interactive Mode**: Plotly-based with drill-down capabilities
- **Static Fallback**: matplotlib for systems without Plotly
- **Enhanced Fonts**: ~10% larger text for better readability
- **Responsive Design**: Mobile-compatible layouts
- **Full Width Charts**: Weekly displays maximize screen real estate

## 🏗️ Architecture Overview

### Core Components
- **`app.py`**: Flask web application (primary interface)
- **`start_ui.py`**: Web UI launcher with dependency validation
- **`ticket_analytics.py`**: Command-line orchestrator
- **`ticket_processor.py`**: Support ticket data processing
- **`chat_processor.py`**: LiveChat data processing
- **`dashboard_builder.py`**: HTML dashboard generation
- **`google_sheets_exporter.py`**: Google Sheets integration
- **`auto_sync_monitor.py`**: Real-time file monitoring
- **`processing_logger.py`**: Comprehensive logging system

### Specialized Analysis
- **`agent_performance_analyzer.py`**: Cross-agent performance comparison
- **`individual_agent_analyzer.py`**: Individual vs team benchmarking
- **`create_monthly_response_charts.py`**: Monthly trend analysis
- **`dashboard_metrics_extractor.py`**: High-level metrics extraction

### AI Components
- **`customer-support-ai-analyst/`**: TypeScript/React AI widget
- **`services/geminiService.ts`**: Google Gemini API integration
- **`services/googleSheetsService.ts`**: Google Sheets API for AI

## 📁 File Structure

```
ticket-dashboard/
├── Core Application Files
│   ├── app.py                          # Flask web app
│   ├── start_ui.py                     # UI launcher
│   ├── ticket_analytics.py             # CLI orchestrator
│   ├── ticket_processor.py             # Ticket processing
│   ├── chat_processor.py               # Chat processing
│   └── dashboard_builder.py            # Dashboard generation
├── Integration & Export
│   ├── google_sheets_exporter.py       # Google Sheets integration
│   ├── auto_sync_monitor.py            # File monitoring
│   ├── processing_logger.py            # Logging system
│   ├── export_utils.py                 # Export functionality
│   └── dashboard_metrics_extractor.py  # Metrics extraction
├── Analysis Modules
│   ├── agent_performance_analyzer.py   # Cross-agent analysis
│   ├── individual_agent_analyzer.py    # Individual benchmarking
│   ├── create_monthly_response_charts.py # Monthly trends
│   └── create_ticket_breakdown_charts.py # Pipeline analysis
├── AI Components
│   └── customer-support-ai-analyst/    # AI-powered analysis
│       ├── App.tsx                     # React application
│       ├── components/                 # React components
│       └── services/                   # AI services
├── Configuration
│   └── config/
│       ├── schedule.yaml               # Agent schedules
│       └── chat-config.yaml            # Chat configuration
├── Data Directories
│   ├── tickets/                        # Support ticket CSVs
│   ├── chats/                          # LiveChat CSVs
│   ├── uploads/                        # User uploads
│   └── results/                        # Generated reports
└── Web Interface
    └── templates/
        └── index.html                  # Main web template
```

## 🚨 Troubleshooting

### Common Issues

**"Authentication failed"**
- Verify `credentials.json` exists and is valid
- Check Google APIs are enabled (Sheets + Drive)
- Ensure service account has sheet access

**"Permission denied"**
- Share sheet with service account email (from `credentials.json`)
- Verify OAuth scopes include Sheets and Drive access

**"Mixed data types warning"**
- This is normal for complex CSV files (320+ columns)
- System handles automatically with `dtype=str, low_memory=False`

**"Import errors"**
```bash
# Install missing dependencies
pip install -r requirements.txt

# Check specific modules
python -c "from ticket_processor import TicketDataProcessor; print('✅ Working')"
```

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.INFO)

# Enable detailed logging
from google_sheets_exporter import GoogleSheetsExporter
exporter = GoogleSheetsExporter('credentials.json', debug=True)
```

## 🔐 Security Best Practices

1. **Secure Credentials**:
   ```bash
   chmod 600 credentials.json
   echo "credentials.json" >> .gitignore
   ```

2. **Use Service Accounts**: More secure for automation than OAuth

3. **Limit API Permissions**: Only enable required APIs

4. **Monitor Usage**: Check Google Cloud Console for quotas

5. **Environment Variables**: Use `.env` files for sensitive configuration

## 🎯 Advanced Usage

### Multiple Spreadsheets

```python
# Separate exports for different teams
ticket_sheet = exporter.export_data(
    ticket_df=tickets, 
    spreadsheet_title="Support Team Dashboard"
)
chat_sheet = exporter.export_data(
    chat_df=chats, 
    spreadsheet_title="Chat Analytics Dashboard"
)
```

### Custom Rolling Windows

```python
# Modify retention period
def get_rolling_window_data(self, df, days=180):  # 6 months instead of 365
    # Custom implementation
```

### Google Sheets Analytics Examples

**Weekend vs Weekday Response Times**:
```
=AVERAGEIF(Is_Weekend:Is_Weekend,TRUE,Response_Time_Hours_Clean:Response_Time_Hours_Clean)
=AVERAGEIF(Is_Weekend:Is_Weekend,FALSE,Response_Time_Hours_Clean:Response_Time_Hours_Clean)
```

**Business Hours Analysis**:
```
=COUNTIFS(Created_During_Business_Hours:Created_During_Business_Hours,TRUE,Response_Time_Category:Response_Time_Category,"< 1 hour")
```

**Quarterly Performance**:
```
=AVERAGEIF(FY_Quarter_Full:FY_Quarter_Full,"2025-Q3",Response_Time_Hours_Clean:Response_Time_Hours_Clean)
```

### AI Analyst Setup

1. **Navigate to AI directory**:
   ```bash
   cd customer-support-ai-analyst
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure Gemini API**:
   ```bash
   # Create .env.local file
   echo "GEMINI_API_KEY=your_api_key_here" > .env.local
   ```

4. **Start development server**:
   ```bash
   npm run dev
   ```

## 📊 Output Structure

Results are saved in timestamped directories:

```
results/YYYY-MM-DD_HH-MM-SS/
├── index.html                          # Navigation dashboard
├── ticket_analytics_dashboard.html     # Ticket analysis (if generated)
├── chat_analytics_dashboard.html       # Chat analysis (if generated)
├── combined_analytics_dashboard.html   # Combined analysis (if both data types)
├── ticket_analytics_summary.txt        # Text summary
├── chat_analytics_summary.txt          # Text summary
├── tickets_transformed.csv             # Processed ticket data
├── chats_transformed.csv               # Processed chat data
└── exports/                            # Export files (PNG, PDF)
    ├── dashboard_[timestamp].png
    ├── dashboard_[timestamp].pdf
    └── [Google Docs links in responses]
```

## Requirements

### Core Dependencies
- **Python 3.8+**
- **pandas>=1.3.0** - Data processing
- **matplotlib>=3.5.0** - Charts (fallback)
- **plotly>=5.0.0** - Interactive charts
- **Flask>=2.0.0** - Web framework
- **pytz** - Timezone support

### Export Dependencies
- **selenium>=4.15.0** - PNG screenshots
- **reportlab>=3.6.0** - PDF generation
- **google-api-python-client>=2.0.0** - Google integration
- **pillow>=9.0.0** - Image processing

### Monitoring Dependencies
- **watchdog** - File monitoring
- **PyYAML** - Configuration files

**Install all**: `pip install -r requirements.txt`

The system is now ready for production use with automated monitoring, Google Sheets integration, and AI-powered analysis capabilities!