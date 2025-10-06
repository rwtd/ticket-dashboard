# 🚀 Hybrid Support Analytics Platform with Conversational AI

A revolutionary support analytics platform that combines traditional dashboards with conversational AI for instant data insights. Query your support data in natural language and get intelligent responses with context and follow-up suggestions.

## ✨ Key Breakthrough: Conversational Query Engine

**Natural Language → SQL → Insights** powered by DuckDB + Gemini AI

```
🧠 "For the last 35 days, what was the average response time?"
→ "Your 35-day average is 2.1 hours, which is excellent! This includes timezone conversion from CDT to ADT. Weekend responses averaged 3.2 hours vs 1.9 hours on weekdays, which aligns with your reduced staffing schedule."

🧠 "Which agent handled the most tickets this quarter?"
→ "Nova leads this quarter with 487 tickets (38% of total). Her average response time of 1.8 hours is 15% faster than the team average. Would you like to see monthly breakdowns or compare to last quarter?"
```

## 🏗️ Hybrid Architecture

- **👥 Humans** → Google Sheets (collaboration, manual analysis)
- **🤖 AI** → DuckDB + Gemini (instant queries, conversation memory)
- **🔒 Privacy-First** → All data stays local, only schema sent to AI

## 🚀 Quick Start

### Web UI with AI Assistant (Recommended)
```bash
# Install dependencies
pip install -r requirements.txt

# Configure API credentials (optional, for automated data sync)
export HUBSPOT_API_KEY="your_hubspot_token"
export LIVECHAT_PAT="your_livechat_token"
export GOOGLE_SHEETS_SPREADSHEET_ID="your_sheet_id"

# Start web interface
python start_ui.py
# Access at http://localhost:5000

# Features:
# - 🤖 AI-Powered Analysis - Chat with your data
# - 📊 Traditional Dashboards - Visual analytics
# - 🔧 Admin Panel (/admin) - Manage API sync and configuration
# - 🌺 Widget Garden (/widgets) - Embeddable analytics for external platforms
```

### Traditional Analytics
```bash
# Run ticket analytics (auto-detect data sources)
python ticket_analytics.py

# Date-specific analysis  
python ticket_analytics.py --week 22072025      # Weekly (Monday-Sunday)
python ticket_analytics.py --day 22072025       # Single day
python ticket_analytics.py --custom 15072025-22072025  # Date range
```

## 🎯 Revolutionary Features

### 🔄 Automated Data Pipeline (NEW)
- **API Integration** - Direct sync from HubSpot and LiveChat APIs
- **Incremental Sync** - Only fetches new/modified data after initial load
- **Google Sheets Hub** - Single source of truth for all analytics
- **Admin Interface** - Web-based configuration and sync management
- **Test Utilities** - Quick validation scripts for API connections
- **Scheduled Sync** - Configurable intervals (1-24 hours)
- **Smart Filtering** - Automatically excludes manager tickets, only shows support team
- **Pipeline Mapping** - Converts numeric IDs to readable labels via HubSpot API

### 🧠 Enhanced Conversational AI Query Engine (`enhanced_query_engine.py`)
- **Natural Time Queries** - "Last 35 days", "this quarter", "past 6 months"
- **Google Sheets Integration** - Access complete historical data, not just recent CSVs
- **Dashboard Logic Awareness** - Understands exactly how your metrics are calculated
- **Context Memory** - Remembers previous conversation for intelligent follow-ups
- **Real-time SQL Generation** - Gemini converts questions to optimized DuckDB queries
- **Privacy-First** - Only table schemas sent to AI, never actual data

### 💬 Persistent Conversation System (`conversation_manager.py`)
- **Session Persistence** - Conversations survive browser refreshes and server restarts
- **Context Restoration** - Automatically restores conversation history on return
- **Conversation Management** - Start new chats, clear current conversation, view history
- **JSONL Storage** - Efficient append-only conversation storage with automatic cleanup
- **Statistics Tracking** - Monitor conversation usage, activity, and engagement metrics

### 📊 Traditional Analytics Suite
- **📋 Ticket Analytics** - Response times, agent performance, volume trends
- **💬 Chat Analytics** - Bot satisfaction, transfer rates, volume analysis  
- **📊 Combined Analytics** - Unified ticket + chat dashboard
- **📈 Agent Performance** - Cross-agent comparison with multiple time periods
- **👤 Individual Agent** - Agent vs team benchmarking

### 🔄 Data Processing Engine
- **Direct CSV Querying** - DuckDB processes files without migration
- **Timezone Conversion** - CDT→ADT (+1 hour) for tickets, UTC→ADT for chats
- **Agent Name Standardization** - Consistent real names across all analytics (Girly, Bhushan, Francis, Nova)
- **Manager Filtering** - Automatically excludes manager tickets (Richie) - only support team included
- **Weekend Detection** - Friday 7PM+ through Monday 6AM using configurable schedules
- **Pipeline Mapping** - Automatic conversion of pipeline IDs to readable labels (11 pipelines supported)
- **Robust Error Handling** - Gracefully handles "Unknown" dates, NaT values, and invalid data

