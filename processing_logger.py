#!/usr/bin/env python3
"""
Processing Logger for Ticket Dashboard
Captures detailed processing logs and sync operations for web UI and Google Sheets
"""

import logging
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
import queue

@dataclass
class ProcessingLogEntry:
    """Single processing log entry"""
    timestamp: str
    level: str  # INFO, WARNING, ERROR, SUCCESS
    stage: str  # INIT, PROCESSING, SHEETS_SYNC, COMPLETE, ERROR
    message: str
    details: Dict[str, Any] = None
    duration_ms: Optional[int] = None

@dataclass
class ProcessingRun:
    """Complete processing run with metadata"""
    run_id: str
    start_time: str
    end_time: Optional[str] = None
    status: str = "RUNNING"  # RUNNING, COMPLETED, FAILED
    analytics_type: str = "tickets"  # tickets, chats, combined
    date_range: str = ""
    files_processed: List[str] = None
    records_processed: int = 0
    sheets_updated: bool = False
    spreadsheet_id: Optional[str] = None
    spreadsheet_url: Optional[str] = None
    total_duration_ms: Optional[int] = None
    log_entries: List[ProcessingLogEntry] = None
    
    def __post_init__(self):
        if self.files_processed is None:
            self.files_processed = []
        if self.log_entries is None:
            self.log_entries = []

