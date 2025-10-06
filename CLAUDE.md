# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Web UI (Primary Interface)
```bash
# Install dependencies
pip install -r requirements.txt

# Start web interface (recommended)
python start_ui.py
# Access at http://localhost:5000 (or 5001 if port conflict)

# Run Flask app directly (development)
python app.py

# Environment variables for AI features
export GEMINI_API_KEY="your-api-key"  # Required for AI-powered analysis
export GOOGLE_SHEETS_CREDENTIALS_PATH="path/to/credentials.json"  # For Sheets integration
export GOOGLE_SHEETS_SPREADSHEET_ID="your_spreadsheet_id"  # Primary data source
```

### API-Based Data Pipeline (NEW)
```bash
# Set up API credentials (see API_ACCESS_REQUIREMENTS.md for obtaining these)
export HUBSPOT_API_KEY="your_hubspot_private_app_token"
export LIVECHAT_PAT="your_livechat_personal_access_token"  # Or username:password format
export GOOGLE_SHEETS_SPREADSHEET_ID="your_spreadsheet_id"
export GOOGLE_SHEETS_CREDENTIALS_PATH="path/to/service_account_credentials.json"

# Test HubSpot connection specifically
python test_hubspot_connection.py  # Validates auth, fetches sample tickets

# Test all API connections
python data_sync_service.py --test

# Run initial full sync (fetch last 365 days from APIs)
python data_sync_service.py --full

# Run incremental sync (fetch only new/updated data)
python data_sync_service.py --incremental

# Test individual API fetchers
python hubspot_fetcher.py  # Uses HUBSPOT_API_KEY env var
python livechat_fetcher.py  # Uses LIVECHAT_PAT env var

# Test Google Sheets data source
python google_sheets_data_source.py
```

### Admin Interface
```bash
# Start the web UI to access admin panel
python start_ui.py

# Navigate to http://localhost:5000/admin
# Default password: admin123 (set ADMIN_PASSWORD env var to change)

# Features:
# - Dashboard with sync status
# - Test API connections
# - Manual sync triggers (full/incremental)
# - Configuration editor with Show/Hide for credentials
# - Sync logs viewing

# See ADMIN_PANEL_GUIDE.md for detailed setup instructions
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

### Testing & Validation
```bash
# Test core functionality
python -c "from ticket_processor import TicketDataProcessor; print('✅ Ticket processor working')"

# Test agent performance enhancements
python test_agent_performance_enhancements.py
python test_enhanced_agent_performance_final.py

# Test daily ticket calculations
python test_daily_tickets.py

# Validate AI query engine (requires GEMINI_API_KEY)
python -c "from enhanced_query_engine import EnhancedSupportQueryEngine; print('✅ Query engine available')"
```

### Deployment
```bash
# Docker build and run locally
docker build -t ticket-dashboard .
docker run -p 5000:5000 -e PORT=5000 ticket-dashboard

# Cloud Run deployment (via Makefile)
make PROJECT_ID=your-project REGION=us-central1 all

# Manual Cloud Run deployment (see CLOUD_RUN_DEPLOYMENT_GUIDE.md)
gcloud run deploy ticket-dashboard --source . --region us-central1
```

### MCP Server (Model Context Protocol)
```bash
# Run MCP analytics server for AI tool integration
python mcp_analytics_server.py

# Server provides AI-accessible tools for:
# - Dataset info retrieval
# - Response time analysis
# - Agent performance queries
# - Volume trend analysis
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

### API Data Pipeline (NEW)
- **`data_sync_service.py`**: **Orchestrates automated data fetching from HubSpot and LiveChat APIs**
  - Schedules incremental sync (every 1-24 hours configurable)
  - Processes data and syncs to Google Sheets as single source of truth
  - Tracks sync state for incremental updates (stores in `sync_state.json`)
  - CLI interface: `--full`, `--incremental`, `--test`