### 🌐 Export & Integration
- **Google Sheets Sync** - Real-time export with automatic sheet creation
- **Multi-format Export** - PNG, PDF, Google Docs with professional formatting
- **Google OAuth** - Secure authentication for Docs/Slides API access ([Setup Guide](OAUTH_QUICK_START.md))
- **Widget Garden** - Embeddable analytics widgets for external platforms (HubSpot, etc.)
- **Auto-monitoring** - File watching with configurable sync intervals
- **Processing Logs** - Real-time status tracking and error monitoring

## 🎯 AI Assistant Examples

### Response Time Analysis
```
🧠 "What are the average response times?"
→ Analyzes all response time columns, converts HH:mm:ss to hours
→ Shows performance ratings and agent-specific breakdowns
```

### Agent Performance
```  
🧠 "Which agent handles the most tickets?"
→ Real-time analysis of all 3,289 tickets
→ Shows counts, percentages, and suggests follow-up questions
```

### Time-based Analysis
```
🧠 "Show me ticket volume by month"
→ Generates monthly breakdown with trends
→ Suggests seasonal analysis and peak period identification
```

### Smart Search
```
🧠 "Find tickets about billing issues"
→ Searches across all text fields
→ Returns relevant results with context
```

## 🏗️ Architecture Components

### API Data Pipeline (NEW)
- **`data_sync_service.py`** - Orchestrates automated API fetching and sync
- **`hubspot_fetcher.py`** - HubSpot CRM API v3 client with pagination
- **`livechat_fetcher.py`** - LiveChat API v3.5 client with thread parsing
- **`google_sheets_data_source.py`** - Unified data access layer
- **`admin_routes.py`** - Web-based admin interface for configuration
- **`test_hubspot_connection.py`** - Quick API validation utility

### Core AI Engine
- **`query_engine.py`** - Conversational AI with DuckDB + Gemini integration
- **`conversation_manager.py`** - Persistent conversation history and context management
- **`app.py`** - Flask web application with integrated chat interface
- **`processing_logger.py`** - Real-time logging and Google Sheets sync tracking

### Traditional Analytics
- **`ticket_processor.py`** - Support ticket processing with timezone conversion
- **`chat_processor.py`** - LiveChat analysis with bot performance tracking
- **`dashboard_builder.py`** - Interactive HTML dashboard generation
- **`google_sheets_exporter.py`** - Automated Google Sheets integration

### Specialized Analyzers
- **`agent_performance_analyzer.py`** - Cross-agent performance comparison
- **`individual_agent_analyzer.py`** - Individual vs team benchmarking
- **Auto-sync monitoring** - Real-time file watching and export automation

## 📊 Sample AI Conversations

### Performance Analysis
```
User: "How are our response times looking?"
AI: "Your average response time is 2.1 hours, which is excellent! Girly leads with 1.8 hours average. Would you like me to break this down by ticket type or compare weekend vs weekday performance?"

User: "Show me weekend performance"  
AI: "Weekend response times average 3.2 hours vs 1.9 hours on weekdays. This is expected given reduced staffing. Should I show you which agents cover weekends or analyze weekend ticket volume patterns?"
```

### Volume Analysis
```
User: "Are we getting busier?"
AI: "Yes! Your ticket volume has increased 23% over the past 3 months. September shows 847 tickets vs 651 in June. Would you like me to identify the main drivers of this increase or show staffing recommendations?"
```

## 🔧 Configuration

### API Data Pipeline
```bash
# HubSpot (Private App token from Settings → Integrations → Private Apps)
export HUBSPOT_API_KEY="your_hubspot_token"

# LiveChat (Personal Access Token or username:password)
export LIVECHAT_PAT="your_livechat_token"

# Google Sheets (service account credentials and spreadsheet ID)
export GOOGLE_SHEETS_SPREADSHEET_ID="your_sheet_id"
export GOOGLE_SHEETS_CREDENTIALS_PATH="service_account_credentials.json"

# Sync settings (optional)
export DATA_SYNC_INTERVAL_HOURS=4  # Default: 4 hours
export DATA_RETENTION_DAYS=365     # Default: 365 days

# Admin interface password (change in production!)
export ADMIN_PASSWORD="your_secure_password"
```

### AI Configuration
```bash
# Google Gemini API key for conversational AI
export GEMINI_API_KEY="your-gemini-key-here"
```

### Schedule Configuration (`config/schedule.yaml`)
```yaml
weekend_start: "Friday 19:00"
weekend_end: "Monday 06:00" 
agents:
  - name: "Girly"
    schedule: "Monday-Friday 9AM-5PM"
```

