#!/usr/bin/env python3
"""
Firestore Logger - Custom logging handler that writes to Firestore
Stores application logs with automatic weekly rotation
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import traceback


class FirestoreLogHandler(logging.Handler):
    """Custom logging handler that writes to Firestore"""
    
    def __init__(self, collection_name='application_logs'):
        super().__init__()
        self.collection_name = collection_name
        self._db = None
    
    @property
    def db(self):
        """Lazy load Firestore database"""
        if self._db is None:
            from firestore_db import get_database
            self._db = get_database()
        return self._db
    
    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to Firestore
        
        Args:
            record: LogRecord to write
        """
        try:
            # CRITICAL: Prevent infinite recursion by ignoring logs from firestore_db module
            if record.name == 'firestore_db' or record.module == 'firestore_db':
                return
            
            # Format the log entry
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': self.format(record),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'thread': record.thread,
                'thread_name': record.threadName,
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry['exception'] = ''.join(traceback.format_exception(*record.exc_info))
            
            # Add extra fields if present
            if hasattr(record, 'user'):
                log_entry['user'] = record.user
            if hasattr(record, 'request_id'):
                log_entry['request_id'] = record.request_id
            
            # Write to Firestore (non-blocking)
            self._write_to_firestore(log_entry)
            
        except Exception as e:
            # Don't let logging errors crash the app
            print(f"Failed to write log to Firestore: {e}")
            self.handleError(record)
    
    def _write_to_firestore(self, log_entry: dict):
        """Write log entry to Firestore collection"""
        try:
            # Temporarily disable logging to prevent recursion
            import logging
            old_level = logging.root.level
            logging.root.setLevel(logging.CRITICAL + 1)  # Disable all logging
            
            try:
                # Generate document ID from timestamp for ordering
                doc_id = f"{log_entry['timestamp']}_{log_entry['level']}"
                
                # Get collection reference
                collection_ref = self.db.db.collection(self.collection_name)
                
                # Add document
                collection_ref.document(doc_id).set(log_entry)
            finally:
                # Restore logging level
                logging.root.setLevel(old_level)
            
        except Exception as e:
            # Use print to avoid triggering more logging
            print(f"Firestore write error: {e}")


class FirestoreLogger:
    """Helper class for managing Firestore logs"""
    
    def __init__(self, collection_name='application_logs'):
        self.collection_name = collection_name
        self._db = None
    
    @property
    def db(self):
        """Lazy load Firestore database"""
        if self._db is None:
            from firestore_db import get_database
            self._db = get_database()
        return self._db
    
    def get_recent_logs(
        self, 
        hours: int = 24, 
        limit: int = 500,
        level: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent logs from Firestore
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of logs to return
            level: Filter by log level (INFO, WARNING, ERROR, etc.)
        
        Returns:
            List of log entries (most recent first)
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cutoff_iso = cutoff.isoformat()
            
            # Build query
            query = self.db.db.collection(self.collection_name)
            query = query.where('timestamp', '>=', cutoff_iso)
            
            if level:
                query = query.where('level', '==', level)
            
            query = query.order_by('timestamp', direction='DESCENDING')
            query = query.limit(limit)
            
            # Execute query
            docs = query.stream()
            
            # Convert to list
            logs = []
            for doc in docs:
                log_data = doc.to_dict()
                log_data['id'] = doc.id
                logs.append(log_data)
            
            return logs
            
        except Exception as e:
            print(f"Failed to fetch logs: {e}")
            return []
    
    def cleanup_old_logs(self, days: int = 7) -> int:
        """
        Delete logs older than specified days
        
        Args:
            days: Delete logs older than this many days
        
        Returns:
            Number of logs deleted
        """
        try:
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(days=days)
            cutoff_iso = cutoff.isoformat()
            
            # Query old logs
            query = self.db.db.collection(self.collection_name)
            query = query.where('timestamp', '<', cutoff_iso)
            
            # Delete in batches
            deleted_count = 0
            batch_size = 500
            
            while True:
                docs = query.limit(batch_size).stream()
                docs_list = list(docs)
                
                if not docs_list:
                    break
                
                # Create batch delete
                batch = self.db.db.batch()
                for doc in docs_list:
                    batch.delete(doc.reference)
                    deleted_count += 1
                
                # Commit batch
                batch.commit()
                
                # If we got fewer than batch_size, we're done
                if len(docs_list) < batch_size:
                    break
            
            return deleted_count
            
        except Exception as e:
            print(f"Failed to cleanup logs: {e}")
            return 0
    
    def get_log_stats(self) -> Dict:
        """
        Get statistics about logs in Firestore
        
        Returns:
            Dictionary with log statistics
        """
        try:
            stats = {
                'total_logs': 0,
                'by_level': {},
                'oldest_log': None,
                'newest_log': None
            }
            
            # Get all logs (limited for performance)
            query = self.db.db.collection(self.collection_name)
            query = query.limit(10000)  # Cap at 10k for stats
            
            docs = query.stream()
            
            for doc in docs:
                data = doc.to_dict()
                stats['total_logs'] += 1
                
                # Count by level
                level = data.get('level', 'UNKNOWN')
                stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
                
                # Track oldest/newest
                timestamp = data.get('timestamp')
                if timestamp:
                    if not stats['oldest_log'] or timestamp < stats['oldest_log']:
                        stats['oldest_log'] = timestamp
                    if not stats['newest_log'] or timestamp > stats['newest_log']:
                        stats['newest_log'] = timestamp
            
            return stats
            
        except Exception as e:
            print(f"Failed to get log stats: {e}")
            return {'error': str(e)}


def setup_firestore_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None
):
    """
    Set up Firestore logging for the application
    
    Args:
        level: Minimum log level to write to Firestore
        format_string: Custom format string for logs
    """
    # Create handler
    handler = FirestoreLogHandler()
    handler.setLevel(level)
    
    # Set format
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    return handler


# Example usage
if __name__ == '__main__':
    # Set up logging
    setup_firestore_logging(level=logging.INFO)
    
    # Test logging
    logger = logging.getLogger(__name__)
    logger.info("Test INFO log entry")
    logger.warning("Test WARNING log entry")
    logger.error("Test ERROR log entry")
    
    # Get recent logs
    firestore_logger = FirestoreLogger()
    recent_logs = firestore_logger.get_recent_logs(hours=1, limit=10)
    
    print(f"\nFound {len(recent_logs)} recent logs:")
    for log in recent_logs:
        print(f"  [{log['level']}] {log['message']}")
    
    # Get stats
    stats = firestore_logger.get_log_stats()
    print(f"\nLog Statistics:")
    print(f"  Total logs: {stats['total_logs']}")
    print(f"  By level: {stats['by_level']}")
    print(f"  Oldest: {stats['oldest_log']}")
    print(f"  Newest: {stats['newest_log']}")