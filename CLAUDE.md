# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Web UI (Primary Interface)
```bash
# Install dependencies
pip install -r requirements.txt

# Start web interface
python start_ui.py
# Access at http://localhost:5000 (or 5001 if port conflict)

# Test UI components
python test_ui.py

# Run Flask app directly (development)
python app.py
```

### Command Line Tool
```bash
# Install dependencies
pip install -r requirements.txt

# Run ticket analytics (auto-detect data sources)
python ticket_analytics.py

# Date-specific analysis
python ticket_analytics.py --week 22072025      # Weekly (Monday-Sunday)
python ticket_analytics.py --day 22072025       # Single day
python ticket_analytics.py --custom 15072025-22072025  # Date range

# Advanced options
python ticket_analytics.py --schedule-file config/schedule.yaml --include-delayed-table
```

### Auto-Sync Monitoring
```bash
# Start automated file monitoring and Google Sheets sync
./start_auto_sync.sh

# Or run directly with custom options
python auto_sync_monitor.py --spreadsheet-id "YOUR_SHEET_ID" --sweep-interval 300

# Monitor specific directories
python auto_sync_monitor.py --tickets-dir /path/to/tickets --chats-dir /path/to/chats

# Use polling instead of real-time monitoring
python auto_sync_monitor.py --no-watchdog --sweep-interval 60
```

### Testing
```bash
# Test core functionality
python -c "from ticket_processor import TicketDataProcessor; print('✅ Ticket processor working')"

# Test UI components (if test_ui.py exists)
python test_ui.py

# Test Google Sheets authentication
python test_desktop_auth.py
```

### Specialized Analysis Scripts
```bash
# Agent performance comparison across multiple time periods
python agent_performance_analyzer.py

# Individual agent vs team benchmarking  
python individual_agent_analyzer.py

# Monthly response time trend analysis
python create_monthly_response_charts.py

# Ticket type breakdown analysis
python create_ticket_breakdown_charts.py

# Weekend chat analysis
python analyze_chat_weekend.py

# Extract metrics and time periods (data utilities)
python extract_metrics.py
python extract_time_periods.py
```

