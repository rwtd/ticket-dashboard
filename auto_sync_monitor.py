#!/usr/bin/env python3
"""
Automated File Monitor for Google Sheets Sync
Watches ./tickets and ./chats folders for new CSV files and auto-syncs to Google Sheets
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import hashlib
import json

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from google_sheets_exporter import export_to_google_sheets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoSyncMonitor:
    """Monitor file system for new CSV files and auto-sync to Google Sheets"""
    
    def __init__(self, 
                 tickets_dir: str = './tickets',
                 chats_dir: str = './chats',
                 spreadsheet_id: Optional[str] = None,
                 sweep_interval: int = 300,  # 5 minutes
                 min_file_age: int = 30):    # 30 seconds (wait for file to finish writing)
        
        self.tickets_dir = Path(tickets_dir)
        self.chats_dir = Path(chats_dir)
        self.spreadsheet_id = spreadsheet_id
        self.sweep_interval = sweep_interval
        self.min_file_age = min_file_age
        
        # State tracking
        self.processed_files = self._load_processed_files()
        self.file_hashes = {}
        self.last_sync = None
        
        # Create directories if they don't exist
        self.tickets_dir.mkdir(exist_ok=True)
        self.chats_dir.mkdir(exist_ok=True)
        
        logger.info(f"🔍 AutoSync Monitor initialized")
        logger.info(f"   📂 Watching: {self.tickets_dir}, {self.chats_dir}")
        logger.info(f"   📊 Target sheet: {self.spreadsheet_id or 'Auto-create new'}")
        logger.info(f"   ⏱️  Sweep interval: {self.sweep_interval}s")
    
    def _load_processed_files(self) -> Set[str]:
        """Load list of previously processed files"""
        state_file = Path('.auto_sync_state.json')
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    return set(state.get('processed_files', []))
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")
        return set()
    
    def _save_processed_files(self):
        """Save list of processed files to state file"""
        try:
            state = {
                'processed_files': list(self.processed_files),
                'last_sync': self.last_sync.isoformat() if self.last_sync else None,
                'spreadsheet_id': self.spreadsheet_id
            }
            with open('.auto_sync_state.json', 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state file: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get MD5 hash of file for change detection"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def _is_csv_file(self, file_path: Path) -> bool:
        """Check if file is a CSV file"""
        return file_path.suffix.lower() == '.csv' and file_path.is_file()
    
    def _is_file_ready(self, file_path: Path) -> bool:
        """Check if file is ready for processing (not being written to)"""
        try:
            # Check file age
            file_age = time.time() - file_path.stat().st_mtime
            if file_age < self.min_file_age:
                return False
            
            # Check if file is still being written (size stability)
            size1 = file_path.stat().st_size
            time.sleep(1)
            size2 = file_path.stat().st_size
            return size1 == size2
            
        except Exception:
            return False
    
    def discover_new_files(self) -> Dict[str, list]:
        """Discover new or changed CSV files"""
        new_files = {'tickets': [], 'chats': []}
        
        # Check tickets directory
        for file_path in self.tickets_dir.glob('*.csv'):
            if self._should_process_file(file_path, 'tickets'):
                new_files['tickets'].append(file_path)
        
        # Check chats directory  
        for file_path in self.chats_dir.glob('*.csv'):
            if self._should_process_file(file_path, 'chats'):
                new_files['chats'].append(file_path)
        
        return new_files
    
    def _should_process_file(self, file_path: Path, file_type: str) -> bool:
        """Determine if file should be processed"""
        file_key = f"{file_type}:{file_path.name}"
        
        # Skip if not ready
        if not self._is_file_ready(file_path):
            return False
        
        # Get current hash
        current_hash = self._get_file_hash(file_path)
        if not current_hash:
            return False
        
        # Check if file is new or changed
        if file_key not in self.processed_files:
            logger.info(f"📄 New {file_type} file discovered: {file_path.name}")
            self.file_hashes[file_key] = current_hash
            return True
        
        # Check if file changed
        if self.file_hashes.get(file_key) != current_hash:
            logger.info(f"📄 Changed {file_type} file detected: {file_path.name}")
            self.file_hashes[file_key] = current_hash
            return True
        
        return False
    
    def process_new_files(self, new_files: Dict[str, list]) -> bool:
        """Process new files and sync to Google Sheets"""
        if not any(new_files.values()):
            return False
        
        ticket_count = len(new_files['tickets'])
        chat_count = len(new_files['chats'])
        
        logger.info(f"🚀 Processing {ticket_count} ticket files, {chat_count} chat files")
        
        # Process files by running analytics
        try:
            # Create a temporary results directory for this batch
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            
            # For now, process the most recent ticket file
            # In future versions, could batch process multiple files
            if new_files['tickets']:
                latest_ticket_file = max(new_files['tickets'], key=lambda p: p.stat().st_mtime)
                logger.info(f"📋 Processing latest ticket file: {latest_ticket_file.name}")
                
                # Extract date from filename or use current date
                date_str = self._extract_date_from_filename(latest_ticket_file)
                if date_str:
                    cmd_args = f"--day {date_str}"
                else:
                    cmd_args = f"--custom {(datetime.now() - timedelta(days=1)).strftime('%d%m%Y')}-{datetime.now().strftime('%d%m%Y')}"
                
                # Run analytics with Google Sheets export
                import subprocess
                cmd = [
                    'python', 'ticket_analytics.py',
                    *cmd_args.split(),
                    '--export-to-sheets'
                ]
                
                if self.spreadsheet_id:
                    cmd.extend(['--sheets-id', self.spreadsheet_id])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    logger.info("✅ Analytics and Google Sheets sync completed successfully")
                    
                    # Mark files as processed
                    for file_path in new_files['tickets']:
                        file_key = f"tickets:{file_path.name}"
                        self.processed_files.add(file_key)
                    
                    # Extract spreadsheet ID from output if not set
                    if not self.spreadsheet_id:
                        output_lines = result.stdout.split('\\n')
                        for line in output_lines:
                            if 'docs.google.com/spreadsheets/d/' in line:
                                # Extract sheet ID from URL
                                import re
                                match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', line)
                                if match:
                                    self.spreadsheet_id = match.group(1)
                                    logger.info(f"📊 Auto-detected spreadsheet ID: {self.spreadsheet_id}")
                    
                    self.last_sync = datetime.now()
                    self._save_processed_files()
                    return True
                else:
                    logger.error(f"❌ Analytics failed: {result.stderr}")
                    return False
            
        except Exception as e:
            logger.error(f"❌ Processing failed: {e}")
            return False
        
        return False
    
    def _extract_date_from_filename(self, file_path: Path) -> Optional[str]:
        """Extract date from filename like 'ticket-export-03092025.csv'"""
        import re
        
        # Look for date patterns in filename
        patterns = [
            r'(\d{8})',      # 03092025
            r'(\d{2}[-_]\d{2}[-_]\d{4})',  # 03-09-2025 or 03_09_2025
            r'(\d{4}[-_]\d{2}[-_]\d{2})',  # 2025-09-03 or 2025_09_03
        ]
        
        for pattern in patterns:
            match = re.search(pattern, file_path.name)
            if match:
                date_str = match.group(1).replace('-', '').replace('_', '')
                # Convert YYYY-MM-DD to DDMMYYYY if needed
                if len(date_str) == 8 and date_str.startswith('20'):
                    # Convert YYYYMMDD to DDMMYYYY
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    date_str = f"{day}{month}{year}"
                return date_str
        
        return None
    
    def start_monitoring(self, use_watchdog: bool = True):
        """Start file monitoring (watchdog or polling)"""
        logger.info("🚀 Starting automated file monitoring...")
        
        if use_watchdog and WATCHDOG_AVAILABLE:
            self._start_watchdog_monitor()
        else:
            self._start_polling_monitor()
    
    def _start_watchdog_monitor(self):
        """Start real-time file monitoring using watchdog"""
        logger.info("👁️  Using real-time file monitoring (watchdog)")
        
        class CSVFileHandler(FileSystemEventHandler):
            def __init__(self, monitor):
                self.monitor = monitor
                self.last_processed = {}
            
            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith('.csv'):
                    logger.info(f"📄 New file detected: {event.src_path}")
                    # Delay processing to ensure file is complete
                    time.sleep(5)
                    self.monitor._process_if_ready(Path(event.src_path))
            
            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith('.csv'):
                    # Throttle modification events
                    now = time.time()
                    if now - self.last_processed.get(event.src_path, 0) > 30:
                        logger.info(f"📝 File modified: {event.src_path}")
                        self.last_processed[event.src_path] = now
                        time.sleep(5)
                        self.monitor._process_if_ready(Path(event.src_path))
        
        event_handler = CSVFileHandler(self)
        observer = Observer()
        
        # Watch both directories
        observer.schedule(event_handler, str(self.tickets_dir), recursive=False)
        observer.schedule(event_handler, str(self.chats_dir), recursive=False)
        
        observer.start()
        
        try:
            logger.info("⏱️  File monitor is running... (Ctrl+C to stop)")
            while True:
                time.sleep(60)  # Heartbeat every minute
                logger.debug("💓 Monitor heartbeat")
        except KeyboardInterrupt:
            logger.info("🛑 Stopping file monitor...")
            observer.stop()
        
        observer.join()
    
    def _start_polling_monitor(self):
        """Start polling-based file monitoring"""
        logger.info(f"🔄 Using polling monitoring (every {self.sweep_interval}s)")
        
        try:
            while True:
                logger.debug("🔍 Scanning for new files...")
                new_files = self.discover_new_files()
                
                if any(new_files.values()):
                    self.process_new_files(new_files)
                else:
                    logger.debug("😴 No new files found")
                
                time.sleep(self.sweep_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Stopping file monitor...")
    
    def _process_if_ready(self, file_path: Path):
        """Process single file if ready"""
        if file_path.parent == self.tickets_dir:
            file_type = 'tickets'
        elif file_path.parent == self.chats_dir:
            file_type = 'chats'
        else:
            return
        
        if self._should_process_file(file_path, file_type):
            new_files = {file_type: [file_path], 'tickets' if file_type == 'chats' else 'chats': []}
            self.process_new_files(new_files)

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Google Sheets sync monitor')
    parser.add_argument('--spreadsheet-id', help='Google Sheets ID (auto-creates if not provided)')
    parser.add_argument('--sweep-interval', type=int, default=300, help='Polling interval in seconds (default: 300)')
    parser.add_argument('--min-file-age', type=int, default=30, help='Minimum file age before processing (default: 30s)')
    parser.add_argument('--tickets-dir', default='./tickets', help='Tickets directory to monitor')
    parser.add_argument('--chats-dir', default='./chats', help='Chats directory to monitor')
    parser.add_argument('--no-watchdog', action='store_true', help='Use polling instead of real-time monitoring')
    
    args = parser.parse_args()
    
    monitor = AutoSyncMonitor(
        tickets_dir=args.tickets_dir,
        chats_dir=args.chats_dir,
        spreadsheet_id=args.spreadsheet_id,
        sweep_interval=args.sweep_interval,
        min_file_age=args.min_file_age
    )
    
    # Initial scan for existing files
    logger.info("🔍 Initial scan for existing files...")
    new_files = monitor.discover_new_files()
    if any(new_files.values()):
        logger.info("📋 Found existing unprocessed files, syncing...")
        monitor.process_new_files(new_files)
    
    # Start monitoring
    monitor.start_monitoring(use_watchdog=not args.no_watchdog)

if __name__ == "__main__":
    main()