## 🚀 Advanced Usage

### Conversational AI Sessions
- **Memory Retention** - Remembers last 5 conversation exchanges with persistent storage
- **Context Awareness** - Understands references to previous queries across sessions
- **Smart Suggestions** - Proposes relevant follow-up analysis based on conversation history
- **Session Management** - Start new conversations, clear current chat, browse history
- **Automatic Persistence** - Conversations survive browser refreshes and server restarts

### Traditional Dashboards
- **Interactive Charts** - Plotly-based with matplotlib fallback
- **Export Options** - PNG, PDF, Google Docs with professional formatting
- **Real-time Sync** - Automatic Google Sheets integration
- **Multi-format Analysis** - Tickets, chats, combined analytics

## 📁 Output Structure
```
results/YYYY-MM-DD_HH-MM-SS/
├── index.html                          # Navigation dashboard
├── *_analytics_dashboard.html          # Interactive dashboards
├── *_analytics_summary.txt             # AI-generated summaries
├── *_transformed.csv                   # Processed data exports
└── exports/                            # Multi-format exports
```

## 🎯 Production Ready

- **Enterprise Security** - Local data processing, approved AI providers only
- **Scalable Architecture** - Handles 4,700+ tickets, 4,400+ chats, 320+ columns
- **Real-time Processing** - Instant query responses with conversation memory
- **Automated Data Pipeline** - API-based sync eliminates manual CSV exports
- **Team Collaboration** - Google Sheets integration for manual workflows
- **Admin Interface** - Web-based configuration and sync management
- **Incremental Sync** - Efficient updates with rate limiting and state tracking
- **Comprehensive Testing** - Built-in test utilities for API validation
- **Smart Data Filtering** - Automatic manager exclusion and pipeline mapping
- **Error Resilience** - Graceful handling of invalid data and edge cases
- **Widget Embeds** - Secure iframe support for external platforms with CSP headers

## 🚀 Quick Start Guide

### 1. Basic Setup (No API Integration)
```bash
pip install -r requirements.txt
python start_ui.py
# Upload CSV files via web interface
```

### 2. API Integration (Automated Sync)
```bash
# Configure credentials
export HUBSPOT_API_KEY="your_token"
export LIVECHAT_PAT="your_token"
export GOOGLE_SHEETS_SPREADSHEET_ID="your_sheet_id"

# Test connections
python test_hubspot_connection.py
python data_sync_service.py --test

# Run initial sync
python data_sync_service.py --full

# Start dashboard with automated data
python start_ui.py
```

### 3. Google OAuth Setup (For Docs/Slides Export)
```bash
# Quick setup (5 minutes)
python setup_google_oauth.py

# This will guide you through:
# 1. Enabling APIs (Docs, Drive, Slides)
# 2. Creating OAuth client credentials
# 3. Configuring redirect URI: http://localhost:9090/
# 4. Testing authentication flow

# See OAUTH_QUICK_START.md for details
```

### 4. Admin Interface
```bash
# Access admin panel at http://localhost:5000/admin
# Default password: admin123 (change via ADMIN_PASSWORD env var)

# Features:
# - Configure API credentials (HubSpot, LiveChat, Google Sheets)
# - Show/Hide toggle for credential viewing
# - Test connections to verify setup
# - Trigger manual syncs (full or incremental)
# - View sync logs and status
# - Data status dashboard (compare Sheets vs local CSVs)
# - Manage all settings via web interface

# See ADMIN_PANEL_GUIDE.md for detailed configuration instructions
```

### 5. Widget Garden
```bash
# Access widget gallery at http://localhost:5000/widgets

# Features:
# - Browse available embeddable widgets
# - Copy iframe embed code
# - Secure CSP headers for external embedding
# - Pre-configured for HubSpot, custom platforms
# - Vertical layout for easy browsing
# - Test widgets before deploying
```

## 📚 Documentation

- **[OAUTH_QUICK_START.md](OAUTH_QUICK_START.md)** - 5-minute Google OAuth setup for Docs/Slides export ⚡
- **[GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)** - Complete OAuth configuration guide with troubleshooting
- **[ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md)** - Complete admin interface setup and configuration guide
- **[API_ACCESS_REQUIREMENTS.md](API_ACCESS_REQUIREMENTS.md)** - How to obtain API credentials from HubSpot and LiveChat
- **[CLAUDE.md](CLAUDE.md)** - Developer reference with commands and architecture details
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical architecture and implementation overview
- **[CLOUD_RUN_DEPLOYMENT_GUIDE.md](CLOUD_RUN_DEPLOYMENT_GUIDE.md)** - Production deployment instructions

**Ready for production deployment with conversational AI and automated data pipeline!** 🎯