### TypeScript/React AI Widget
```bash
# Navigate to AI widget directory
cd customer-support-ai-analyst

# Install Node.js dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Architecture Overview

### Core Components
- **`app.py`**: Flask web application providing the primary user interface
- **`start_ui.py`**: Startup script with dependency checking and graceful initialization
- **`ticket_analytics.py`**: Command-line application orchestrator focused on ticket analysis
- **`ticket_processor.py`**: Support ticket data processing with timezone conversion (CDT→ADT) and agent mapping
- **`chat_processor.py`**: LiveChat data processing with bot performance and transfer analysis
- **`dashboard_builder.py`**: HTML dashboard generation with responsive design for both tickets and chats
- **`common_utils.py`**: Shared utilities for date handling, chart generation, and configuration management
- **`chart_components.py`**: Interactive chart system with Plotly/matplotlib fallback
- **`export_utils.py`**: Export functionality for PNG, PDF, and Google Docs integration

### Specialized Analysis Modules
- **`agent_performance_analyzer.py`**: Cross-agent performance comparison with multiple time periods
- **`individual_agent_analyzer.py`**: Individual agent benchmarking against team averages
- **`create_monthly_response_charts.py`**: Monthly response time trend analysis with hybrid charts
- **`create_ticket_breakdown_charts.py`**: Ticket type/pipeline breakdown visualizations
- **`analyze_chat_weekend.py`**: Weekend-specific chat volume and satisfaction analysis
- **`extract_metrics.py`**: Data extraction utility for metrics analysis
- **`extract_time_periods.py`**: Time period data extraction and processing

### Web Interface Components
- **`templates/index.html`**: Main web UI with analytics type selection, file upload, date selection, and results display
- **`uploads/`**: Directory for user-uploaded CSV files (both tickets and chats)
- **`test_ui.py`**: UI component testing and validation script

### AI-Powered Components
- **`customer-support-ai-analyst/`**: TypeScript/React-based AI analyst widget using Google Gemini
  - **`App.tsx`**: Main application component with chat interface
  - **`components/AIAnalystChat.tsx`**: Chat interface for AI-powered data analysis
  - **`components/DataSourceSelector.tsx`**: Data source selection and upload interface
  - **`services/geminiService.ts`**: Google Gemini API integration for AI analysis
  - **`services/googleSheetsService.ts`**: Google Sheets integration for data import

### Analytics Types
- **📋 Ticket Analytics**: Support ticket analysis with response times and agent performance
- **💬 Chat Analytics**: LiveChat analysis with bot satisfaction and transfer rates
- **📊 Combined Analytics**: Unified dashboard (planned feature)
- **🤖 AI-Powered Analysis**: Google Gemini-powered chat interface for natural language data exploration

### Data Pipeline Architecture
1. **Detection**: Scans `./tickets/` and `./chats/` directories for CSV files
2. **Validation**: Validates required columns and data formats for both ticket and chat data
3. **Processing**: 
   - **Tickets**: CDT→ADT timezone conversion (+1 hour), weekend flagging, agent name standardization
   - **Chats**: UTC→ADT timezone conversion, bot/human classification, transfer detection
4. **Analytics Generation**: Calculates metrics, trends, and performance for tickets and chats
5. **Dashboard Creation**: Responsive HTML with interactive/static chart modes for unified analytics

### Configuration System
- **Chart Modes**: Set via `CHART_MODE` environment variable or `set_chart_mode()` function
  - `interactive`: Plotly-based charts (default if available)
  - `static`: matplotlib fallback charts
- **Schedule Configuration**: `config/schedule.yaml` defines agent shifts for weekend detection
- **Data Sources**: Environment variable for `TICKET_DATA_SOURCE`, `OUTPUT_DIR`
- **AI Configuration**: `GEMINI_API_KEY` environment variable for AI-powered analysis features

## Key Data Processing Logic

### Agent Classification
- **Tickets**: Staff name mapping (`Girly .` → `Girly`, `Nora N` → `Nova`) with weekend exclusion logic
- **Chats**: Bot detection (`Wynn AI`, `Agent Scrape`) vs Human agents (`Bhushan`, `Girly`, `Francis`, `Nova`)

### Agent Name Standardization
**All analytics consistently use real names:**
- `Gillie`/`Gillie E`/`Girly E` → `Girly`
- `Shan`/`Shan D` → `Bhushan`
- `Chris`/`Chris S` → `Francis`
- `Nora`/`Nora N` → `Nova`

### Date Handling
- **Tickets**: Input format DDMMYYYY (e.g., `22072025`), CDT→ADT timezone conversion (+1 hour)
- **Chats**: UTC timestamps from LiveChat exports, converted to ADT for local analysis
- **Weekend Detection**: Friday 7PM+ through Monday 6AM using `config/schedule.yaml`
- **Date Range Validation**: Monday requirement for weekly analysis across both data types

### Chat-Specific Processing
- **Bot Detection**: `Wynn AI` (sales bot), `Agent Scrape` (support bot - formerly Traject Data Customer Support)
- **Bot Transfer Detection**: Uses `chatbot-transfer` tags and secondary agent fields
- **Satisfaction Analysis**: "rated good" (5), "rated bad" (1), excludes "not rated"
- **Volume Metrics**: Daily/weekly chat trends, hourly distribution, geographic analysis

## File Structure Patterns

### Data Organization
```
tickets/          # Support ticket CSV exports
chats/            # LiveChat CSV exports  
uploads/          # User-uploaded CSV files (web interface)
results/          # Generated dashboards (timestamped directories)
config/           # Configuration files (schedule.yaml)
```

### Output Structure
Results saved in `./results/YYYY-MM-DD_HH-MM-SS/`:
- `index.html` - Navigation dashboard
- `ticket_analytics_dashboard.html` - Ticket dashboard (if ticket analysis)
- `chat_analytics_dashboard.html` - Chat dashboard (if chat analysis)  
- `ticket_analytics_summary.txt` - Ticket analysis text summary
- `chat_analytics_summary.txt` - Chat analysis text summary
- `tickets_transformed.csv` - Processed ticket data export
- `chats_transformed.csv` - Processed chat data export

## Chart Mode Configuration

The system supports dynamic chart rendering with enhanced font sizes (~10% larger than default):

```python
from common_utils import set_chart_mode
set_chart_mode('interactive')  # Use Plotly
set_chart_mode('static')       # Use matplotlib
```

Interactive mode requires `plotly` package; system automatically falls back to static mode if unavailable.

## Chat Analytics Features

### Weekly Chat Volume & Satisfaction Charts
- **12 Weeks Display**: Both weekly charts show 12 weeks of data (expanded from 8 weeks)
- **Full Width Layout**: Weekly charts span entire page width for better visibility
- **Trend Lines**: Interactive trend analysis overlays on weekly data
- **Bot Focus**: Weekly satisfaction chart shows only bot performance data

### Bot Performance Analysis
- **Individual Bot Metrics**: Separate analysis for `Wynn AI` (sales) and `Agent Scrape` (support)
- **Satisfaction Tracking**: Good/bad rating percentages (excludes "not rated")
- **Combined Bot Overview**: Overall bot performance comparison
- **Volume Analysis**: Bot chat volumes and resolution rates

### Human Agent Analysis  
- **Agent Performance**: Individual analysis for `Bhushan`, `Girly`, `Francis`, `Nova`
- **Transfer Metrics**: Chats transferred from bots to each human agent
- **Satisfaction Ratings**: Human agent satisfaction compared to bots
- **Response Times**: Average response times for human agents

### Transfer Analysis
- **Bot-to-Human Rate**: Percentage of chats escalated from bot to human
- **Daily Transfer Trends**: Transfer rate changes over time
- **Bot Resolution Rate**: Chats successfully resolved by bots alone
- **Transfer Detection**: Automatic identification via `chatbot-transfer` tags

### Volume & Trend Analysis
- **Daily Chat Volume**: Line charts showing chat trends over time
- **Weekly Totals**: Bar charts for weekly volume analysis with trend indicators
- **Hourly Distribution**: Chat volume patterns by hour of day
- **Geographic Analysis**: Top countries by chat volume
- **Peak Detection**: Identifies busiest periods and usage patterns

### Dashboard Features
- **Agent Performance Table**: Comprehensive comparison of all agents (bots + humans)
- **Interactive Charts**: Plotly-based visualizations with drill-down capabilities
- **Satisfaction Comparison**: Side-by-side bot vs human satisfaction analysis
- **Transfer Flow Visualization**: Bot-to-human escalation patterns

## Ticket Analytics Features

### Daily Ticket Volume Chart
- **Daily Breakdown**: Bar chart showing daily ticket counts over time
- **Interactive Display**: Hover details and responsive design
- **Volume Tracking**: Identifies peak days and volume patterns

### Weekly Response Time Analysis
- **Historical Tracking**: Shows 35+ weeks of response time data from start of 2025
- **Mean-Based Calculations**: Uses average response times for consistency with previous behavior
- **Multiple Categories**: All tickets, weekday-only, weekend-only analysis
- **Interactive Controls**: Toggle visibility of different categories and trend lines
- **Time Range Selection**: All weeks, last 12 weeks, last 8 weeks options
- **Trend Analysis**: Linear regression trend lines for performance tracking

### Agent Performance Analysis
- **Individual Metrics**: Performance breakdown by agent (`Girly`, `Francis`, `Bhushan`, `Nova`)
- **Response Time Comparison**: Average and median response times per agent
- **Volume Distribution**: Ticket counts and percentages per agent
- **Pipeline Breakdown**: Ticket distribution across different support pipelines

## Export Capabilities

### Dashboard Export Options
- **PNG Export**: High-quality image export for presentations
- **PDF Export**: Multi-page PDF reports with charts and tables
- **Google Docs Integration**: Direct upload to Google Docs for collaborative editing
- **Google Docs Setup**: Requires `GOOGLE_DOCS_SETUP.md` configuration

## Development Notes

- **Modular Design**: Clean separation of concerns with focused ticket and chat processing
- **Error Resilience**: Graceful handling of missing files and malformed data
- **Performance**: Efficient CSV processing with progress indicators for large datasets
- **SPAM Filtering**: Automatic exclusion of "SPAM Tickets" pipeline data
- **Multi-Agent Analytics**: Comprehensive performance tracking across tickets and chats
- **Timezone Consistency**: Unified ADT timezone for all analytics (tickets: CDT→ADT +1h, chats: UTC→ADT)
- **Font Enhancement**: All chart text and labels increased by ~10% for better readability
- **Full Width Charts**: Weekly chat charts positioned outside grid system for maximum visibility
- **Real Name Usage**: All analytics consistently show agent real names regardless of source data format

## Recent Updates (August 2025)

- **Restored Daily Volume Chart**: Added back daily ticket volume visualization
- **Response Time Calculation**: Reverted to mean-based calculations for consistency with historical data
- **Font Size Enhancement**: Increased all chart text by ~10% across dashboards
- **Agent Name Consistency**: Comprehensive mapping ensures real names appear in all analytics
- **Chat Analytics Enhancement**: Added 12-week display with trend lines for weekly charts
- **Full Width Layout**: Weekly chat charts now span entire page width
- **Bot Performance Focus**: Weekly satisfaction charts show only bot data for clarity