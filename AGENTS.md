# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Critical Timezone Gotchas
- **Tickets MUST use `US/Eastern`**, NOT `Canada/Atlantic`, despite both being Atlantic timezone (see [`common_utils.py:60`](common_utils.py:60))
- **Chats use UTC→ADT conversion** in [`data_sync_service.py`](data_sync_service.py:298)
- **Weekend boundaries are 6PM Friday to 5AM Monday EDT**, not midnight (see [`config/schedule.yaml`](config/schedule.yaml:1))
- [`app.py`](app.py:417) enforces `US/Eastern` for date filtering - replicating this in other modules is critical

## Agent Name Mapping (Non-Standard)
Real names appear in analytics, but source data has multiple pseudonyms requiring mapping:
- `Shan`/`Shan D` → `Bhushan`
- `Chris`/`Chris S` → `Francis`  
- `Nora`/`Nora N` → `Nova`
- `Gillie`/`Gillie E`/`Girly E` → `Girly`
- **Manager (Richie) tickets are auto-excluded** - only Bhushan, Girly, Nova, Francis analyzed

## Data Processing Gotchas
- **Invalid dates must use `errors='coerce'`** - chat data contains "Unknown" strings causing NaT comparison errors (see [`chat_processor.py`](chat_processor.py:1))
- **SPAM pipeline (ID `95947431`) is auto-excluded** from all ticket analytics
- **Overnight shifts supported** in schedule.yaml when `end < start` (e.g., 19:00-05:00)
- **Negative response times are invalid** - treat as None/exclude

## Firestore Architecture (Oct 2025)
- **Primary data source is Firestore**, NOT Google Sheets (despite CLAUDE.md references)
- [`firestore_db.py`](firestore_db.py:1) provides `get_tickets()` and `get_chats()` - use these, not direct CSV access
- **Widgets use Firestore** via [`firestore_db.get_database()`](firestore_db.py:1), fallback to CSV only if Firestore unavailable
- **Google Sheets is export target**, not source (via [`export_firestore_to_sheets.py`](export_firestore_to_sheets.py:1))

## Deployment Commands (Non-Standard)
- **Cloud Run requires 5 env vars** as mounted secrets: `GOOGLE_SHEETS_SPREADSHEET_ID`, `HUBSPOT_API_KEY`, `LIVECHAT_PAT`, `GEMINI_API_KEY`, plus credentials JSON (see [`Makefile:54`](Makefile:54))
- **Admin password defaults to `admin123`** if `ADMIN_PASSWORD` not set - admin routes disabled without it
- **Firestore logging uses 7-day retention** by default (see [`start_ui.py:76`](start_ui.py:76))

## AI Query Engine Context
- [`enhanced_query_engine.py`](enhanced_query_engine.py:49) loads dashboard logic from hardcoded dict - when changing metric calculations, **update both processor AND query engine dashboard_logic**
- **Conversation context limited to last 5 exchanges** (see [`enhanced_query_engine.py:573`](enhanced_query_engine.py:573))
- **Schema-only approach** - never send raw customer data to AI APIs

## Testing Pattern
Tests are **executable Python scripts** (not pytest), run directly: `python test_agent_performance_enhancements.py`. They write HTML output to review visually, exit early if CSV fixtures missing.

## Widget Security
- **CSP frame-ancestors includes HubSpot domains by default** (see [`app.py:80`](app.py:80))
- Widgets use `interactive_widget_base.html` for time-range filtering, `widget_base.html` for static charts
