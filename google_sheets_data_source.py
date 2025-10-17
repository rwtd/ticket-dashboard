#!/usr/bin/env python3
"""
Google Sheets Data Source
Unified data access layer for reading from Google Sheets across the application
Used by: main app, widgets, AI query engine
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import warnings

# Suppress FutureWarnings from pandas
warnings.filterwarnings('ignore', category=FutureWarning)

import pandas as pd
import pytz

try:
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

logger = logging.getLogger(__name__)


class GoogleSheetsDataSource:
    """
    Unified data source for reading ticket and chat data from Google Sheets

    This class provides:
    - Cached data access with automatic refresh
    - Date range filtering
    - Fallback to local CSV files when Sheets unavailable
    - Thread-safe caching for widgets
    """

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str = 'service_account_credentials.json',
        cache_ttl_seconds: int = 300  # 5 minutes
    ):
        """
        Initialize Google Sheets data source

        Args:
            spreadsheet_id: Google Sheets ID
            credentials_path: Path to credentials file
            cache_ttl_seconds: Cache validity duration
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.cache_ttl_seconds = cache_ttl_seconds
        self.service = None

        # Cache
        self._tickets_cache = None
        self._chats_cache = None
        self._tickets_cache_time = None
        self._chats_cache_time = None

        # Scopes
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    def authenticate(self) -> bool:
        """Authenticate with Google Sheets API"""
        if not GOOGLE_AVAILABLE:
            logger.error("Google API client not available")
            return False

        try:
            creds = None

            # Try service account first
            if os.path.exists(self.credentials_path):
                try:
                    creds = ServiceAccountCredentials.from_service_account_file(
                        self.credentials_path,
                        scopes=self.scopes
                    )
                    logger.info("✅ Authenticated with service account")
                except Exception as e:
                    logger.warning(f"Service account auth failed: {e}")

            if not creds:
                logger.error("No valid credentials found")
                return False

            self.service = build('sheets', 'v4', credentials=creds)
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def _is_cache_valid(self, cache_time: Optional[datetime]) -> bool:
        """Check if cache is still valid"""
        if cache_time is None:
            return False
        elapsed = (datetime.now() - cache_time).total_seconds()
        return elapsed < self.cache_ttl_seconds

    def _read_sheet_to_dataframe(self, sheet_name: str) -> Optional[pd.DataFrame]:
        """
        Read a sheet and convert to DataFrame

        Args:
            sheet_name: Name of the sheet (e.g., 'Tickets', 'Chats')

        Returns:
            DataFrame or None
        """
        try:
            if self.service is None:
                if not self.authenticate():
                    return None

            # Read all data from sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:ZZ"  # Read all columns
            ).execute()

            values = result.get('values', [])

            if not values:
                logger.warning(f"Sheet '{sheet_name}' is empty")
                return None

            # First row is header
            headers = values[0]
            data_rows = values[1:]

            # Normalize data rows - pad rows that are shorter than headers
            normalized_data = []
            for row in data_rows:
                # Pad row with empty strings if it's shorter than headers
                if len(row) < len(headers):
                    row = row + [''] * (len(headers) - len(row))
                # Truncate row if it's longer than headers (shouldn't happen but be safe)
                elif len(row) > len(headers):
                    row = row[:len(headers)]
                normalized_data.append(row)

            # Create DataFrame with normalized data
            df = pd.DataFrame(normalized_data, columns=headers)

            logger.info(f"📊 Loaded {len(df)} rows from sheet '{sheet_name}'")
            return df

        except HttpError as e:
            if e.resp.status == 404:
                logger.error(f"Spreadsheet or sheet '{sheet_name}' not found")
            else:
                logger.error(f"HTTP error reading sheet: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read sheet '{sheet_name}': {e}")
            return None

    def get_tickets(
        self,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Get tickets data from Google Sheets

        Args:
            use_cache: Use cached data if available
            force_refresh: Force refresh even if cache valid

        Returns:
            DataFrame with tickets or None
        """
        try:
            # Check cache
            if use_cache and not force_refresh and self._is_cache_valid(self._tickets_cache_time):
                logger.debug("Using cached tickets data")
                return self._tickets_cache.copy() if self._tickets_cache is not None else None

            # Fetch from Sheets
            logger.info("📥 Fetching tickets from Google Sheets...")
            df = self._read_sheet_to_dataframe('Tickets')

            if df is not None:
                # Convert date columns
                date_columns = ['Create date', 'Last Modified Date', 'Close date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)

                utc_columns = [
                    'ticket_created_at_utc',
                    'ticket_last_modified_utc',
                    'ticket_closed_at_utc'
                ]
                for col in utc_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)

                if 'ticket_created_at_utc' not in df.columns or df['ticket_created_at_utc'].notna().sum() == 0:
                    candidates = [
                        ('Create date', False),
                        ('created_at', True),
                    ]
                    created_utc = None
                    for column, already_utc in candidates:
                        if column not in df.columns:
                            continue
                        parsed = pd.to_datetime(df[column], errors='coerce', utc=already_utc)
                        if parsed.notna().any():
                            created_utc = parsed.dt.tz_convert(pytz.UTC)
                            break

                    if created_utc is not None:
                        df['ticket_created_at_utc'] = created_utc
                        df['ticket_created_at_iso'] = created_utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                        eastern = pytz.timezone('US/Eastern')
                        df['Create date'] = created_utc.dt.tz_convert(eastern)

                # Convert numeric columns
                numeric_columns = ['First Response Time (Hours)', 'Ticket ID']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # Update cache
                self._tickets_cache = df
                self._tickets_cache_time = datetime.now()

                logger.info(f"✅ Loaded {len(df)} tickets from Google Sheets")

            return df.copy() if df is not None else None

        except Exception as e:
            logger.error(f"Failed to get tickets: {e}")
            return None

    def get_chats(
        self,
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Get chats data from Google Sheets

        Args:
            use_cache: Use cached data if available
            force_refresh: Force refresh even if cache valid

        Returns:
            DataFrame with chats or None
        """
        try:
            # Check cache
            if use_cache and not force_refresh and self._is_cache_valid(self._chats_cache_time):
                logger.debug("Using cached chats data")
                return self._chats_cache.copy() if self._chats_cache is not None else None

            # Fetch from Sheets
            logger.info("📥 Fetching chats from Google Sheets...")
            df = self._read_sheet_to_dataframe('Chats')

            if df is not None:
                # Convert date columns
                date_columns = ['chat_creation_date_utc', 'chat_creation_date_adt']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')

                # Convert numeric columns
                numeric_columns = ['rating_value', 'duration_minutes', 'first_response_time', 'bot_transfer']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # Convert boolean columns
                boolean_columns = ['has_rating']
                for col in boolean_columns:
                    if col in df.columns:
                        df[col] = df[col].astype(bool)

                utc_columns = [
                    'chat_created_at_utc',
                    'chat_started_at_utc'
                ]
                for col in utc_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)

                # Update cache
                self._chats_cache = df
                self._chats_cache_time = datetime.now()

                logger.info(f"✅ Loaded {len(df)} chats from Google Sheets")

            return df.copy() if df is not None else None

        except Exception as e:
            logger.error(f"Failed to get chats: {e}")
            return None

    def get_tickets_filtered(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pipeline: Optional[str] = None,
        owner: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get filtered tickets data

        Args:
            start_date: Filter by creation date >= start_date
            end_date: Filter by creation date <= end_date
            pipeline: Filter by pipeline name
            owner: Filter by case owner

        Returns:
            Filtered DataFrame or None
        """
        df = self.get_tickets()

        if df is None or df.empty:
            return None

        # Apply filters
        if start_date is not None and 'Create date' in df.columns:
            df = df[df['Create date'] >= start_date]

        if end_date is not None and 'Create date' in df.columns:
            df = df[df['Create date'] <= end_date]

        if pipeline is not None and 'Pipeline' in df.columns:
            df = df[df['Pipeline'] == pipeline]

        if owner is not None and 'Case Owner' in df.columns:
            df = df[df['Case Owner'] == owner]

        return df.copy()

    def get_chats_filtered(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get filtered chats data

        Args:
            start_date: Filter by creation date >= start_date
            end_date: Filter by creation date <= end_date
            agent_type: Filter by agent type ('bot' or 'human')
            agent_name: Filter by specific agent name

        Returns:
            Filtered DataFrame or None
        """
        df = self.get_chats()

        if df is None or df.empty:
            return None

        # Apply filters
        if start_date is not None and 'chat_creation_date_adt' in df.columns:
            df = df[df['chat_creation_date_adt'] >= start_date]

        if end_date is not None and 'chat_creation_date_adt' in df.columns:
            df = df[df['chat_creation_date_adt'] <= end_date]

        if agent_type is not None and 'agent_type' in df.columns:
            df = df[df['agent_type'] == agent_type]

        if agent_name is not None and 'display_agent' in df.columns:
            df = df[df['display_agent'] == agent_name]

        return df.copy()

    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about available data

        Returns:
            Dictionary with summary info
        """
        summary = {
            'tickets': {'available': False, 'count': 0, 'date_range': None},
            'chats': {'available': False, 'count': 0, 'date_range': None},
            'last_updated': None
        }

        try:
            # Get tickets summary
            df_tickets = self.get_tickets()
            if df_tickets is not None and not df_tickets.empty:
                summary['tickets']['available'] = True
                summary['tickets']['count'] = len(df_tickets)

                if 'Create date' in df_tickets.columns:
                    min_date = df_tickets['Create date'].min()
                    max_date = df_tickets['Create date'].max()
                    summary['tickets']['date_range'] = (min_date, max_date)

            # Get chats summary
            df_chats = self.get_chats()
            if df_chats is not None and not df_chats.empty:
                summary['chats']['available'] = True
                summary['chats']['count'] = len(df_chats)

                if 'chat_creation_date_adt' in df_chats.columns:
                    min_date = df_chats['chat_creation_date_adt'].min()
                    max_date = df_chats['chat_creation_date_adt'].max()
                    summary['chats']['date_range'] = (min_date, max_date)

            summary['last_updated'] = datetime.now()

        except Exception as e:
            logger.error(f"Failed to get data summary: {e}")

        return summary


# Singleton instance for app-wide use
_sheets_data_source = None


def get_sheets_data_source(
    spreadsheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None
) -> Optional[GoogleSheetsDataSource]:
    """
    Get or create singleton Google Sheets data source

    Args:
        spreadsheet_id: Google Sheets ID (uses env var if not provided)
        credentials_path: Credentials path (uses env var if not provided)

    Returns:
        GoogleSheetsDataSource instance or None
    """
    global _sheets_data_source

    if _sheets_data_source is None:
        # Get from environment if not provided
        if spreadsheet_id is None:
            spreadsheet_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
        if credentials_path is None:
            credentials_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')

        if not spreadsheet_id:
            logger.warning("No spreadsheet ID provided - Google Sheets data source unavailable")
            return None

        try:
            _sheets_data_source = GoogleSheetsDataSource(
                spreadsheet_id=spreadsheet_id,
                credentials_path=credentials_path
            )

            # Test authentication
            if not _sheets_data_source.authenticate():
                logger.warning("Google Sheets authentication failed - data source unavailable")
                _sheets_data_source = None
                return None

        except Exception as e:
            logger.error(f"Failed to create Google Sheets data source: {e}")
            return None

    return _sheets_data_source


# ============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# These functions provide backward compatibility with the old interface
# ============================================================================

def _load_local_tickets() -> Optional[pd.DataFrame]:
    """Load tickets from local CSV files as fallback"""
    try:
        tickets_dir = Path('tickets')
        if not tickets_dir.exists():
            logger.warning("Tickets directory not found")
            return None
        
        csv_files = list(tickets_dir.glob('*.csv'))
        if not csv_files:
            logger.warning("No ticket CSV files found")
            return None
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, low_memory=False)
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {e}")
        
        if not dfs:
            return None
        
        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined_df)} tickets from {len(dfs)} local CSV files")
        return combined_df
        
    except Exception as e:
        logger.error(f"Error loading local tickets: {e}")
        return None


def _load_local_chats() -> Optional[pd.DataFrame]:
    """Load chats from local CSV files as fallback"""
    try:
        chats_dir = Path('chats')
        if not chats_dir.exists():
            logger.warning("Chats directory not found")
            return None
        
        csv_files = list(chats_dir.glob('*.csv'))
        if not csv_files:
            logger.warning("No chat CSV files found")
            return None
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, low_memory=False)
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {e}")
        
        if not dfs:
            return None
        
        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined_df)} chats from {len(dfs)} local CSV files")
        return combined_df
        
    except Exception as e:
        logger.error(f"Error loading local chats: {e}")
        return None


def get_tickets_data(use_cache: bool = True, force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """
    Get tickets data from Google Sheets or fallback to local CSV
    
    Legacy compatibility function - provides the old simple interface
    
    Args:
        use_cache: Use cached data if available
        force_refresh: Force refresh even if cache valid
    
    Returns:
        DataFrame with tickets or None
    """
    try:
        # Try Google Sheets first
        sheets_source = get_sheets_data_source()
        if sheets_source:
            df = sheets_source.get_tickets(use_cache=use_cache, force_refresh=force_refresh)
            if df is not None and not df.empty:
                logger.info(f"Successfully loaded {len(df)} tickets from Google Sheets")
                return df
            else:
                logger.warning("Google Sheets returned empty tickets data")
        else:
            logger.info("Google Sheets not available, using local CSV fallback")
    
    except Exception as e:
        logger.error(f"Error fetching tickets from Google Sheets: {e}")
    
    # Fallback to local CSV
    logger.warning("Falling back to local CSV for tickets")
    return _load_local_tickets()


def get_chats_data(use_cache: bool = True, force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """
    Get chats data from Google Sheets or fallback to local CSV
    
    Legacy compatibility function - provides the old simple interface
    
    Args:
        use_cache: Use cached data if available
        force_refresh: Force refresh even if cache valid
    
    Returns:
        DataFrame with chats or None
    """
    try:
        # Try Google Sheets first
        sheets_source = get_sheets_data_source()
        if sheets_source:
            df = sheets_source.get_chats(use_cache=use_cache, force_refresh=force_refresh)
            if df is not None and not df.empty:
                logger.info(f"Successfully loaded {len(df)} chats from Google Sheets")
                return df
            else:
                logger.warning("Google Sheets returned empty chats data")
        else:
            logger.info("Google Sheets not available, using local CSV fallback")
    
    except Exception as e:
        logger.error(f"Error fetching chats from Google Sheets: {e}")
    
    # Fallback to local CSV
    logger.warning("Falling back to local CSV for chats")
    return _load_local_chats()


def main():
    """Test the data source"""
    logging.basicConfig(level=logging.INFO)

    # Get configuration from environment
    spreadsheet_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
    credentials_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')

    if not spreadsheet_id:
        logger.error("GOOGLE_SHEETS_SPREADSHEET_ID environment variable not set")
        return

    # Create data source
    ds = GoogleSheetsDataSource(spreadsheet_id, credentials_path)

    # Test authentication
    if not ds.authenticate():
        logger.error("Authentication failed")
        return

    # Get summary
    logger.info("\n📊 Data Summary:")
    summary = ds.get_data_summary()
    print(f"Tickets: {summary['tickets']['count']} available")
    print(f"Chats: {summary['chats']['count']} available")

    # Test tickets
    logger.info("\n🎫 Testing tickets fetch...")
    df_tickets = ds.get_tickets()
    if df_tickets is not None:
        print(f"Loaded {len(df_tickets)} tickets")
        print(f"Columns: {list(df_tickets.columns)[:10]}...")
        print(f"\nSample data:")
        print(df_tickets[['Ticket ID', 'Subject', 'Pipeline']].head())

    # Test chats
    logger.info("\n💬 Testing chats fetch...")
    df_chats = ds.get_chats()
    if df_chats is not None:
        print(f"Loaded {len(df_chats)} chats")
        print(f"Columns: {list(df_chats.columns)[:10]}...")
        print(f"\nSample data:")
        print(df_chats[['chat_id', 'agent_type', 'display_agent']].head())

    # Test filtering
    logger.info("\n🔍 Testing filtered queries...")
    last_30_days = datetime.now() - timedelta(days=30)
    df_recent_tickets = ds.get_tickets_filtered(start_date=last_30_days)
    if df_recent_tickets is not None:
        print(f"Found {len(df_recent_tickets)} tickets from last 30 days")


if __name__ == '__main__':
    main()
