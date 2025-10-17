# Firestore Logging System Guide

## Overview

The application now logs all application events to Firestore instead of relying on ephemeral console logs. This provides:

- **Persistent logs** that survive container restarts
- **Queryable logs** via the admin interface
- **Automatic cleanup** with 7-day retention by default
- **Structured logging** with timestamps, levels, and metadata

## Architecture

```
Application Logs → FirestoreLogHandler → Firestore Collection
                                              ↓
                                    Admin Interface Query
```

## Setup

### Automatic Setup

Firestore logging is automatically enabled when you start the application:

```bash
python start_ui.py
```

You'll see: `📝 Firestore logging enabled (7-day retention)`

### Manual Setup

To enable Firestore logging in your own scripts:

```python
from firestore_logger import setup_firestore_logging
import logging

# Enable Firestore logging
setup_firestore_logging(level=logging.INFO)

# Use logging as normal
logger = logging.getLogger(__name__)
logger.info("This will be stored in Firestore")
logger.warning("And so will this")
logger.error("And this too")
```

## Firestore Collection Structure

Logs are stored in the `application_logs` collection with the following schema:

```json
{
  "timestamp": "2025-10-16T13:35:00.000Z",
  "level": "INFO",
  "logger": "app",
  "message": "Server started successfully",
  "module": "app",
  "function": "main",
  "line": 123,
  "thread": 12345,
  "thread_name": "MainThread",
  "exception": "Full traceback if exception occurred"
}
```

## Admin Interface

### View Recent Logs

The admin interface provides endpoints for viewing logs:

**GET `/admin/logs/recent`**
- Returns logs from the last 24 hours
- Limit: 500 entries
- Sorted: Most recent first

Example response:
```json
{
  "status": "success",
  "logs": [
    {
      "timestamp": "2025-10-16T13:35:00.000Z",
      "level": "INFO",
      "message": "Server started",
      "module": "app",
      "function": "main",
      "line": 123
    }
  ],
  "count": 42
}
```

### Clean Up Old Logs

**POST `/admin/logs/clear-old`**
- Deletes logs older than 7 days
- Returns count of deleted entries

Example response:
```json
{
  "status": "success",
  "message": "Deleted 1,234 old log entries",
  "deleted_count": 1234
}
```

## Programmatic Access

### Get Recent Logs

```python
from firestore_logger import FirestoreLogger

logger = FirestoreLogger()

# Get logs from last 24 hours
recent_logs = logger.get_recent_logs(hours=24, limit=100)

# Get only ERROR logs
error_logs = logger.get_recent_logs(hours=24, level='ERROR')

for log in recent_logs:
    print(f"[{log['level']}] {log['message']}")
```

### Cleanup Old Logs

```python
from firestore_logger import FirestoreLogger

logger = FirestoreLogger()

# Delete logs older than 7 days
deleted_count = logger.cleanup_old_logs(days=7)
print(f"Deleted {deleted_count} old logs")
```

### Get Log Statistics

```python
from firestore_logger import FirestoreLogger

logger = FirestoreLogger()

stats = logger.get_log_stats()
print(f"Total logs: {stats['total_logs']}")
print(f"By level: {stats['by_level']}")
print(f"Oldest: {stats['oldest_log']}")
print(f"Newest: {stats['newest_log']}")
```

## Configuration

### Log Levels

Set the minimum log level in `setup_firestore_logging()`:

```python
import logging

# Only log WARNING and above
setup_firestore_logging(level=logging.WARNING)

# Log everything (DEBUG and above)
setup_firestore_logging(level=logging.DEBUG)
```

### Custom Format

Customize the log format string:

```python
setup_firestore_logging(
    level=logging.INFO,
    format_string='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### Retention Period

Change the default 7-day retention when cleaning up:

```python
from firestore_logger import FirestoreLogger

