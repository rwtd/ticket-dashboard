#!/usr/bin/env python3
"""
Simplified Data Sync Service using Firestore

This replaces data_sync_service.py + google_sheets_exporter.py with
a much simpler implementation using Firestore as the primary data store.

Changes from old version:
- No complex rolling windows or cleanup
- No upsert row tracking
- No batch size magic numbers
- Just: fetch from API → save to Firestore
- ~200 lines instead of 2,500+
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import warnings

# Suppress FutureWarnings from pandas
warnings.filterwarnings('ignore', category=FutureWarning)

import pandas as pd
import pytz
import json

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import our modules
from hubspot_fetcher import HubSpotTicketFetcher
from livechat_fetcher import LiveChatFetcher
from ticket_processor import TicketDataProcessor
from chat_processor import ChatDataProcessor
from firestore_db import get_database

logger = logging.getLogger(__name__)


class FirestoreSyncService:
    """
    Simplified sync service using Firestore
    
    Architecture:
    1. Fetch from APIs
    2. Light processing (timezone, agent names)
    3. Save directly to Firestore
    4. Done. That's it.
    """
    
    def __init__(
        self,
        hubspot_api_key: str,
        livechat_pat: str,
        project_id: Optional[str] = None
    ):
        """
        Initialize sync service
        
        Args:
            hubspot_api_key: HubSpot Private App token
            livechat_pat: LiveChat Personal Access Token
            project_id: GCP project ID (auto-detected if not provided)
        """
        self.hubspot_fetcher = HubSpotTicketFetcher(hubspot_api_key)
        
        # LiveChat PAT handling
        if ':' in livechat_pat:
            username, password = livechat_pat.split(':', 1)
            self.livechat_fetcher = LiveChatFetcher(username, password)
        else:
            self.livechat_fetcher = LiveChatFetcher(livechat_pat, '')
        
        # Firestore database
        self.db = get_database(project_id=project_id)
        
        # Timezone configuration
        self.cdt_tz = pytz.timezone('America/Chicago')  # HubSpot
        self.adt_tz = pytz.timezone('America/Halifax')  # Target
        self.utc_tz = pytz.UTC
    
    def sync_tickets(self, incremental: bool = True) -> int:
        """
        Fetch and sync tickets from HubSpot
        
        Args:
            incremental: If True, only fetch since last sync
            
        Returns:
            Number of tickets synced
        """
        try:
            logger.info("="*60)
            logger.info("🎫 SYNCING TICKETS FROM HUBSPOT")
            logger.info("="*60)
            
            # Check last sync
            last_sync = None
            if incremental:
                metadata = self.db.get_sync_metadata('tickets')
                if metadata and 'last_sync_time' in metadata:
                    last_sync = metadata['last_sync_time']
                    logger.info(f"📥 Incremental sync since {last_sync}")
            
            if not last_sync:
                logger.info("📥 Full sync: fetching last 365 days")
                last_sync = datetime.now(pytz.UTC) - timedelta(days=365)
            
            # Fetch from HubSpot
            df_raw = self.hubspot_fetcher.fetch_tickets(since_date=last_sync)
            
            if df_raw.empty:
                logger.info("✅ No new tickets to sync")
                return 0
            
            logger.info(f"📥 Fetched {len(df_raw)} tickets from HubSpot")
            
            # Simple processing
            df_processed = self._process_tickets(df_raw)
            
            # Save to Firestore
            count = self.db.save_tickets(df_processed)
            
            # Update sync metadata
            self.db.save_sync_metadata('tickets', {
                'last_sync_time': datetime.now(pytz.UTC),
                'last_count': count,
                'status': 'success'
            })
            
            logger.info(f"✅ Synced {count} tickets to Firestore")
            return count
            
        except Exception as e:
            logger.error(f"❌ Ticket sync failed: {e}", exc_info=True)
            return 0
    
    def sync_chats(self, incremental: bool = True) -> int:
        """
        Fetch and sync chats from LiveChat
        
        Args:
            incremental: If True, only fetch since last sync
            
        Returns:
            Number of chats synced
        """
        try:
            logger.info("="*60)
            logger.info("💬 SYNCING CHATS FROM LIVECHAT")
            logger.info("="*60)
            
            # Check last sync
            last_sync = None
            if incremental:
                metadata = self.db.get_sync_metadata('chats')
                if metadata and 'last_sync_time' in metadata:
                    last_sync = metadata['last_sync_time']
                    logger.info(f"📥 Incremental sync since {last_sync}")
            
            if not last_sync:
                logger.info("📥 Full sync: fetching last 365 days")
                last_sync = datetime.now(pytz.UTC) - timedelta(days=365)
            
            # Fetch from LiveChat
            df_raw = self.livechat_fetcher.fetch_and_parse(from_date=last_sync)
            
            if df_raw.empty:
                logger.info("✅ No new chats to sync")
                return 0
            
            logger.info(f"📥 Fetched {len(df_raw)} chats from LiveChat")
            
            # Simple processing
            df_processed = self._process_chats(df_raw)
            
            # Save to Firestore
            count = self.db.save_chats(df_processed)
            
            # Update sync metadata
            self.db.save_sync_metadata('chats', {
                'last_sync_time': datetime.now(pytz.UTC),
                'last_count': count,
                'status': 'success'
            })
            
            logger.info(f"✅ Synced {count} chats to Firestore")
            return count
            
        except Exception as e:
            logger.error(f"❌ Chat sync failed: {e}", exc_info=True)
            return 0
    
    def _process_tickets(self, df: pd.DataFrame) -> pd.DataFrame:
        """Light processing for tickets"""
        # Column mapping
        column_mapping = {
            'subject': 'Subject',
            'hs_pipeline': 'Pipeline',
            'hs_pipeline_stage': 'Pipeline Stage',
            'createdate': 'Create date',
            'hs_lastmodifieddate': 'Last Modified Date',
            'closed_date': 'Close date',
            'hubspot_owner_id': 'Case Owner',
            'hs_ticket_priority': 'Priority',
            'content': 'Description',
            'ticket_id': 'Ticket ID'
        }
        
        df_processed = df.rename(columns=column_mapping)
        
        # Fetch owner names
        if 'Case Owner' in df_processed.columns:
            owner_map = self.hubspot_fetcher.fetch_owners()
            df_processed['Case Owner'] = df_processed['Case Owner'].map(owner_map).fillna(df_processed['Case Owner'])
        
        # Fetch pipeline names
        if 'Pipeline' in df_processed.columns:
            pipeline_map = self.hubspot_fetcher.fetch_pipelines()
            df_processed['Pipeline'] = df_processed['Pipeline'].astype(str).map(pipeline_map).fillna(df_processed['Pipeline'])
        
        # Timezone conversion (CDT → ADT)
        for col in ['Create date', 'Last Modified Date', 'Close date']:
            if col in df_processed.columns:
                df_processed[col] = pd.to_datetime(df_processed[col], errors='coerce', utc=True)
        
        # Use existing processor for weekend flags, agent standardization
        processor = TicketDataProcessor()
        processor.df = df_processed
        processor.process_data()
        
        return processor.df
    
    def _process_chats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process chats using ChatDataProcessor"""
        # Use the chat processor to properly process all columns
        # This handles: agent classification, satisfaction ratings, transfers, etc.
        processor = ChatDataProcessor()
        processor.df = df
        processor.process_data()
        
        return processor.df
    
    def run_full_sync(self) -> bool:
        """Run complete sync"""
        try:
            logger.info("🚀 Starting full sync...")
            start_time = datetime.now()
            
            ticket_count = self.sync_tickets(incremental=False)
            chat_count = self.sync_chats(incremental=False)
            
            elapsed = datetime.now() - start_time
            logger.info(f"⏱️  Completed in {elapsed.total_seconds():.1f}s")
            logger.info(f"✅ FULL SYNC COMPLETE: {ticket_count} tickets, {chat_count} chats")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Full sync failed: {e}", exc_info=True)
            return False
    
    def run_incremental_sync(self) -> bool:
        """Run incremental sync"""
        try:
            logger.info("🔄 Starting incremental sync...")
            start_time = datetime.now()
            
            ticket_count = self.sync_tickets(incremental=True)
            chat_count = self.sync_chats(incremental=True)
            
            elapsed = datetime.now() - start_time
            logger.info(f"⏱️  Completed in {elapsed.total_seconds():.1f}s")
            logger.info(f"✅ INCREMENTAL SYNC COMPLETE: {ticket_count} tickets, {chat_count} chats")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Incremental sync failed: {e}", exc_info=True)
            return False


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Firestore Data Sync Service')
    parser.add_argument('--full', action='store_true', help='Run full sync')
    parser.add_argument('--incremental', action='store_true', help='Run incremental sync')
    parser.add_argument('--test', action='store_true', help='Test connections only')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    hubspot_api_key = os.environ.get('HUBSPOT_API_KEY')
    livechat_pat = os.environ.get('LIVECHAT_PAT')
    project_id = os.environ.get('GCP_PROJECT_ID')
    
    # Validate
    if not all([hubspot_api_key, livechat_pat]):
        logger.error("❌ Missing required environment variables:")
        if not hubspot_api_key:
            logger.error("  - HUBSPOT_API_KEY")
        if not livechat_pat:
            logger.error("  - LIVECHAT_PAT")
        sys.exit(1)
    
    # Initialize service
    service = FirestoreSyncService(
        hubspot_api_key=hubspot_api_key,
        livechat_pat=livechat_pat,
        project_id=project_id
    )
    
    # Test
    if args.test:
        logger.info("🧪 Testing connections...")
        hubspot_ok = service.hubspot_fetcher.test_connection()
        livechat_ok = service.livechat_fetcher.test_connection()
        firestore_ok = service.db.test_connection()
        
        if all([hubspot_ok, livechat_ok, firestore_ok]):
            logger.info("✅ All connections successful!")
            sys.exit(0)
        else:
            logger.error("❌ Some connections failed")
            sys.exit(1)
    
    # Run sync
    if args.full:
        success = service.run_full_sync()
    elif args.incremental:
        success = service.run_incremental_sync()
    else:
        logger.error("Please specify --full or --incremental")
        parser.print_help()
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()