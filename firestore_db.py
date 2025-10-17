#!/usr/bin/env python3
"""
Firestore Database Layer for Ticket Dashboard
Clean, simple replacement for Google Sheets as primary data store

This module provides:
- Simple CRUD operations for tickets and chats
- Efficient batch operations
- Query filtering by date range, agent, pipeline
- Automatic indexing and performance
- Zero maintenance required
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import pytz

try:
    from google.cloud import firestore
    from google.api_core import retry
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class FirestoreDatabase:
    """
    Clean database layer using Firestore in Datastore mode
    
    Collections:
    - tickets: Support ticket records
    - chats: LiveChat conversation records
    - sync_metadata: Last sync timestamps and status
    """
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize Firestore client
        
        Args:
            project_id: GCP project ID (auto-detected if not provided)
        """
        if not FIRESTORE_AVAILABLE:
            raise ImportError(
                "Firestore client not available. Install with: "
                "pip install google-cloud-firestore"
            )
        
        try:
            import os
            # Quick check: if GOOGLE_APPLICATION_CREDENTIALS is missing, fail fast
            if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') and not os.environ.get('FIRESTORE_EMULATOR_HOST'):
                # Check if running on GCP (auto-credentials available)
                try:
                    import google.auth
                    _, project = google.auth.default()
                    if not project:
                        raise ValueError("No GCP project found - auth likely unavailable")
                except Exception:
                    logger.warning("⚠️ Firestore credentials not found, skipping Firestore")
                    self.db = None
                    return
            
            if project_id:
                self.db = firestore.Client(project=project_id)
            else:
                self.db = firestore.Client()
            
            logger.info("✅ Firestore database initialized")
            
        except Exception as e:
            # Don't spam auth errors
            if "Reauthentication" not in str(e) and "ALTS" not in str(e):
                logger.error(f"Failed to initialize Firestore: {e}")
            else:
                logger.warning("⚠️ Firestore auth unavailable, using fallback data sources")
            # Set db to None instead of raising - let callers handle fallback
            self.db = None
    
    # ============================================================================
    # TICKETS
    # ============================================================================
    
    def save_tickets(self, tickets_df: pd.DataFrame) -> int:
        """
        Save or update tickets in batch
        
        Args:
            tickets_df: DataFrame with ticket data
            
        Returns:
            Number of tickets saved
        """
        if tickets_df.empty:
            logger.warning("No tickets to save")
            return 0
        
        try:
            batch = self.db.batch()
            count = 0
            
            for idx, row in tickets_df.iterrows():
                # Use Ticket ID as document ID
                ticket_id = str(row.get('Ticket ID') or row.get('ticket_id') or idx)
                doc_ref = self.db.collection('tickets').document(ticket_id)
                
                # Convert row to dict, handling timestamps
                data = self._prepare_ticket_data(row)
                
                batch.set(doc_ref, data, merge=True)
                count += 1
                
                # Firestore batch limit is 500 operations
                if count % 500 == 0:
                    batch.commit()
                    batch = self.db.batch()
                    logger.info(f"💾 Saved batch of {count} tickets...")
            
            # Commit remaining
            if count % 500 != 0:
                batch.commit()
            
            logger.info(f"✅ Saved {count} tickets to Firestore")
            return count
            
        except Exception as e:
            logger.error(f"Failed to save tickets: {e}")
            raise
    
    def get_tickets(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pipeline: Optional[str] = None,
        owner: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Retrieve tickets with optional filtering
        
        Args:
            start_date: Filter by create date >= start_date
            end_date: Filter by create date <= end_date
            pipeline: Filter by pipeline name
            owner: Filter by case owner
            limit: Maximum number of tickets to return
            
        Returns:
            DataFrame with ticket data
        """
        try:
            query = self.db.collection('tickets')
            
            # Apply filters
            if start_date:
                # Ensure timezone aware
                if start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=timezone.utc)
                query = query.where('create_date', '>=', start_date)
            
            if end_date:
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                query = query.where('create_date', '<=', end_date)
            
            if pipeline:
                query = query.where('pipeline', '==', pipeline)
            
            if owner:
                query = query.where('case_owner', '==', owner)
            
            # Add ordering
            query = query.order_by('create_date', direction=firestore.Query.DESCENDING)
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            docs = query.stream()
            
            # Convert to DataFrame
            tickets = [doc.to_dict() for doc in docs]
            
            if not tickets:
                logger.warning("No tickets found matching criteria")
                return pd.DataFrame()
            
            df = pd.DataFrame(tickets)
            
            # Convert timestamps back to datetime
            df = self._restore_ticket_timestamps(df)
            
            logger.info(f"📥 Retrieved {len(df)} tickets from Firestore")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return pd.DataFrame()
    
    def delete_old_tickets(self, days: int = 365) -> int:
        """
        Delete tickets older than specified days (for data retention)
        
        Args:
            days: Delete tickets older than this many days
            
        Returns:
            Number of tickets deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Query old tickets
            query = self.db.collection('tickets').where('create_date', '<', cutoff_date)
            docs = query.stream()
            
            # Delete in batches
            batch = self.db.batch()
            count = 0
            
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                
                if count % 500 == 0:
                    batch.commit()
                    batch = self.db.batch()
                    logger.info(f"🗑️  Deleted {count} old tickets...")
            
            if count % 500 != 0:
                batch.commit()
            
            logger.info(f"✅ Deleted {count} tickets older than {days} days")
            return count
            
        except Exception as e:
            logger.error(f"Failed to delete old tickets: {e}")
            return 0
    
    # ============================================================================
    # CHATS
    # ============================================================================
    
    def save_chats(self, chats_df: pd.DataFrame) -> int:
        """
        Save or update chats in batch
        
        Args:
            chats_df: DataFrame with chat data
            
        Returns:
            Number of chats saved
        """
        if chats_df.empty:
            logger.warning("No chats to save")
            return 0
        
        try:
            batch = self.db.batch()
            count = 0
            
            for idx, row in chats_df.iterrows():
                # Use chat ID as document ID
                chat_id = str(row.get('chat_id') or idx)
                doc_ref = self.db.collection('chats').document(chat_id)
                
                # Convert row to dict, handling timestamps
                data = self._prepare_chat_data(row)
                
                batch.set(doc_ref, data, merge=True)
                count += 1
                
                if count % 500 == 0:
                    batch.commit()
                    batch = self.db.batch()
                    logger.info(f"💾 Saved batch of {count} chats...")
            
            if count % 500 != 0:
                batch.commit()
            
            logger.info(f"✅ Saved {count} chats to Firestore")
            return count
            
        except Exception as e:
            logger.error(f"Failed to save chats: {e}")
            raise
    
    def get_chats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Retrieve chats with optional filtering
        
        Args:
            start_date: Filter by creation date >= start_date
            end_date: Filter by creation date <= end_date
            agent_type: Filter by agent type ('bot' or 'human')
            agent_name: Filter by specific agent name
            limit: Maximum number of chats to return
            
        Returns:
            DataFrame with chat data
        """
        try:
            query = self.db.collection('chats')
            
            # Apply filters - use chat_creation_date_adt (Firestore Timestamp) for proper date filtering
            if start_date:
                if start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=timezone.utc)
                query = query.where('chat_creation_date_adt', '>=', start_date)
            
            if end_date:
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                query = query.where('chat_creation_date_adt', '<=', end_date)
            
            if agent_type:
                query = query.where('agent_type', '==', agent_type)
            
            if agent_name:
                query = query.where('display_agent', '==', agent_name)
            
            # Add ordering - use chat_creation_date_adt for consistency
            query = query.order_by('chat_creation_date_adt', direction=firestore.Query.DESCENDING)
            
            if limit:
                query = query.limit(limit)
            
            # Execute query
            docs = query.stream()
            
            # Convert to DataFrame
            chats = [doc.to_dict() for doc in docs]
            
            if not chats:
                logger.warning("No chats found matching criteria")
                return pd.DataFrame()
            
            df = pd.DataFrame(chats)
            
            # Convert timestamps back to datetime
            df = self._restore_chat_timestamps(df)
            
            logger.info(f"📥 Retrieved {len(df)} chats from Firestore")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get chats: {e}")
            return pd.DataFrame()
    
    # ============================================================================
    # SYNC METADATA
    # ============================================================================
    
    def save_sync_metadata(self, sync_type: str, metadata: Dict[str, Any]) -> bool:
        """
        Save sync metadata (last sync time, status, etc.)
        
        Args:
            sync_type: Type of sync ('tickets', 'chats', 'full')
            metadata: Metadata dictionary
            
        Returns:
            True if successful
        """
        try:
            doc_ref = self.db.collection('sync_metadata').document(sync_type)
            metadata['updated_at'] = datetime.now(timezone.utc)
            doc_ref.set(metadata, merge=True)
            return True
        except Exception as e:
            logger.error(f"Failed to save sync metadata: {e}")
            return False
    
    def get_sync_metadata(self, sync_type: str) -> Optional[Dict[str, Any]]:
        """
        Get sync metadata
        
        Args:
            sync_type: Type of sync ('tickets', 'chats', 'full')
            
        Returns:
            Metadata dictionary or None
        """
        try:
            doc_ref = self.db.collection('sync_metadata').document(sync_type)
            doc = doc_ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"Failed to get sync metadata: {e}")
            return None
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _prepare_ticket_data(self, row: pd.Series) -> Dict[str, Any]:
        """Prepare ticket data for Firestore storage"""
        data = {}
        
        # Map common column names to standardized keys
        column_mapping = {
            'Ticket ID': 'ticket_id',
            'Subject': 'subject',
            'Pipeline': 'pipeline',
            'Pipeline Stage': 'pipeline_stage',
            'Create date': 'create_date',
            'Last Modified Date': 'last_modified_date',
            'Close date': 'close_date',
            'First agent email response date': 'first_agent_response_date',
            'first_agent_reply_date': 'first_agent_response_date',
            'Case Owner': 'case_owner',
            'Ticket owner': 'case_owner',
            'Priority': 'priority',
            'Description': 'description',
            'First Response Time (Hours)': 'first_response_hours',
            'Weekend_Ticket': 'is_weekend',
        }
        
        for col, key in column_mapping.items():
            if col in row.index and pd.notna(row[col]):
                value = row[col]
                
                # Handle timestamps
                if 'date' in col.lower() and isinstance(value, (pd.Timestamp, datetime)):
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)
                    data[key] = value
                # Handle booleans
                elif isinstance(value, (bool, pd.BooleanDtype)):
                    data[key] = bool(value)
                # Handle numbers
                elif isinstance(value, (int, float)) and not pd.isna(value):
                    data[key] = float(value) if isinstance(value, float) else int(value)
                # Handle strings
                else:
                    data[key] = str(value)
        
        # Add any additional columns not in mapping
        for col in row.index:
            if col not in column_mapping and pd.notna(row[col]):
                key = col.lower().replace(' ', '_').replace('(', '').replace(')', '')
                if key not in data:
                    data[key] = str(row[col])
        
        return data
    
    def _prepare_chat_data(self, row: pd.Series) -> Dict[str, Any]:
        """Prepare chat data for Firestore storage"""
        data = {}
        
        # Store ALL columns to preserve raw data for chat processor
        column_mapping = {
            'chat_id': 'chat_id',
            'chat_creation_date_utc': 'chat_creation_date',
            'chat_creation_date_adt': 'chat_creation_date_adt',
            'chat_start_date': 'chat_start_date',
            'primary_agent': 'primary_agent',
            'primary_agent_raw': 'primary_agent_raw',
            'secondary_agent': 'secondary_agent',
            'secondary_agent_raw': 'secondary_agent_raw',
            'display_agent': 'display_agent',
            'agent_type': 'agent_type',
            'bot_transfer': 'bot_transfer',
            'rating_value': 'rating_value',
            'has_rating': 'has_rating',
            'rate_raw': 'rate_raw',
            'duration_minutes': 'duration_minutes',
            'duration_seconds': 'duration_seconds',
            'duration_raw': 'duration_raw',
            'first_response_time': 'first_response_time',
            'first_response_raw': 'first_response_raw',
            'avg_response_time': 'avg_response_time',
            'avg_response_raw': 'avg_response_raw',
            'country_raw': 'country_raw',
            'tag1_raw': 'tag1_raw',
            'tag2_raw': 'tag2_raw',
            'date': 'date',
            'hour': 'hour',
            'day_of_week': 'day_of_week',
        }
        
        for col, key in column_mapping.items():
            if col in row.index:
                # Special handling for rate_raw - always include it even if empty/NA
                # This is critical because chat_processor needs it to calculate rating_value
                if col == 'rate_raw':
                    value = row[col]
                    # Store empty string for NA/None to preserve the column
                    data[key] = str(value) if pd.notna(value) else ''
                    continue
                
                if pd.notna(row[col]):
                    value = row[col]
                    
                    if 'date' in col and isinstance(value, (pd.Timestamp, datetime)):
                        if value.tzinfo is None:
                            value = value.replace(tzinfo=timezone.utc)
                        data[key] = value
                    elif isinstance(value, (bool, pd.BooleanDtype)):
                        data[key] = bool(value)
                    elif isinstance(value, (int, float)) and not pd.isna(value):
                        data[key] = float(value) if isinstance(value, float) else int(value)
                    else:
                        data[key] = str(value)
        
        # Add any additional columns not in mapping
        for col in row.index:
            if col not in column_mapping and pd.notna(row[col]):
                key = col.lower().replace(' ', '_').replace('(', '').replace(')', '')
                if key not in data:
                    value = row[col]
                    if isinstance(value, (pd.Timestamp, datetime)):
                        if value.tzinfo is None:
                            value = value.replace(tzinfo=timezone.utc)
                        data[key] = value
                    else:
                        data[key] = str(value)
        
        return data
    
    def _restore_ticket_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert Firestore timestamps back to pandas datetime and restore original column names"""
        timestamp_columns = ['create_date', 'last_modified_date', 'close_date', 'first_agent_reply_date', 'first_agent_response_date']
        
        for col in timestamp_columns:
            if col in df.columns:
                # Use format='ISO8601' to handle various ISO timestamp formats
                df[col] = pd.to_datetime(df[col], format='ISO8601', utc=True)
        
        # Restore original CSV column names (ticket_processor expects these exact names)
        column_mapping = {
            'ticket_id': 'Ticket ID',
            'subject': 'Subject',
            'pipeline': 'Pipeline',
            'pipeline_stage': 'Pipeline Stage',
            'create_date': 'Create date',
            'last_modified_date': 'Last Modified Date',
            'close_date': 'Close date',
            'first_agent_response_date': 'First agent email response date',
            'first_agent_reply_date': 'First agent email response date',  # Map the actual Firestore column
            'case_owner': 'Case Owner',
            'priority': 'Priority',
            'description': 'Description',
            'first_response_hours': 'First Response Time (Hours)',
            'is_weekend': 'Weekend_Ticket',
        }
        
        # Only rename columns that exist in the DataFrame
        rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        return df
    
    def _restore_chat_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert Firestore timestamps back to pandas datetime and restore original column names"""
        timestamp_columns = ['chat_creation_date', 'chat_creation_date_adt', 'chat_start_date']
        
        for col in timestamp_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True)
        
        # Restore original column names (chat_processor expects these exact names)
        # Note: We keep the column names as-is since we're storing them with their original names
        column_mapping = {
            'chat_creation_date': 'chat_creation_date_utc',
        }
        
        # Only rename columns that exist in the DataFrame
        rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)
        
        return df
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_collection_count(self, collection_name: str) -> int:
        """Get document count for a collection"""
        try:
            # Note: This is inefficient for large collections
            # Consider using aggregation queries in production
            docs = self.db.collection(collection_name).stream()
            return sum(1 for _ in docs)
        except Exception as e:
            logger.error(f"Failed to count {collection_name}: {e}")
            return 0
    
    def test_connection(self) -> bool:
        """Test Firestore connection"""
        try:
            # Try to read from sync_metadata (lightweight)
            doc_ref = self.db.collection('sync_metadata').document('test')
            doc_ref.set({'test': True, 'timestamp': datetime.now(timezone.utc)})
            doc = doc_ref.get()
            
            if doc.exists:
                logger.info("✅ Firestore connection successful")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Firestore connection failed: {e}")
            return False


# Convenience function for singleton pattern
_db_instance = None

def get_database(project_id: Optional[str] = None) -> FirestoreDatabase:
    """Get or create singleton database instance"""
    global _db_instance
    
    if _db_instance is None:
        _db_instance = FirestoreDatabase(project_id=project_id)
    
    return _db_instance


def main():
    """Test the database"""
    import os
    logging.basicConfig(level=logging.INFO)
    
    # Initialize
    project_id = os.environ.get('GCP_PROJECT_ID')
    db = FirestoreDatabase(project_id=project_id)
    
    # Test connection
    if db.test_connection():
        print("✅ Database connected and working!")
        
        # Show counts
        ticket_count = db.get_collection_count('tickets')
        chat_count = db.get_collection_count('chats')
        
        print(f"\n📊 Current data:")
        print(f"  Tickets: {ticket_count}")
        print(f"  Chats: {chat_count}")
    else:
        print("❌ Database connection failed")


if __name__ == '__main__':
    main()