class ProcessingLogger:
    """Centralized logging system for processing operations"""
    
    def __init__(self, log_file: str = "processing_runs.jsonl"):
        self.log_file = Path(log_file)
        self.current_run: Optional[ProcessingRun] = None
        self.run_start_time = None
        
        # Thread-safe log queue for real-time updates
        self.log_queue = queue.Queue()
        self.live_subscribers = set()
        
        # Setup file logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        # Create custom handler that captures logs
        self.log_handler = LogCaptureHandler(self)
        
        # Configure root logger to capture all app logs
        root_logger = logging.getLogger()
        if not any(isinstance(h, LogCaptureHandler) for h in root_logger.handlers):
            root_logger.addHandler(self.log_handler)
            
    def start_processing_run(self, analytics_type: str = "tickets", date_range: str = "") -> str:
        """Start a new processing run"""
        run_id = f"run_{int(time.time() * 1000)}"
        self.run_start_time = time.time()
        
        self.current_run = ProcessingRun(
            run_id=run_id,
            start_time=datetime.now().isoformat(),
            analytics_type=analytics_type,
            date_range=date_range,
            status="RUNNING"
        )
        
        self.log_info("INIT", f"🚀 Starting {analytics_type} processing run", {
            "run_id": run_id,
            "date_range": date_range
        })
        
        return run_id
    
    def end_processing_run(self, status: str = "COMPLETED"):
        """End the current processing run"""
        if not self.current_run:
            return
            
        self.current_run.end_time = datetime.now().isoformat()
        self.current_run.status = status
        
        if self.run_start_time:
            duration = int((time.time() - self.run_start_time) * 1000)
            self.current_run.total_duration_ms = duration
        
        # Log completion
        status_emoji = "✅" if status == "COMPLETED" else "❌"
        self.log_info("COMPLETE", f"{status_emoji} Processing run {status.lower()}", {
            "run_id": self.current_run.run_id,
            "duration_ms": self.current_run.total_duration_ms,
            "records_processed": self.current_run.records_processed,
            "sheets_updated": self.current_run.sheets_updated
        })
        
        # Save to file
        self._save_run_to_file()
        
        # Clear current run
        self.current_run = None
        self.run_start_time = None
    
    def log_info(self, stage: str, message: str, details: Dict[str, Any] = None):
        """Log info level message"""
        self._log_entry("INFO", stage, message, details)
    
    def log_warning(self, stage: str, message: str, details: Dict[str, Any] = None):
        """Log warning level message"""
        self._log_entry("WARNING", stage, message, details)
    
    def log_error(self, stage: str, message: str, details: Dict[str, Any] = None):
        """Log error level message"""
        self._log_entry("ERROR", stage, message, details)
    
    def log_success(self, stage: str, message: str, details: Dict[str, Any] = None):
        """Log success level message"""
        self._log_entry("SUCCESS", stage, message, details)
    
    def _log_entry(self, level: str, stage: str, message: str, details: Dict[str, Any] = None):
        """Add log entry to current run"""
        entry = ProcessingLogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            stage=stage,
            message=message,
            details=details or {}
        )
        
        if self.current_run:
            self.current_run.log_entries.append(entry)
        
        # Add to real-time queue
        self.log_queue.put(entry)
        
        # Also log to console/file
        log_level = getattr(logging, level.upper() if level != "SUCCESS" else "INFO")
        logging.getLogger(__name__).log(log_level, f"[{stage}] {message}")
    
    def update_run_metadata(self, **kwargs):
        """Update current run metadata"""
        if not self.current_run:
            return
            
        for key, value in kwargs.items():
            if hasattr(self.current_run, key):
                setattr(self.current_run, key, value)
    
    def add_processed_file(self, filename: str):
        """Add processed file to current run"""
        if self.current_run:
            self.current_run.files_processed.append(filename)
    
    def set_sheets_info(self, spreadsheet_id: str, updated: bool = True):
        """Set Google Sheets information"""
        if self.current_run:
            self.current_run.spreadsheet_id = spreadsheet_id
            self.current_run.sheets_updated = updated
            self.current_run.spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    
    def _save_run_to_file(self):
        """Save completed run to JSONL file"""
        if not self.current_run:
            return
            
        try:
            # Convert to dict and save as JSON line
            run_dict = asdict(self.current_run)
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                json.dump(run_dict, f, ensure_ascii=False)
                f.write('\n')
                
        except Exception as e:
            logging.error(f"Failed to save processing run: {e}")
    
    def get_recent_runs(self, limit: int = 50) -> List[ProcessingRun]:
        """Get recent processing runs"""
        runs = []
        
        if not self.log_file.exists():
            return runs
            
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Get last N lines and parse
            for line in lines[-limit:]:
                if line.strip():
                    run_dict = json.loads(line.strip())
                    # Convert dict back to ProcessingRun
                    run_dict['log_entries'] = [
                        ProcessingLogEntry(**entry) for entry in run_dict.get('log_entries', [])
                    ]
                    runs.append(ProcessingRun(**run_dict))
                    
        except Exception as e:
            logging.error(f"Failed to load processing runs: {e}")
            
        return list(reversed(runs))  # Most recent first
    
    def get_live_logs(self, since_timestamp: Optional[str] = None) -> List[ProcessingLogEntry]:
        """Get live log entries for real-time updates"""
        logs = []
        
        # Get from queue (non-blocking)
        while True:
            try:
                entry = self.log_queue.get_nowait()
                
                # Filter by timestamp if provided
                if since_timestamp is None or entry.timestamp > since_timestamp:
                    logs.append(entry)
                    
            except queue.Empty:
                break
        
        return logs
    
    def get_current_run(self) -> Optional[ProcessingRun]:
        """Get current running processing run"""
        return self.current_run

class LogCaptureHandler(logging.Handler):
    """Custom logging handler to capture logs for processing runs"""
    
    def __init__(self, processing_logger: ProcessingLogger):
        super().__init__()
        self.processing_logger = processing_logger
        
    def emit(self, record):
        """Capture log record"""
        if not self.processing_logger.current_run:
            return
            
        # Extract stage and message from log record
        stage = getattr(record, 'stage', 'PROCESSING')
        message = record.getMessage()
        
        # Map log levels
        level_map = {
            'DEBUG': 'INFO',
            'INFO': 'INFO', 
            'WARNING': 'WARNING',
            'ERROR': 'ERROR',
            'CRITICAL': 'ERROR'
        }
        
        level = level_map.get(record.levelname, 'INFO')
        
        # Add to current run (avoid recursion)
        if hasattr(record, 'skip_capture'):
            return
            
        entry = ProcessingLogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            stage=stage,
            message=message,
            details={'logger': record.name, 'line': record.lineno}
        )
        
        if self.processing_logger.current_run:
            self.processing_logger.current_run.log_entries.append(entry)

# Global logger instance
processing_logger = ProcessingLogger()

def get_processing_logger() -> ProcessingLogger:
    """Get the global processing logger instance"""
    return processing_logger