- **`hubspot_fetcher.py`**: HubSpot Tickets API client with pagination and rate limiting
  - Fetches tickets using HubSpot CRM API v3
  - Maps API fields to CSV column format
  - Handles 100 requests/10 seconds rate limit
  - Supports incremental sync based on modification date
- **`livechat_fetcher.py`**: LiveChat API v3.5 client with chat parsing
  - Fetches chats, parses threads for metrics
  - Detects bot vs human agents and transfers
  - Handles 180 requests/minute rate limit
  - Supports incremental sync based on creation date
- **`google_sheets_data_source.py`**: **Unified data access layer for Google Sheets**
  - Used by main app, widgets, and AI engine
  - Provides cached access with 5-minute TTL
  - Supports filtering by date, agent, pipeline
  - Graceful fallback to local CSVs if unavailable
- **`test_hubspot_connection.py`**: **Quick validation script for HubSpot API setup**
  - Tests authentication and scopes
  - Fetches sample tickets and owners
  - Exports sample data for verification
  - Useful for debugging API access issues

### Admin Interface (NEW)
- **`admin_routes.py`**: Flask blueprint providing web-based admin interface
  - Dashboard with sync status and configuration overview
  - Test API connections for HubSpot, LiveChat, and Google Sheets
  - Manual sync triggers (full or incremental)
  - Configuration editor with Show/Hide toggle for credentials
  - Easy credential entry with placeholder guidance
  - Sync logs viewer for audit trail
  - Simple password authentication (set via `ADMIN_PASSWORD` env var)
  - Access at `/admin` endpoint when running web UI
  - **See [`ADMIN_PANEL_GUIDE.md`](ADMIN_PANEL_GUIDE.md:1) for complete setup guide**

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

### AI & Query Components
- **`enhanced_query_engine.py`**: AI-powered query engine with DuckDB + Gemini integration
  - Natural language → SQL translation
  - Google Sheets data integration for complete historical analysis
  - Dashboard logic awareness (understands exactly how metrics are calculated)
  - Privacy-first design (only schemas sent to AI, never raw data)
- **`conversation_manager.py`**: Persistent conversation history system
  - JSONL-based storage with automatic cleanup (30-day default retention)
  - Session restoration across browser refreshes
  - Context-aware follow-up suggestions
- **`query_engine.py`**: Base query engine with DuckDB CSV querying
- **`mcp_analytics_server.py`**: Model Context Protocol server for AI tool access
- **`customer-support-ai-analyst/`**: TypeScript/React-based AI analyst widget using Google Gemini
  - **`App.tsx`**: Main application component with chat interface
  - **`services/geminiService.ts`**: Google Gemini API integration for AI analysis
  - **`services/googleSheetsService.ts`**: Google Sheets integration for data import

### Analytics Types
- **📋 Ticket Analytics**: Support ticket analysis with response times and agent performance
- **💬 Chat Analytics**: LiveChat analysis with bot satisfaction and transfer rates
- **📊 Combined Analytics**: Unified dashboard (planned feature)
- **🤖 AI-Powered Analysis**: Google Gemini-powered chat interface for natural language data exploration

### Data Pipeline Architecture

**NEW: API-Based Automated Pipeline (Recommended)**
1. **API Fetching**: `data_sync_service.py` fetches from HubSpot + LiveChat APIs (scheduled)
2. **Processing**:
   - **Tickets**: CDT→ADT timezone conversion (+1 hour), weekend flagging, agent name standardization
   - **Chats**: UTC→ADT timezone conversion, bot/human classification, transfer detection
3. **Sync to Sheets**: Upserts to Google Sheets (rolling 365-day window)
4. **Unified Access**: All components read from Google Sheets via `google_sheets_data_source.py`
5. **Analytics Generation**: Main app, widgets, AI all use same Google Sheets data

**Legacy: CSV-Based Pipeline (Fallback)**
1. **Detection**: Scans `./tickets/` and `./chats/` directories for CSV files
2. **Validation**: Validates required columns and data formats for both ticket and chat data
3. **Processing**: Same as API pipeline (timezone conversion, agent mapping, etc.)
4. **Analytics Generation**: Calculates metrics, trends, and performance for tickets and chats
5. **Dashboard Creation**: Responsive HTML with interactive/static chart modes for unified analytics