logger = FirestoreLogger()
logger.cleanup_old_logs(days=14)  # Keep logs for 2 weeks
```

## Scheduled Cleanup

### Option 1: Cron Job (Linux/Mac)

Add to your crontab (`crontab -e`):

```bash
# Clean up logs every day at 2 AM
0 2 * * * cd /path/to/ticket-dashboard && python -c "from firestore_logger import FirestoreLogger; FirestoreLogger().cleanup_old_logs(days=7)"
```

### Option 2: Cloud Scheduler (GCP)

Create a scheduled Cloud Run job:

```bash
gcloud scheduler jobs create http cleanup-logs \
  --schedule="0 2 * * *" \
  --uri="https://your-app.run.app/admin/logs/clear-old" \
  --http-method=POST \
  --oidc-service-account-email=your-service-account@project.iam.gserviceaccount.com
```

### Option 3: Python Script

Create `cleanup_logs.py`:

```python
#!/usr/bin/env python3
from firestore_logger import FirestoreLogger

if __name__ == '__main__':
    logger = FirestoreLogger()
    deleted = logger.cleanup_old_logs(days=7)
    print(f"Deleted {deleted} old log entries")
```

Run daily via cron:
```bash
0 2 * * * cd /path/to/ticket-dashboard && python cleanup_logs.py
```

## Performance Considerations

### Batch Writes

The handler writes to Firestore asynchronously but be aware:
- Each log entry = 1 Firestore write
- Free tier: 20,000 writes/day
- Typical usage: ~5,000-10,000 logs/day

### Query Limits

When fetching logs, the default limit is 500 entries. For larger queries:

```python
# Get up to 1000 logs (may be slow)
logs = logger.get_recent_logs(hours=168, limit=1000)  # 1 week
```

### Index Requirements

Firestore automatically creates indexes for:
- `timestamp` (ascending/descending)
- `level` (single-field)

For complex queries, you may need composite indexes.

## Troubleshooting

### Logs Not Appearing

1. **Check Firestore connection:**
   ```python
   from firestore_db import get_database
   db = get_database()
   print("Connected!" if db else "Failed")
   ```

2. **Verify logging is enabled:**
   ```python
   import logging
   logger = logging.getLogger()
   print(f"Handlers: {logger.handlers}")
   ```

3. **Check permissions:**
   - Service account needs `datastore.user` role
   - Or use Application Default Credentials

### Performance Issues

If logging is slow:
- Reduce log level (e.g., WARNING instead of INFO)
- Use local console logging for DEBUG
- Increase cleanup frequency to reduce collection size

### Cost Concerns

Monitor Firestore usage:
- Free tier: 1 GB storage, 50K reads/day, 20K writes/day
- Check usage: [GCP Console → Firestore](https://console.cloud.google.com/firestore)

## Best Practices

1. **Use appropriate log levels:**
   - DEBUG: Detailed debugging info (not recommended for production)
   - INFO: General informational messages
   - WARNING: Warning messages for potential issues
   - ERROR: Error messages for failures
   - CRITICAL: Critical errors requiring immediate attention

2. **Include context:**
   ```python
   logger.info(f"User {user_id} performed action {action}")
   ```

3. **Log exceptions properly:**
   ```python
   try:
       risky_operation()
   except Exception as e:
       logger.error(f"Operation failed", exc_info=True)
   ```

4. **Clean up regularly:**
   - Schedule daily cleanup jobs
   - Keep retention period reasonable (7-14 days)

5. **Monitor costs:**
   - Watch Firestore write operations
   - Reduce log verbosity in production if needed

## Migration from Console Logs

If you were previously using console logs:

1. ✅ Firestore logging is now automatically enabled
2. ✅ Console logs still work (dual output)
3. ✅ No code changes required in most cases
4. ✅ Old console logs are not migrated (start fresh)

## Support

For issues or questions:
- Check Firestore Console for actual log data
- Use `/admin/logs/recent` to verify logs are being written
- Review `firestore_logger.py` for implementation details