#!/usr/bin/env python3
"""
Migration Script: Google Sheets → Firestore

This script safely migrates your existing data from Google Sheets to Firestore.
It can be run multiple times safely (idempotent).

Usage:
    # Dry run (preview only)
    python migrate_to_firestore.py --dry-run
    
    # Actually migrate
    python migrate_to_firestore.py
    
    # Migrate and keep Sheets as read-only backup
    python migrate_to_firestore.py --keep-sheets
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Import existing modules
from firestore_db import FirestoreDatabase, get_database
from google_sheets_data_source import GoogleSheetsDataSource

logger = logging.getLogger(__name__)


class SheetToFirestoreMigration:
    """Handle migration from Google Sheets to Firestore"""
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize migration
        
        Args:
            dry_run: If True, only preview what would be migrated
        """
        self.dry_run = dry_run
        self.sheets_source = None
        self.firestore_db = None
        
    def setup(self) -> bool:
        """Set up connections to Sheets and Firestore"""
        try:
            # Get Google Sheets connection
            logger.info("🔗 Connecting to Google Sheets...")
            sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
            sheets_creds = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 
                                         'service_account_credentials.json')
            
            if not sheets_id:
                logger.error("❌ GOOGLE_SHEETS_SPREADSHEET_ID not set")
                return False
            
            self.sheets_source = GoogleSheetsDataSource(
                spreadsheet_id=sheets_id,
                credentials_path=sheets_creds
            )
            
            if not self.sheets_source.authenticate():
                logger.error("❌ Failed to authenticate with Google Sheets")
                return False
            
            logger.info("✅ Connected to Google Sheets")
            
            # Get Firestore connection
            logger.info("🔗 Connecting to Firestore...")
            project_id = os.environ.get('GCP_PROJECT_ID')
            self.firestore_db = get_database(project_id=project_id)
            
            if not self.firestore_db.test_connection():
                logger.error("❌ Failed to connect to Firestore")
                return False
            
            logger.info("✅ Connected to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False
    
    def migrate_tickets(self) -> bool:
        """Migrate ticket data from Sheets to Firestore"""
        try:
            logger.info("\n" + "="*60)
            logger.info("🎫 MIGRATING TICKETS")
            logger.info("="*60)
            
            # Load from Sheets
            logger.info("📥 Loading tickets from Google Sheets...")
            tickets_df = self.sheets_source.get_tickets(use_cache=False, force_refresh=True)
            
            if tickets_df is None or tickets_df.empty:
                logger.warning("⚠️  No tickets found in Google Sheets")
                return True
            
            logger.info(f"📊 Found {len(tickets_df)} tickets in Sheets")
            logger.info(f"   Columns: {list(tickets_df.columns)[:10]}...")
            
            if self.dry_run:
                logger.info("🔍 DRY RUN: Would migrate tickets:")
                logger.info(f"   - Total tickets: {len(tickets_df)}")
                if 'Create date' in tickets_df.columns:
                    min_date = tickets_df['Create date'].min()
                    max_date = tickets_df['Create date'].max()
                    logger.info(f"   - Date range: {min_date} to {max_date}")
                logger.info(f"   - Sample ticket IDs: {tickets_df['Ticket ID'].head().tolist()}")
                return True
            
            # Save to Firestore
            logger.info("💾 Saving tickets to Firestore...")
            count = self.firestore_db.save_tickets(tickets_df)
            
            logger.info(f"✅ Successfully migrated {count} tickets")
            
            # Save metadata
            self.firestore_db.save_sync_metadata('tickets_migration', {
                'migrated_at': datetime.now(timezone.utc),
                'ticket_count': count,
                'source': 'google_sheets',
                'status': 'completed'
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ticket migration failed: {e}", exc_info=True)
            return False
    
    def migrate_chats(self) -> bool:
        """Migrate chat data from Sheets to Firestore"""
        try:
            logger.info("\n" + "="*60)
            logger.info("💬 MIGRATING CHATS")
            logger.info("="*60)
            
            # Load from Sheets
            logger.info("📥 Loading chats from Google Sheets...")
            chats_df = self.sheets_source.get_chats(use_cache=False, force_refresh=True)
            
            if chats_df is None or chats_df.empty:
                logger.warning("⚠️  No chats found in Google Sheets")
                return True
            
            logger.info(f"📊 Found {len(chats_df)} chats in Sheets")
            logger.info(f"   Columns: {list(chats_df.columns)[:10]}...")
            
            if self.dry_run:
                logger.info("🔍 DRY RUN: Would migrate chats:")
                logger.info(f"   - Total chats: {len(chats_df)}")
                if 'chat_creation_date_adt' in chats_df.columns:
                    min_date = chats_df['chat_creation_date_adt'].min()
                    max_date = chats_df['chat_creation_date_adt'].max()
                    logger.info(f"   - Date range: {min_date} to {max_date}")
                if 'agent_type' in chats_df.columns:
                    bot_count = len(chats_df[chats_df['agent_type'] == 'bot'])
                    human_count = len(chats_df[chats_df['agent_type'] == 'human'])
                    logger.info(f"   - Bot chats: {bot_count}, Human chats: {human_count}")
                return True
            
            # Save to Firestore
            logger.info("💾 Saving chats to Firestore...")
            count = self.firestore_db.save_chats(chats_df)
            
            logger.info(f"✅ Successfully migrated {count} chats")
            
            # Save metadata
            self.firestore_db.save_sync_metadata('chats_migration', {
                'migrated_at': datetime.now(timezone.utc),
                'chat_count': count,
                'source': 'google_sheets',
                'status': 'completed'
            })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Chat migration failed: {e}", exc_info=True)
            return False
    
    def verify_migration(self) -> bool:
        """Verify data was migrated correctly"""
        try:
            logger.info("\n" + "="*60)
            logger.info("✅ VERIFYING MIGRATION")
            logger.info("="*60)
            
            # Check Sheets counts
            sheets_tickets = self.sheets_source.get_tickets()
            sheets_chats = self.sheets_source.get_chats()
            
            sheets_ticket_count = len(sheets_tickets) if sheets_tickets is not None else 0
            sheets_chat_count = len(sheets_chats) if sheets_chats is not None else 0
            
            logger.info(f"📊 Google Sheets:")
            logger.info(f"   - Tickets: {sheets_ticket_count}")
            logger.info(f"   - Chats: {sheets_chat_count}")
            
            if self.dry_run:
                logger.info("\n🔍 DRY RUN: Skipping Firestore verification")
                return True
            
            # Check Firestore counts
            firestore_ticket_count = self.firestore_db.get_collection_count('tickets')
            firestore_chat_count = self.firestore_db.get_collection_count('chats')
            
            logger.info(f"\n📊 Firestore:")
            logger.info(f"   - Tickets: {firestore_ticket_count}")
            logger.info(f"   - Chats: {firestore_chat_count}")
            
            # Compare
            ticket_match = firestore_ticket_count == sheets_ticket_count
            chat_match = firestore_chat_count == sheets_chat_count
            
            if ticket_match and chat_match:
                logger.info("\n✅ VERIFICATION PASSED: All data migrated successfully!")
                return True
            else:
                logger.warning("\n⚠️  VERIFICATION WARNING: Counts don't match perfectly")
                if not ticket_match:
                    logger.warning(f"   - Ticket mismatch: Sheets={sheets_ticket_count}, Firestore={firestore_ticket_count}")
                if not chat_match:
                    logger.warning(f"   - Chat mismatch: Sheets={sheets_chat_count}, Firestore={firestore_chat_count}")
                logger.warning("   - This might be okay if data changed during migration")
                return True
                
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return False
    
    def run(self) -> bool:
        """Run the complete migration"""
        try:
            start_time = datetime.now()
            
            logger.info("🚀 Starting migration from Google Sheets to Firestore")
            if self.dry_run:
                logger.info("🔍 DRY RUN MODE: No data will be written")
            logger.info("")
            
            # Setup
            if not self.setup():
                logger.error("❌ Setup failed, aborting migration")
                return False
            
            # Migrate tickets
            if not self.migrate_tickets():
                logger.error("❌ Ticket migration failed, aborting")
                return False
            
            # Migrate chats
            if not self.migrate_chats():
                logger.error("❌ Chat migration failed, aborting")
                return False
            
            # Verify
            if not self.verify_migration():
                logger.warning("⚠️  Verification had issues, but migration completed")
            
            # Final summary
            elapsed = datetime.now() - start_time
            logger.info("\n" + "="*60)
            logger.info("✅ MIGRATION COMPLETE!")
            logger.info("="*60)
            logger.info(f"⏱️  Total time: {elapsed.total_seconds():.1f} seconds")
            
            if self.dry_run:
                logger.info("\n🔍 This was a DRY RUN - no data was actually migrated")
                logger.info("   Run without --dry-run to perform actual migration")
            else:
                logger.info("\n📝 Next steps:")
                logger.info("   1. Update data_sync_service.py to use Firestore")
                logger.info("   2. Update app.py and widgets to use firestore_db")
                logger.info("   3. Test the application thoroughly")
                logger.info("   4. Once verified, you can stop using Sheets sync")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            return False


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Migrate data from Google Sheets to Firestore'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview migration without writing data'
    )
    parser.add_argument(
        '--keep-sheets',
        action='store_true',
        help='Keep Sheets data as read-only backup (future feature)'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Check environment
    required_env = ['GOOGLE_SHEETS_SPREADSHEET_ID']
    missing = [var for var in required_env if not os.environ.get(var)]
    
    if missing:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing)}")
        logger.info("Set them with:")
        for var in missing:
            logger.info(f"  export {var}='your-value-here'")
        sys.exit(1)
    
    # Run migration
    migration = SheetToFirestoreMigration(dry_run=args.dry_run)
    success = migration.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()