### Configuration System
- **Chart Modes**: Set via `CHART_MODE` environment variable or `set_chart_mode()` function
  - `interactive`: Plotly-based charts (default if available)
  - `static`: matplotlib fallback charts
- **Schedule Configuration**: `config/schedule.yaml` defines agent shifts for weekend detection
  - Per-agent schedules: Nova, Girly, Bhushan, Francis
  - Weekend boundaries: Friday 6PM - Monday 5AM EDT
  - Overnight shifts supported (e.g., Francis 7PM-5AM)
- **Data Sources**: Environment variables
  - `TICKET_DATA_SOURCE`: Path to ticket CSV directory
  - `OUTPUT_DIR`: Results output directory
- **AI Configuration**: Environment variables for AI-powered features
  - `GEMINI_API_KEY`: Required for enhanced query engine (get from [Google AI Studio](https://aistudio.google.com))
  - `GOOGLE_SHEETS_CREDENTIALS_PATH`: For Sheets integration (OAuth or service account)
  - `GOOGLE_SHEETS_SPREADSHEET_ID`: **Primary data source for all analytics**
- **API Data Pipeline**: Environment variables for automated sync
  - `HUBSPOT_API_KEY`: HubSpot Private App token for tickets API (see [API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md:1))
  - `LIVECHAT_PAT`: LiveChat Personal Access Token for chats API (can be PAT token or `username:password` format)
  - `DATA_SYNC_INTERVAL_HOURS`: Sync frequency (default: 4 hours)
  - `DATA_RETENTION_DAYS`: Rolling window for Google Sheets (default: 365 days)
- **Admin Interface**: Environment variables for access control
  - `ADMIN_PASSWORD`: Password for admin interface access (default: `admin123` - change in production!)
- **Widget Security**: Environment variables for embedding
  - `WIDGETS_XFO`: X-Frame-Options header (default: SAMEORIGIN)
  - `WIDGETS_FRAME_ANCESTORS`: CSP frame-ancestors directive (default includes HubSpot domains)
  - `WIDGETS_SCRIPT_SRC`: CSP script-src directive

## Key Data Processing Logic

### Agent Classification & Filtering
- **Manager Exclusion**: Tickets from manager (Richie) are automatically filtered out - only support team tickets are included in analytics
- **Support Team**: Only includes tickets/chats from `Bhushan`, `Girly`, `Francis`, `Nova`
- **Tickets**: Staff name mapping (`Girly .` → `Girly`, `Nora N` → `Nova`) with weekend exclusion logic
- **Chats**: Bot detection (`Wynn AI`, `Agent Scrape`) vs Human agents (`Bhushan`, `Girly`, `Francis`, `Nova`)

### Agent Name Standardization
**All analytics consistently use real names:**
- `Gillie`/`Gillie E`/`Girly E` → `Girly`
- `Shan`/`Shan D` → `Bhushan`
- `Chris`/`Chris S` → `Francis`
- `Nora`/`Nora N` → `Nova`
- **Richie** (Manager) → Filtered out from all analytics

### Pipeline Mapping
**Pipeline IDs are automatically mapped to readable names via HubSpot API:**
- `0` → `Support Pipeline`
- `147307289` → `Live Chat`
- `648529801` → `Upgrades/Downgrades`
- `667370066` → `Success`
- `724973238` → `Customer Onboarding`
- `76337708` → `Dev Tickets`
- `77634704` → `Marketing, Finance`
- `803109779` → `Product Testing Requests - Enterprise`
- `803165721` → `Trial Account Requests - Enterprise`
- `95256452` → `Enterprise and VIP Tickets`
- `95947431` → `SPAM Tickets` (automatically excluded from analytics)

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
- **Invalid Date Handling**: "Unknown" date values are gracefully converted to NaT using `errors='coerce'` to prevent processing errors

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

## Development Best Practices

### Working with Data Processing
- **Test with real data**: Always validate changes against actual CSV exports from tickets/ and chats/ directories
- **Timezone awareness**: All datetime processing must account for CDT→ADT (+1h) for tickets, UTC→ADT for chats
- **Agent name mapping**: Use the standardization functions in processors to ensure consistent naming
- **Weekend detection**: Leverage `config/schedule.yaml` rather than hardcoding time boundaries
- **SPAM filtering**: Always exclude "SPAM Tickets" pipeline in ticket analytics

### Working with AI Features
- **API key management**: Never commit `GEMINI_API_KEY` to version control
- **Schema-only approach**: Ensure only table schemas are sent to AI, never raw customer data
- **Conversation limits**: Keep context window to last 5 exchanges to manage token usage
- **Error handling**: AI queries should gracefully fall back to error messages, not crash the app

### Working with Charts
- **Mode detection**: System auto-detects Plotly availability and falls back to matplotlib
- **Font sizing**: Use the 1.1x multiplier consistently for all chart text
- **Responsive design**: Test charts on mobile viewports (weekly charts use full width)
- **Interactive features**: Plotly charts should include hover details and zoom capabilities

### Adding New Analytics
1. **Processor first**: Add data transformation logic to `ticket_processor.py` or `chat_processor.py`
2. **Metrics calculation**: Implement calculations in processor, return structured data
3. **Dashboard builder**: Add visualization logic to `dashboard_builder.py`
4. **Update schema**: If adding columns, update `enhanced_query_engine.py` dashboard logic awareness
5. **Test thoroughly**: Run against sample data before deploying

### Performance Considerations
- **CSV efficiency**: Use pandas chunking for files >10MB
- **DuckDB optimization**: Index frequently queried columns when possible
- **Progress indicators**: Add for operations >5 seconds
- **Caching**: Results are timestamped in `results/` - consider reusing recent runs

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

## AI Query Engine Architecture

The enhanced query engine provides conversational AI analysis through a sophisticated pipeline:

1. **User Question** → Natural language input (e.g., "What's our average response time?")
2. **Context Loading** → Retrieves conversation history from `conversation_manager.py`
3. **Data Discovery** → Connects to Google Sheets (via API) or local CSVs (via DuckDB)
4. **Schema Analysis** → Extracts table structure, column types, sample data
5. **Prompt Engineering** → Constructs detailed prompt with:
   - Dashboard logic awareness (how metrics are calculated)
   - Schema information (columns, types)
   - Conversation context (previous exchanges)
   - Available SQL functions
6. **Gemini Translation** → AI converts question to SQL query
7. **Query Execution** → DuckDB runs query against data
8. **Response Generation** → Gemini formats results with insights
9. **Persistence** → Saves exchange to `conversations.jsonl`

Key features:
- **Privacy-first**: Only schemas/queries sent to AI, never raw customer data
- **Context-aware**: Understands references like "compare that to last month"
- **Dashboard-aligned**: Knows exactly how response times, weekends, etc. are calculated
- **Multi-source**: Can query Google Sheets (full history) or local CSV files

## Widget Integration

The system includes embeddable analytics widgets for external platforms:

- **Blueprint-based architecture**: Widgets served via Flask blueprint at root path
- **Security headers**: Configurable CSP and X-Frame-Options for safe embedding
- **HubSpot integration**: Pre-configured frame-ancestors for HubSpot CMS
- **Standalone widgets**: Independent HTML widgets in `widgets/` directory

## Quick Start: API Pipeline Setup

### Prerequisites
1. **HubSpot Private App** - Create in HubSpot Settings → Integrations → Private Apps
   - Required scopes: `crm.objects.tickets.read`, `crm.schemas.tickets.read`, `crm.objects.owners.read`
   - Copy the generated access token

2. **LiveChat Personal Access Token** - Create in LiveChat Developer Console
   - Required scopes: `chats--all:ro`, `chats--access:ro`, `agents--all:ro`
   - Copy the generated token

3. **Google Sheets** - Set up service account credentials
   - Create service account in Google Cloud Console
   - Enable Google Sheets API
   - Download credentials JSON file
   - Create a Google Sheet and note the spreadsheet ID

### Initial Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
export HUBSPOT_API_KEY="your_hubspot_private_app_token"
export LIVECHAT_USERNAME="your_livechat_client_id"
export LIVECHAT_PASSWORD="your_livechat_api_key"
export GOOGLE_SHEETS_SPREADSHEET_ID="your_spreadsheet_id"
export GOOGLE_SHEETS_CREDENTIALS_PATH="service_account_credentials.json"

# Test connections
python data_sync_service.py --test

# Run initial full sync (fetches last 365 days)
python data_sync_service.py --full

# Start the dashboard
python start_ui.py
```

See [API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md) for detailed setup instructions.

## Recent Updates (October 2025)

### Latest Improvements (October 6, 2025)
- **Manager Ticket Filtering**: Automatically excludes manager tickets (Richie) from analytics - only shows support team (Bhushan, Girly, Nova, Francis)
- **Pipeline Name Mapping**: Replaces numeric pipeline IDs with readable labels (e.g., "Customer Onboarding", "Live Chat") via HubSpot API
- **Widget Garden**: New `/widgets` endpoint with embeddable analytics widgets for external platforms (HubSpot, etc.)
- **Enhanced UI Layout**:
  - Added Widget Garden button to header with gradient styling
  - Improved widget registry with vertical stacking for better readability
  - Fixed responsive mobile layout for header buttons
- **Improved Error Handling**:
  - Graceful handling of "Unknown" date values in chat data with `errors='coerce'`
  - Fixed NaT (Not a Time) comparison errors in admin data status checks
  - Suppressed annoying pandas FutureWarning messages across the application
- **Data Status Dashboard**: Admin panel now shows comprehensive data comparison between Google Sheets and local CSV files with recommendations

### New Features (September 2025)
- **API-Based Data Pipeline**: Automated sync from HubSpot and LiveChat APIs
- **Admin Interface**: Web-based admin panel for configuration and sync management
- **Test Connection Script**: [`test_hubspot_connection.py`](test_hubspot_connection.py:1) for quick API validation
- **Incremental Sync**: Only fetches new/modified data after initial full sync
- **Sync State Tracking**: Persistent state management in `sync_state.json`
- **Google Sheets Integration**: Single source of truth for all analytics components
- **Unified Data Access**: All components (app, widgets, AI) read from Google Sheets

### Enhancements (September 2025)
- **Enhanced AI Query Engine**: Added Google Sheets integration and dashboard logic awareness
- **Persistent Conversations**: JSONL-based conversation history with session restoration
- **MCP Server**: Added Model Context Protocol server for AI tool integration
- **Widget Security**: Configurable CSP headers for safe embedding in external platforms
- **Cloud Run Deployment**: Complete Docker and GCP deployment workflows with Makefile
- **Restored Daily Volume Chart**: Added back daily ticket volume visualization
- **Response Time Calculation**: Reverted to mean-based calculations for consistency with historical data
- **Font Size Enhancement**: Increased all chart text by ~10% across dashboards
- **Agent Name Consistency**: Comprehensive mapping ensures real names appear in all analytics
- **Chat Analytics Enhancement**: Added 12-week display with trend lines for weekly charts
- **Full Width Layout**: Weekly chat charts now span entire page width
- **Bot Performance Focus**: Weekly satisfaction charts show only bot data for clarity

### API Integration Details
- **HubSpot Fetcher**: Complete API v3 client with owner mapping, pipeline mapping, and incremental sync
- **LiveChat Fetcher**: API v3.5 client with thread parsing and bot detection
- **Rate Limiting**: Automatic rate limiting to respect API quotas
- **Error Handling**: Graceful degradation with detailed logging
- **Timezone Handling**: Automatic CDT→ADT and UTC→ADT conversions
- **Data Quality**: Robust handling of invalid dates, NaT values, and missing data