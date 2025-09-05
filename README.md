# 🚀 Hybrid Support Analytics Platform with Conversational AI

A revolutionary support analytics platform that combines traditional dashboards with conversational AI for instant data insights. Query your support data in natural language and get intelligent responses with context and follow-up suggestions.

## ✨ Key Breakthrough: Conversational Query Engine

**Natural Language → SQL → Insights** powered by DuckDB + Gemini AI

```
🧠 "Which agent handles the most tickets?"
→ "Nora N is your top performer with 1,240 tickets! Would you like to see how this breaks down by time period?"

🧠 "What time period?" 
→ "Your data spans from September 2024 to September 2025. Would you like me to show monthly trends or compare seasonal patterns?"
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

# Start web interface
python start_ui.py
# Access at http://localhost:5000

# Click "🤖 AI-Powered Analysis" and start chatting with your data!
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

### 🧠 Conversational AI Query Engine (`query_engine.py`)
- **Natural Language Processing** - Ask questions in plain English
- **Context Memory** - Remembers previous conversation for follow-ups
- **Smart Follow-ups** - Suggests deeper analysis and related questions
- **Real-time SQL Generation** - Gemini converts questions to DuckDB queries
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
- **Agent Name Standardization** - Consistent real names across all analytics
- **Weekend Detection** - Friday 7PM+ through Monday 6AM using configurable schedules

### 🌐 Export & Integration
- **Google Sheets Sync** - Real-time export with automatic sheet creation
- **Multi-format Export** - PNG, PDF, Google Docs with professional formatting
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

### AI Configuration
```python
# Uses your existing Gemini API key
GEMINI_API_KEY = "your-key-here"
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
- **Scalable Architecture** - Handles 3,289+ tickets, 2,203+ chats, 320+ columns
- **Real-time Processing** - Instant query responses with conversation memory
- **Team Collaboration** - Google Sheets integration for manual workflows
- **Automated Monitoring** - File watching, sync status, error tracking

**Ready for production deployment with conversational AI that understands your support data like a human analyst!** 🎯