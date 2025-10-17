#!/usr/bin/env python3
"""
Automated Data Sync Service
Orchestrates fetching data from HubSpot and LiveChat APIs,
processes it, and syncs to Google Sheets as the primary data source
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

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed

# Import our custom modules
from hubspot_fetcher import HubSpotTicketFetcher
from livechat_fetcher import LiveChatFetcher
from ticket_processor import TicketDataProcessor
from chat_processor import ChatDataProcessor
from google_sheets_exporter import GoogleSheetsExporter

logger = logging.getLogger(__name__)


def _ensure_utc_columns(df: pd.DataFrame, src_col: str, base_name: str) -> pd.DataFrame:
    """
    Create canonical UTC datetime columns from a timezone-aware source column.

    Adds two columns:
        <base_name>_utc  (datetime64[ns, UTC])
        <base_name>_iso  (str, ISO-8601 Z format)
    """
    if src_col not in df.columns:
        return df

    series = pd.to_datetime(df[src_col], errors='coerce', utc=False)
    if series.dt.tz is None:
        # Assume values are naive but represent ADT (Atlantic) as per existing pipeline
        atlantic = pytz.timezone('Canada/Atlantic')
        series = series.dt.tz_localize(atlantic, ambiguous=False, nonexistent='shift_forward')

    utc_series = series.dt.tz_convert(pytz.UTC)
    df[f"{base_name}_utc"] = utc_series
    df[f"{base_name}_iso"] = utc_series.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return df


class DataSyncService:
    """
    Orchestrates automated data fetching and syncing to Google Sheets
    """

    def __init__(
        self,
        hubspot_api_key: str,
        livechat_pat: str,
        sheets_spreadsheet_id: str,
        sheets_credentials_path: str,
        sync_state_file: str = 'sync_state.json'
    ):
        """
        Initialize sync service

        Args:
            hubspot_api_key: HubSpot Private App token
            livechat_pat: LiveChat Personal Access Token
            sheets_spreadsheet_id: Google Sheets ID for data storage
            sheets_credentials_path: Path to Google service account credentials
            sync_state_file: File to track last sync times
        """
        self.hubspot_fetcher = HubSpotTicketFetcher(hubspot_api_key)
        # LiveChat can use PAT (as username with empty password) or username/password
        if ':' in livechat_pat:
            # Assume it's username:password format
            username, password = livechat_pat.split(':', 1)
            self.livechat_fetcher = LiveChatFetcher(username, password)
        else:
            # Assume it's a PAT token (use as username with empty password)
            self.livechat_fetcher = LiveChatFetcher(livechat_pat, '')
        self.sheets_exporter = GoogleSheetsExporter(sheets_credentials_path)
        self.sheets_spreadsheet_id = sheets_spreadsheet_id
        self.sync_state_file = Path(sync_state_file)

        # Timezone configuration
        self.cdt_tz = pytz.timezone('America/Chicago')  # HubSpot tickets (CDT)
        self.adt_tz = pytz.timezone('America/Halifax')  # Target timezone (ADT)
        self.utc_tz = pytz.UTC  # LiveChat (UTC)

    def load_sync_state(self) -> Dict[str, Any]:
        """Load last sync state from file"""
        if self.sync_state_file.exists():
            try:
                with open(self.sync_state_file, 'r') as f:
                    state = json.load(f)
                    # Convert ISO strings back to datetime
                    if 'last_ticket_sync' in state:
                        state['last_ticket_sync'] = datetime.fromisoformat(state['last_ticket_sync'])
                    if 'last_chat_sync' in state:
                        state['last_chat_sync'] = datetime.fromisoformat(state['last_chat_sync'])
                    return state
            except Exception as e:
                logger.warning(f"Failed to load sync state: {e}")

        # Default state (fetch last 365 days on first run)
        return {
            'last_ticket_sync': datetime.now(pytz.UTC) - timedelta(days=365),
            'last_chat_sync': datetime.now(pytz.UTC) - timedelta(days=365),
            'last_full_sync': None
        }

    def save_sync_state(self, state: Dict[str, Any]):
        """Save sync state to file"""
        try:
            # Convert datetime to ISO strings for JSON
            serializable_state = {}
            for key, value in state.items():
                if isinstance(value, datetime):
                    serializable_state[key] = value.isoformat()
                else:
                    serializable_state[key] = value

            with open(self.sync_state_file, 'w') as f:
                json.dump(serializable_state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")

    def sync_tickets(self, incremental: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch and process tickets from HubSpot

        Args:
            incremental: If True, only fetch since last sync; if False, fetch all

        Returns:
            Processed DataFrame or None on failure
        """
        try:
            logger.info("=" * 60)
            logger.info("🎫 SYNCING TICKETS FROM HUBSPOT")
            logger.info("=" * 60)

            # Load sync state
            state = self.load_sync_state()
            last_sync = state.get('last_ticket_sync')

            # Fetch tickets
            if incremental and last_sync:
                logger.info(f"📥 Incremental sync: fetching tickets since {last_sync}")
                df_raw = self.hubspot_fetcher.fetch_incremental(last_sync)
            else:
                logger.info("📥 Full sync: fetching all tickets (last 365 days)")
                from_date = datetime.now(pytz.UTC) - timedelta(days=365)
                df_raw = self.hubspot_fetcher.fetch_tickets(since_date=from_date)

            if df_raw.empty:
                logger.warning("⚠️  No tickets fetched")
                return None

            logger.info(f"✅ Fetched {len(df_raw)} raw tickets")

            # Process tickets using existing processor
            logger.info("⚙️  Processing tickets...")
            processor = TicketDataProcessor()

            # Convert to format expected by processor
            # Map HubSpot API fields to CSV column names
            df_processed = df_raw.copy()

            # Rename columns to match CSV format
            column_mapping = {
                'subject': 'Subject',
                'hs_pipeline': 'Pipeline',
                'hs_pipeline_stage': 'Pipeline Stage',
                'createdate': 'Create date',
                'hs_lastmodifieddate': 'Last Modified Date',
                'closed_date': 'Close date',
                'hubspot_owner_id': 'Case Owner',  # Will be mapped to name later
                'first_agent_reply_date': 'First agent email response date',  # For response time calculation
                'hs_ticket_priority': 'Priority',
                'content': 'Description',
                'ticket_id': 'Ticket ID'
            }

            # Rename available columns
            df_processed.rename(columns=column_mapping, inplace=True)

            # Fetch owner mapping and replace IDs with names
            if 'Case Owner' in df_processed.columns:
                owner_map = self.hubspot_fetcher.fetch_owners()
                df_processed['Case Owner'] = df_processed['Case Owner'].map(owner_map).fillna(df_processed['Case Owner'])

            # Fetch pipeline mapping and replace IDs with labels
            if 'Pipeline' in df_processed.columns:
                pipeline_map = self.hubspot_fetcher.fetch_pipelines()
                df_processed['Pipeline'] = df_processed['Pipeline'].astype(str).map(pipeline_map).fillna(df_processed['Pipeline'])

            # Convert dates to CDT then ADT
            for date_col in ['Create date', 'Last Modified Date', 'Close date']:
                if date_col in df_processed.columns:
                    df_processed[date_col] = pd.to_datetime(df_processed[date_col], errors='coerce')
                    # Check if already timezone-aware, if not localize to UTC first
                    if df_processed[date_col].dt.tz is None:
                        df_processed[date_col] = df_processed[date_col].dt.tz_localize('UTC')
                    else:
                        # Already has timezone, convert to UTC first
                        df_processed[date_col] = df_processed[date_col].dt.tz_convert('UTC')
                    # Now convert from UTC to CDT to ADT (+1 hour)
                    df_processed[date_col] = df_processed[date_col].dt.tz_convert(self.cdt_tz).dt.tz_convert(self.adt_tz)

            # Load into processor for additional processing
            processor.df = df_processed
            processor.process_data()  # Adds weekend flags, standardizes agent names, etc.

            # Get processed data
            df_final = processor.df

            logger.info(f"✅ Processed {len(df_final)} tickets")
            logger.info(f"📊 Columns: {list(df_final.columns)}")

            # Normalize canonical UTC columns for downstream consumers
            if 'Create date' in df_final.columns:
                df_final = _ensure_utc_columns(df_final, 'Create date', 'ticket_created_at')
            if 'Last Modified Date' in df_final.columns:
                df_final = _ensure_utc_columns(df_final, 'Last Modified Date', 'ticket_last_modified')
            if 'Close date' in df_final.columns:
                df_final = _ensure_utc_columns(df_final, 'Close date', 'ticket_closed_at')

            # Update sync state
            state['last_ticket_sync'] = datetime.now(pytz.UTC)
            self.save_sync_state(state)

            return df_final

        except Exception as e:
            logger.error(f"❌ Ticket sync failed: {e}", exc_info=True)
            return None

    def sync_chats(self, incremental: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch and process chats from LiveChat

        Args:
            incremental: If True, only fetch since last sync; if False, fetch all

        Returns:
            Processed DataFrame or None on failure
        """
        try:
            logger.info("=" * 60)
            logger.info("💬 SYNCING CHATS FROM LIVECHAT")
            logger.info("=" * 60)

            # Load sync state
            state = self.load_sync_state()
            last_sync = state.get('last_chat_sync')

            # Fetch chats
            if incremental and last_sync:
                logger.info(f"📥 Incremental sync: fetching chats since {last_sync}")
                df_raw = self.livechat_fetcher.fetch_incremental(last_sync)
            else:
                logger.info("📥 Full sync: fetching all chats (last 365 days)")
                from_date = datetime.now(pytz.UTC) - timedelta(days=365)
                df_raw = self.livechat_fetcher.fetch_and_parse(from_date=from_date)

            if df_raw.empty:
                logger.warning("⚠️  No chats fetched")
                return None

            logger.info(f"✅ Fetched {len(df_raw)} raw chats")

            # LiveChat fetcher already returns processed data (agent names, bot detection, etc.)
            # No need for ChatDataProcessor - it's designed for CSV exports, not API data
            logger.info("⚙️  Processing chats...")

            # Convert timezone from UTC to ADT
            df_final = df_raw.copy()
            if 'chat_creation_date_utc' in df_final.columns:
                df_final['chat_creation_date_adt'] = pd.to_datetime(df_final['chat_creation_date_utc'], errors='coerce')
                # Only localize if not already timezone-aware
                if df_final['chat_creation_date_adt'].dt.tz is None:
                    df_final['chat_creation_date_adt'] = df_final['chat_creation_date_adt'].dt.tz_localize('UTC')
                df_final['chat_creation_date_adt'] = df_final['chat_creation_date_adt'].dt.tz_convert(self.adt_tz)

            logger.info(f"✅ Processed {len(df_final)} chats")
            logger.info(f"📊 Columns: {list(df_final.columns)}")

            # Normalize timestamps to canonical UTC fields
            if 'chat_creation_date_adt' in df_final.columns:
                df_final = _ensure_utc_columns(df_final, 'chat_creation_date_adt', 'chat_created_at')
            elif 'chat_creation_date_utc' in df_final.columns:
                df_final['chat_created_at_utc'] = pd.to_datetime(df_final['chat_creation_date_utc'], errors='coerce', utc=True)
                df_final['chat_created_at_iso'] = df_final['chat_created_at_utc'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            if 'chat_start_date_adt' in df_final.columns:
                df_final = _ensure_utc_columns(df_final, 'chat_start_date_adt', 'chat_started_at')

            # Update sync state
            state['last_chat_sync'] = datetime.now(pytz.UTC)
            self.save_sync_state(state)

            return df_final

        except Exception as e:
            logger.error(f"❌ Chat sync failed: {e}", exc_info=True)
            return None

    def sync_to_sheets(self, tickets_df: Optional[pd.DataFrame], chats_df: Optional[pd.DataFrame]) -> bool:
        """
        Sync processed data to Google Sheets

        Args:
            tickets_df: Processed tickets DataFrame
            chats_df: Processed chats DataFrame

        Returns:
            True if successful
        """
        try:
            logger.info("=" * 60)
            logger.info("📊 SYNCING TO GOOGLE SHEETS")
            logger.info("=" * 60)

            # Authenticate
            if not self.sheets_exporter.authenticate():
                logger.error("❌ Google Sheets authentication failed")
                return False

            # Create temporary directory for export
            temp_dir = Path('/tmp/data_sync')
            temp_dir.mkdir(exist_ok=True)

            # Save DataFrames to temporary CSVs
            success = True

            if tickets_df is not None and not tickets_df.empty:
                tickets_csv = temp_dir / 'tickets_transformed.csv'
                tickets_df.to_csv(tickets_csv, index=False)
                logger.info(f"💾 Saved {len(tickets_df)} tickets to temp CSV")

                # Upload to Sheets
                logger.info("📤 Uploading tickets to Google Sheets...")
                result = self.sheets_exporter.export_data(
                    ticket_df=tickets_df,
                    chat_df=None,
                    spreadsheet_id=self.sheets_spreadsheet_id
                )
                if result:
                    logger.info("✅ Tickets uploaded successfully")
                else:
                    logger.error("❌ Tickets upload failed")
                    success = False

            if chats_df is not None and not chats_df.empty:
                chats_csv = temp_dir / 'chats_transformed.csv'
                chats_df.to_csv(chats_csv, index=False)
                logger.info(f"💾 Saved {len(chats_df)} chats to temp CSV")

                # Upload to Sheets
                logger.info("📤 Uploading chats to Google Sheets...")
                result = self.sheets_exporter.export_data(
                    ticket_df=None,
                    chat_df=chats_df,
                    spreadsheet_id=self.sheets_spreadsheet_id
                )
                if result:
                    logger.info("✅ Chats uploaded successfully")
                else:
                    logger.error("❌ Chats upload failed")
                    success = False

            # Log sync to Sync_Log sheet
            sync_log_entry = {
                'Timestamp': datetime.now(self.adt_tz).isoformat(),
                'Tickets_Count': len(tickets_df) if tickets_df is not None else 0,
                'Chats_Count': len(chats_df) if chats_df is not None else 0,
                'Status': 'Success' if success else 'Partial Failure'
            }
            logger.info(f"📝 Sync completed: {sync_log_entry}")

            return success

        except Exception as e:
            logger.error(f"❌ Google Sheets sync failed: {e}", exc_info=True)
            return False

    def run_full_sync(self) -> bool:
        """
        Run complete sync: fetch from APIs and upload to Google Sheets

        Returns:
            True if successful
        """
        try:
            logger.info("🚀 Starting full data sync...")
            start_time = datetime.now()

            # Sync tickets
            tickets_df = self.sync_tickets(incremental=False)

            # Sync chats
            chats_df = self.sync_chats(incremental=False)

            # Upload to Sheets
            success = self.sync_to_sheets(tickets_df, chats_df)

            # Update state
            if success:
                state = self.load_sync_state()
                state['last_full_sync'] = datetime.now(pytz.UTC)
                self.save_sync_state(state)

            elapsed = datetime.now() - start_time
            logger.info(f"⏱️  Sync completed in {elapsed.total_seconds():.1f} seconds")

            if success:
                logger.info("✅ FULL SYNC SUCCESSFUL")
            else:
                logger.warning("⚠️  SYNC COMPLETED WITH ERRORS")

            return success

        except Exception as e:
            logger.error(f"❌ Full sync failed: {e}", exc_info=True)
            return False

    def run_incremental_sync(self) -> bool:
        """
        Run incremental sync: fetch only new/updated data

        Returns:
            True if successful
        """
        try:
            logger.info("🔄 Starting incremental data sync...")
            start_time = datetime.now()

            # Sync tickets
            tickets_df = self.sync_tickets(incremental=True)

            # Sync chats
            chats_df = self.sync_chats(incremental=True)

            # Upload to Sheets
            success = self.sync_to_sheets(tickets_df, chats_df)

            elapsed = datetime.now() - start_time
            logger.info(f"⏱️  Sync completed in {elapsed.total_seconds():.1f} seconds")

            if success:
                logger.info("✅ INCREMENTAL SYNC SUCCESSFUL")
            else:
                logger.warning("⚠️  SYNC COMPLETED WITH ERRORS")

            return success

        except Exception as e:
            logger.error(f"❌ Incremental sync failed: {e}", exc_info=True)
            return False


def main():
    """CLI entry point for manual sync"""
    import argparse

    parser = argparse.ArgumentParser(description='Data Sync Service for Ticket Dashboard')
    parser.add_argument('--full', action='store_true', help='Run full sync (last 365 days)')
    parser.add_argument('--incremental', action='store_true', help='Run incremental sync (since last run)')
    parser.add_argument('--test', action='store_true', help='Test API connections only')

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration from environment
    hubspot_api_key = os.environ.get('HUBSPOT_API_KEY')
    livechat_pat = os.environ.get('LIVECHAT_PAT')
    sheets_spreadsheet_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
    sheets_credentials_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')

    # Validate configuration
    if not all([hubspot_api_key, livechat_pat, sheets_spreadsheet_id]):
        logger.error("❌ Missing required environment variables:")
        if not hubspot_api_key:
            logger.error("  - HUBSPOT_API_KEY")
        if not livechat_pat:
            logger.error("  - LIVECHAT_PAT")
        if not sheets_spreadsheet_id:
            logger.error("  - GOOGLE_SHEETS_SPREADSHEET_ID")
        sys.exit(1)

    # Initialize service
    service = DataSyncService(
        hubspot_api_key=hubspot_api_key,
        livechat_pat=livechat_pat,
        sheets_spreadsheet_id=sheets_spreadsheet_id,
        sheets_credentials_path=sheets_credentials_path
    )

    # Test connections
    if args.test:
        logger.info("🧪 Testing API connections...")
        hubspot_ok = service.hubspot_fetcher.test_connection()
        livechat_ok = service.livechat_fetcher.test_connection()
        sheets_ok = service.sheets_exporter.authenticate()

        if all([hubspot_ok, livechat_ok, sheets_ok]):
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
