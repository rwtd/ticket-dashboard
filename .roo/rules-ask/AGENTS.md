# Ask Mode - Non-Obvious Documentation Context

## Hidden Documentation & Counterintuitive Structures

### Data Source Architecture (Counterintuitive)
- **Firestore is primary data source**, NOT Google Sheets (despite extensive Google Sheets docs in CLAUDE.md)
- **Google Sheets is export-only** - all references to "Google Sheets as data source" in docs are outdated (pre-Oct 2025)
- **CSV files are fallback only** - `tickets/` and `chats/` directories are backup, not primary source

### Misleading Naming Patterns
- **"Canada/Atlantic" vs "US/Eastern"** - both are Atlantic timezone but code MUST use `US/Eastern` for tickets (see [`common_utils.py:60`](../../common_utils.py:60))
- **"ADT" means Atlantic Daylight Time** - but implementation uses multiple timezone conversions (CDT→ADT for tickets, UTC→ADT for chats)
- **"Weekend" means Friday 6PM - Monday 5AM** - NOT Saturday-Sunday (see [`config/schedule.yaml`](../../config/schedule.yaml:1))

### Important Context Not Evident from File Structure
- **Manager tickets excluded** - Richie's tickets automatically filtered, only support team (Bhushan, Girly, Nova, Francis) analyzed
- **Agent name mapping** - source data uses pseudonyms (Shan, Chris, Nora, Gillie) that get standardized to real names
- **SPAM pipeline auto-excluded** - pipeline ID `95947431` never appears in analytics, no user control

### Non-Obvious Module Relationships
- **Dashboard logic lives in two places** - processors calculate metrics AND [`enhanced_query_engine.py:49`](../../enhanced_query_engine.py:49) has hardcoded dict explaining calculations
- **Conversation context limited** - AI query engine only keeps last 5 exchanges (see [`enhanced_query_engine.py:573`](../../enhanced_query_engine.py:573))
- **Schema-only AI approach** - raw customer data NEVER sent to AI APIs, only table structures

### Testing & Validation Context
- **Tests are executable scripts** - NOT pytest framework, run directly: `python test_*.py`
- **HTML output for verification** - tests write visual artifacts, not just pass/fail
- **CSV fixtures required** - tests exit early if source data missing from `tickets/` or `chats/`

### Deployment Context
- **Five environment variables required** - `GOOGLE_SHEETS_SPREADSHEET_ID`, `HUBSPOT_API_KEY`, `LIVECHAT_PAT`, `GEMINI_API_KEY`, plus credentials JSON (see [`Makefile:54`](../../Makefile:54))
- **Admin password defaults** - `admin123` if `ADMIN_PASSWORD` not set, admin routes disabled without it
- **Firestore logging retention** - 7 days by default (see [`start_ui.py:76`](../../start_ui.py:76))