# Debug Mode - Non-Obvious Rules

## Critical Debugging Context

### Data Pipeline Debugging
- **Firestore connection issues** - if widgets show no data, check Firestore connectivity BEFORE assuming CSV fallback works (see [`firestore_db.py`](../../firestore_db.py:1))
- **Empty widget charts** - likely date filtering mismatch between data timezone (ADT) and filter timezone (`US/Eastern`) - see [`app.py:417`](../../app.py:417)
- **Pipeline ID vs name display** - widgets show numeric IDs when pipeline mapping not loaded from HubSpot API (see [`hubspot_fetcher.py`](../../hubspot_fetcher.py:1) `fetch_pipelines()`)

### Timezone Debugging Gotchas
- **NaT comparison errors** - chat data with "Unknown" dates crashes without `errors='coerce'` (see [`chat_processor.py`](../../chat_processor.py:1))
- **Weekend detection failures** - schedule.yaml uses 6PM-5AM boundaries, NOT midnight (see [`config/schedule.yaml`](../../config/schedule.yaml:1))
- **Timezone mismatch symptoms** - if ticket counts differ by 1 day, check `US/Eastern` vs `Canada/Atlantic` usage

### Hidden Log Locations
- **Firestore logs** - 7-day retention in Firestore `logs` collection, access via admin panel `/admin/logs/recent`
- **Start-up logging** - [`start_ui.py:76`](../../start_ui.py:76) initializes Firestore logger, check console output
- **Admin panel logs** - `/admin` requires `ADMIN_PASSWORD` env var (defaults to `admin123`)

### Silent Failure Points
- **Manager ticket exclusion** - Richie tickets filtered silently in processors, appears as "missing" data
- **SPAM pipeline exclusion** - pipeline ID `95947431` auto-filtered, no error messages
- **Negative response times** - treated as None/excluded silently, check source data validity

### Widget-Specific Debug Patterns
- **Interactive widgets need time-range buttons** - use `interactive_widget_base.html`, not `widget_base.html` (see [`widgets/routes.py:168`](../../widgets/routes.py:168))
- **Empty charts** - check date column exists in data, verify timezone conversion applied
- **Pipeline IDs instead of names** - HubSpot API mapping not loaded, check `HUBSPOT_API_KEY` env var