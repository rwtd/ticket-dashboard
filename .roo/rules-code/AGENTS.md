# Code Mode - Non-Obvious Rules

## Critical Data Processing Patterns
- **Timezone conversion MUST match processor modules** - tickets use `US/Eastern` (NOT `Canada/Atlantic`), chats use `UTC→ADT` (see [`app.py:417`](../../app.py:417) and [`data_sync_service.py:298`](../../data_sync_service.py:298))
- **Invalid dates require `errors='coerce'`** - chat data contains "Unknown" strings that crash without this (see [`chat_processor.py`](../../chat_processor.py:1))
- **Agent name standardization happens in processors** - don't replicate mapping logic, import from [`ticket_processor.py`](../../ticket_processor.py:1) or [`chat_processor.py`](../../chat_processor.py:1)

## Non-Standard Architecture Decisions
- **Firestore is primary data source** - use [`firestore_db.get_database()`](../../firestore_db.py:1), NOT direct CSV access or Google Sheets API
- **Google Sheets is export-only** - never read from it, only write via [`export_firestore_to_sheets.py`](../../export_firestore_to_sheets.py:1)
- **Widget data access pattern** - Firestore first via `get_database()`, fallback to CSV only if Firestore fails

## Hidden Coupling & Dependencies
- **Dashboard logic dict in query engine** - when changing metric calculations in processors, MUST update [`enhanced_query_engine.py:49`](../../enhanced_query_engine.py:49) hardcoded dict
- **Manager tickets auto-excluded** - filtering happens in processors, but analytics code assumes Richie already removed
- **SPAM pipeline (95947431) auto-excluded** - processors handle this, don't filter again downstream

## File Operation Gotchas
- **CSV encoding** - always use `encoding='utf-8'` and `errors='coerce'` for date columns
- **Overnight shifts** - schedule.yaml supports `end < start` times (19:00-05:00), don't validate against midnight boundaries
- **Response time validation** - negative/zero values are invalid data, treat as None

## Testing Requirements
- **Executable scripts, not pytest** - tests are run directly: `python test_*.py`
- **HTML output for visual review** - tests write HTML artifacts to verify charts, not just assertions
- **CSV fixtures required** - tests exit early if `tickets/*.csv` or `chats/*.csv` missing