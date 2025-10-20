# Architect Mode - Non-Obvious Architecture Constraints

## Critical Architectural Decisions (Non-Standard)

### Data Flow Architecture (Counterintuitive)
- **Firestore is primary data source** - NOT Google Sheets (despite extensive Sheets documentation)
- **Google Sheets is export target only** - one-way data flow: APIs → Firestore → Sheets (see [`export_firestore_to_sheets.py`](../../export_firestore_to_sheets.py:1))
- **CSV files are fallback/backup** - `tickets/` and `chats/` directories used only when Firestore unavailable

### Hidden Coupling & Dependencies
- **Dashboard logic duplicated** - metric calculations exist in processors AND [`enhanced_query_engine.py:49`](../../enhanced_query_engine.py:49) hardcoded dict
- **Timezone conversion chain** - tickets: HubSpot CDT → `US/Eastern` → ADT; chats: LiveChat UTC → ADT (see [`data_sync_service.py:298`](../../data_sync_service.py:298))
- **Agent name standardization** - happens in processors, downstream code assumes already mapped (Shan→Bhushan, Chris→Francis, etc.)

### Non-Obvious Performance Constraints
- **Conversation context limited to 5 exchanges** - AI query engine truncates history (see [`enhanced_query_engine.py:573`](../../enhanced_query_engine.py:573))
- **Firestore logging 7-day retention** - automatic cleanup prevents unbounded growth (see [`start_ui.py:76`](../../start_ui.py:76))
- **Schema-only AI approach** - raw customer data NEVER sent to AI APIs, only table structures and aggregates

### Security & Access Patterns
- **Admin routes disabled by default** - require `ADMIN_PASSWORD` env var, default `admin123` if set
- **Widget CSP includes HubSpot domains** - frame-ancestors configured for embedding (see [`app.py:80`](../../app.py:80))
- **Five secrets required for Cloud Run** - `GOOGLE_SHEETS_SPREADSHEET_ID`, `HUBSPOT_API_KEY`, `LIVECHAT_PAT`, `GEMINI_API_KEY`, plus credentials JSON

### Data Processing Constraints (Must Follow)
- **Manager tickets auto-excluded** - Richie filtered in processors, analytics assumes only support team (Bhushan, Girly, Nova, Francis)
- **SPAM pipeline auto-excluded** - ID `95947431` filtered silently, no user control
- **Weekend boundaries non-standard** - Friday 6PM to Monday 5AM EDT, NOT midnight-based (see [`config/schedule.yaml`](../../config/schedule.yaml:1))
- **Overnight shifts supported** - schedule.yaml allows `end < start` times (e.g., 19:00-05:00)

### Testing Architecture
- **Executable scripts, not pytest** - tests run directly: `python test_*.py`
- **HTML output for visual verification** - tests write artifacts for manual review
- **CSV fixtures required** - tests exit early if source data missing

### Deployment Architecture
- **Cloud Run with mounted secrets** - credentials as volume mounts, not env vars (see [`Makefile:54`](../../Makefile:54))
- **Port from environment** - Cloud Run sets `PORT`, defaults to 5000 locally
- **Production detection** - `FLASK_ENV=production` changes server behavior