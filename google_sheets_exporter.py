#!/usr/bin/env python3
"""
Google Sheets Exporter for Ticket Dashboard
Handles rolling 365-day data exports with upsert functionality
"""

import os
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import time

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

class GoogleSheetsExporter:
    """Export and sync ticket/chat data to Google Sheets with rolling 365-day windows"""
    
    def __init__(self, credentials_path: str = 'service_account_credentials.json', token_path: str = 'token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
        
    def authenticate(self) -> bool:
        """Authenticate with Google Sheets API"""
        if not GOOGLE_AVAILABLE:
            logger.error("Google API client not available. Install with: pip install google-api-python-client google-auth")
            return False
            
        try:
            creds = None
            
            # Try to load existing token
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
                
            # If there are no valid credentials, try service account
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(self.credentials_path):
                    # Try service account credentials first
                    try:
                        creds = ServiceAccountCredentials.from_service_account_file(
                            self.credentials_path, scopes=self.scopes)
                        logger.info("Using service account authentication")
                    except Exception:
                        # Try OAuth flow for desktop apps
                        try:
                            from google_auth_oauthlib.flow import InstalledAppFlow
                            
                            flow = InstalledAppFlow.from_client_secrets_file(
                                self.credentials_path, 
                                scopes=self.scopes
                            )
                            
                            # Run local server for OAuth callback
                            creds = flow.run_local_server(port=0, prompt='consent')
                            
                            # Save the credentials for future use
                            with open(self.token_path, 'w') as token:
                                token.write(creds.to_json())
                                
                        except Exception as e:
                            logger.error(f"OAuth flow failed: {e}")
                            logger.error("Could not authenticate with service account or user credentials")
                            return False
                else:
                    logger.error(f"No valid credentials found. Please ensure {self.credentials_path} exists")
                    return False
                    
            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("✅ Google Sheets API authenticated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    def create_spreadsheet(self, title: str) -> Optional[str]:
        """Create a new Google Sheet and return its ID"""
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                },
                'sheets': [
                    {
                        'properties': {
                            'title': 'Tickets',
                            'gridProperties': {
                                'frozenRowCount': 1  # Freeze header row
                            }
                        }
                    },
                    {
                        'properties': {
                            'title': 'Chats', 
                            'gridProperties': {
                                'frozenRowCount': 1
                            }
                        }
                    },
                    {
                        'properties': {
                            'title': 'Sync_Log',
                            'gridProperties': {
                                'frozenRowCount': 1
                            }
                        }
                    },
                    {
                        'properties': {
                            'title': 'Dashboard_Metrics',
                            'gridProperties': {
                                'frozenRowCount': 1
                            }
                        }
                    }
                ]
            }
            
            result = self.service.spreadsheets().create(body=spreadsheet).execute()
            spreadsheet_id = result['spreadsheetId']
            
            # Make the sheet publicly readable (optional)
            try:
                from googleapiclient.discovery import build as drive_build
                drive_service = build('drive', 'v3', credentials=self.service._http.credentials)
                drive_service.permissions().create(
                    fileId=spreadsheet_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
            except Exception:
                pass  # Permission setting failed, but sheet was created
                
            logger.info(f"✅ Created Google Sheet: {title} (ID: {spreadsheet_id})")
            return spreadsheet_id
            
        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {str(e)}")
            return None
    
    def get_rolling_window_data(self, df: pd.DataFrame, days: int = 365) -> pd.DataFrame:
        """Get data for rolling window (default 365 days)"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Ensure Create date is datetime
        if 'Create date' in df.columns:
            df['Create date'] = pd.to_datetime(df['Create date'], errors='coerce', utc=True)
            
            # Make cutoff_date timezone aware to match
            import pytz
            cutoff_date = pytz.UTC.localize(cutoff_date)
            
            return df[df['Create date'] >= cutoff_date].copy()
        return df
    
    def prepare_data_for_sheets(self, df: pd.DataFrame, data_type: str) -> List[List]:
        """Prepare dataframe for Google Sheets format with enhanced calculated fields"""
        # Get rolling window data
        df_filtered = self.get_rolling_window_data(df)
        
        # Add calculated fields specific to data type
        df_enhanced = self._add_calculated_fields(df_filtered.copy(), data_type)
        
        # Add metadata columns
        df_enhanced['Last_Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df_enhanced['Data_Type'] = data_type

        # Convert datetime columns to ISO strings BEFORE converting everything to string
        # This prevents NaT from becoming the string "NaT"
        for col in df_enhanced.columns:
            if pd.api.types.is_datetime64_any_dtype(df_enhanced[col]):
                # Convert datetime to ISO string, NaT becomes empty string
                df_enhanced[col] = df_enhanced[col].apply(
                    lambda x: x.isoformat() if pd.notna(x) else ''
                )

        # Convert to string and truncate long values for Google Sheets limits
        df_str = df_enhanced.astype(str).fillna('')

        # Replace any remaining "NaT", "nan", "None" strings with empty strings
        df_str = df_str.replace(['NaT', 'nan', 'None', '<NA>'], '')
        
        # Truncate cells that exceed Google Sheets character limit (50,000)
        for col in df_str.columns:
            mask = df_str[col].str.len() > 49000  # Leave some buffer
            if mask.any():
                df_str.loc[mask, col] = df_str.loc[mask, col].str[:49000] + '...[TRUNCATED]'
                truncated_count = mask.sum()
                logger.info(f"⚠️ Truncated {truncated_count} values in column '{col}' (exceeded 50k chars)")
        
        # Prepare header and data
        headers = df_str.columns.tolist()
        data = [headers] + df_str.values.tolist()
        
        logger.info(f"✅ Prepared {len(data)-1:,} {data_type} records for Google Sheets (with calculated fields)")
        return data
    
    def _add_calculated_fields(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Add calculated fields not present in source data"""
        try:
            if data_type.lower() == 'tickets':
                df = self._add_ticket_calculated_fields(df)
            elif data_type.lower() == 'chats':
                df = self._add_chat_calculated_fields(df)
                
            logger.info(f"✅ Added calculated fields for {data_type}")
            return df
            
        except Exception as e:
            logger.warning(f"Could not add calculated fields: {e}")
            return df
    
    def _add_ticket_calculated_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add calculated fields specific to ticket data"""
        import pytz
        
        # Ensure Create date is properly formatted
        if 'Create date' in df.columns:
            df['Create date'] = pd.to_datetime(df['Create date'], errors='coerce')
            
            # Add day of week (Monday=1, Sunday=7)
            df['Day_of_Week_Number'] = df['Create date'].dt.dayofweek + 1  # pandas uses 0=Monday
            df['Day_of_Week_Name'] = df['Create date'].dt.day_name()
            
            # Add weekend/weekday boolean (Saturday=6, Sunday=0 in pandas dayofweek)
            df['Is_Weekend'] = df['Create date'].dt.dayofweek.isin([5, 6])  # Saturday, Sunday
            df['Is_Weekday'] = ~df['Is_Weekend']
            
            # Add fiscal year quarter (calendar aligned)
            df['FY_Quarter'] = df['Create date'].dt.quarter
            df['FY_Quarter_Name'] = 'Q' + df['FY_Quarter'].astype(str)
            df['FY_Year'] = df['Create date'].dt.year
            df['FY_Quarter_Full'] = df['FY_Year'].astype(str) + '-' + df['FY_Quarter_Name']
            
            # Add month name for additional granularity
            df['Month_Number'] = df['Create date'].dt.month
            df['Month_Name'] = df['Create date'].dt.month_name()
            df['Month_Year'] = df['Create date'].dt.strftime('%Y-%m (%B)')  # 2025-01 (January)
        
        # Add response time calculations if not already present
        if 'First Response Time (Hours)' not in df.columns and 'First agent email response date' in df.columns:
            df = self._calculate_response_time(df)
        elif 'First Response Time (Hours)' in df.columns:
            # Clean up response time field for better readability
            response_times = pd.to_numeric(df['First Response Time (Hours)'], errors='coerce')
            df['Response_Time_Hours_Clean'] = response_times.round(2)
            df['Response_Time_Days'] = (response_times / 24).round(2)
            df['Response_Time_Category'] = pd.cut(response_times, 
                                                bins=[0, 1, 4, 24, 72, float('inf')],
                                                labels=['< 1 hour', '1-4 hours', '4-24 hours', '1-3 days', '3+ days'],
                                                include_lowest=True)
        
        # Add business hours calculation
        if 'Create date' in df.columns:
            df['Created_During_Business_Hours'] = self._is_business_hours(df['Create date'])
        
        # Add ticket age in days
        if 'Create date' in df.columns:
            now = datetime.now(pytz.UTC)
            df['Ticket_Age_Days'] = (now - df['Create date']).dt.total_seconds() / (24 * 3600)
            df['Ticket_Age_Days'] = df['Ticket_Age_Days'].round(1)
        
        # Add QA scoring fields (empty initially - to be populated from separate QA sheet)
        df = self._add_qa_scoring_fields(df)
        
        return df
    
    def _add_qa_scoring_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add QA scoring fields to be populated from separate QA tracking sheet"""
        
        qa_fields = [
            'QA - Evaluator Name',
            'QA - Ticket ID', 
            'QA - Channel',
            'QA - Date of Interaction',
            'QA - 1. Revenue Opportunity',
            'QA - 2. SLA Adherence',
            'QA - 2a.',
            'QA - 3. SLA Miss Reason',
            'QA - 4. Unnecessary Interactions',
            'QA - 5. Technical Accuracy & Problem Resolution',
            'QA - 5a.',
            'QA - 6. Communication & Professionalism',
            'QA - 6a.',
            'QA - 7. Customer Service & Experience',
            'QA - 7a.',
            'QA - 8. Process Adherence & Efficiency',
            'QA - 8a.',
            'QA - 9. Case Management & Documentation',
            'QA - 9a.',
            'QA - 10. Customer Growth & Health',
            'QA - 10a.',
            'QA - 11. Revenue Impact Assessment',
            'QA - 12. Identified Root Cause',
            'QA - 12a.',
            'QA - 13. Suggestions for Deflection',
            'QA - 14. Tag for Systemic Review?',
            'QA - 15. Additional Comments / Coaching',
            'QA - Overall Performance Rating'
        ]
        
        # Initialize all QA fields as empty (to be populated later via scripting)
        for field in qa_fields:
            df[field] = ''
        
        logger.info(f"✅ Added {len(qa_fields)} QA scoring fields (ready for external population)")
        return df
    
    def _add_chat_calculated_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add calculated fields specific to chat data"""
        # Detect likely date column for chats
        date_col = None
        for col in ['chat_creation_date', 'Create date', 'Started at', 'Date']:
            if col in df.columns:
                date_col = col
                break
        
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            
            # Add day of week
            df['Day_of_Week_Number'] = df[date_col].dt.dayofweek + 1
            df['Day_of_Week_Name'] = df[date_col].dt.day_name()
            
            # Add weekend/weekday boolean
            df['Is_Weekend'] = df[date_col].dt.dayofweek.isin([5, 6])
            df['Is_Weekday'] = ~df['Is_Weekend']
            
            # Add fiscal year quarter (calendar aligned)
            df['FY_Quarter'] = df[date_col].dt.quarter
            df['FY_Quarter_Name'] = 'Q' + df['FY_Quarter'].astype(str)
            df['FY_Year'] = df[date_col].dt.year
            df['FY_Quarter_Full'] = df[date_col].dt.year.astype(str) + '-' + df['FY_Quarter_Name']
            
            # Add month name for additional granularity
            df['Month_Number'] = df[date_col].dt.month
            df['Month_Name'] = df[date_col].dt.month_name()
            df['Month_Year'] = df[date_col].dt.strftime('%Y-%m (%B)')  # 2025-01 (January)
            
            # Add hour of day for chat volume analysis
            df['Hour_of_Day'] = df[date_col].dt.hour
            df['Time_Period'] = pd.cut(df['Hour_of_Day'],
                                     bins=[0, 6, 12, 18, 24],
                                     labels=['Night (0-6)', 'Morning (6-12)', 'Afternoon (12-18)', 'Evening (18-24)'],
                                     include_lowest=True)
        
        # Add response time from duration if available
        if 'duration_seconds' in df.columns:
            duration_secs = pd.to_numeric(df['duration_seconds'], errors='coerce')
            df['Duration_Minutes'] = (duration_secs / 60).round(2)
            df['Duration_Hours'] = (duration_secs / 3600).round(2)
        
        # Add QA scoring fields for chats (same structure as tickets)
        df = self._add_qa_scoring_fields(df)
        
        return df
    
    def _calculate_response_time(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate response time from create date and first response date"""
        if 'First agent email response date' in df.columns and 'Create date' in df.columns:
            create_date = pd.to_datetime(df['Create date'], errors='coerce')
            response_date = pd.to_datetime(df['First agent email response date'], errors='coerce')
            
            # Calculate time difference in hours
            time_diff = response_date - create_date
            response_hours = time_diff.dt.total_seconds() / 3600
            
            # Only keep positive response times
            response_hours = response_hours.where(response_hours > 0)
            
            df['First_Response_Time_Hours'] = response_hours.round(2)
            df['First_Response_Time_Days'] = (response_hours / 24).round(2)
            
        return df
    
    def _is_business_hours(self, date_series: pd.Series) -> pd.Series:
        """Determine if timestamp falls during business hours (9 AM - 5 PM, Mon-Fri)"""
        # Convert to local timezone (assuming EDT/EST)
        import pytz
        eastern = pytz.timezone('US/Eastern')
        
        # Convert to Eastern time
        local_times = date_series.dt.tz_convert(eastern)
        
        # Check if weekday (Monday=0, Sunday=6)
        is_weekday = local_times.dt.dayofweek < 5
        
        # Check if between 9 AM and 5 PM
        hour = local_times.dt.hour
        is_business_hour = (hour >= 9) & (hour < 17)
        
        return is_weekday & is_business_hour
    
    def integrate_qa_data(self, main_df: pd.DataFrame, qa_df: pd.DataFrame, 
                         join_key: str = 'Ticket ID') -> pd.DataFrame:
        """
        Integrate QA scoring data from separate sheet into main dataset
        
        Args:
            main_df: Main ticket/chat dataframe
            qa_df: QA scoring dataframe with evaluations
            join_key: Column name to join on (default: 'Ticket ID')
            
        Returns:
            Enhanced dataframe with QA scores populated
        """
        try:
            # Ensure join key exists in both dataframes
            if join_key not in main_df.columns:
                logger.error(f"Join key '{join_key}' not found in main dataset")
                return main_df
                
            if join_key not in qa_df.columns:
                logger.error(f"Join key '{join_key}' not found in QA dataset")
                return main_df
            
            # Create a mapping from QA data (Ticket ID -> QA scores)
            qa_columns = [col for col in qa_df.columns if col.startswith('QA - ')]
            if not qa_columns:
                # If QA data doesn't have QA- prefix, add it
                qa_data_clean = qa_df.copy()
                for col in qa_df.columns:
                    if col != join_key and not col.startswith('QA - '):
                        qa_data_clean[f'QA - {col}'] = qa_data_clean[col]
                        qa_data_clean.drop(columns=[col], inplace=True)
                qa_columns = [col for col in qa_data_clean.columns if col.startswith('QA - ')]
            else:
                qa_data_clean = qa_df
            
            # Merge QA data into main dataset
            enhanced_df = main_df.copy()
            
            # Left join to preserve all main data records
            for ticket_id in qa_data_clean[join_key].unique():
                if pd.isna(ticket_id):
                    continue
                    
                # Find matching records in main dataset
                main_mask = enhanced_df[join_key] == ticket_id
                if main_mask.any():
                    # Get QA scores for this ticket
                    qa_scores = qa_data_clean[qa_data_clean[join_key] == ticket_id].iloc[0]
                    
                    # Update QA fields in main dataset
                    for qa_col in qa_columns:
                        if qa_col in qa_scores.index:
                            enhanced_df.loc[main_mask, qa_col] = qa_scores[qa_col]
            
            populated_count = enhanced_df[enhanced_df['QA - Overall Performance Rating'] != ''].shape[0]
            logger.info(f"✅ Integrated QA data for {populated_count:,} records")
            
            return enhanced_df
            
        except Exception as e:
            logger.error(f"QA data integration failed: {e}")
            return main_df
    
    def get_existing_data(self, spreadsheet_id: str, sheet_name: str) -> Dict[str, int]:
        """Get existing data and return mapping of unique IDs to row numbers"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:C"  # Get first 3 columns to find ID and headers
            ).execute()
            
            values = result.get('values', [])
            if not values:
                return {}
            
            # Find ID column (usually first column)
            headers = values[0] if values else []
            id_col_idx = 0  # Default to first column
            
            # Look for common ID column names
            for i, header in enumerate(headers):
                if 'id' in header.lower() or header.lower() == 'ticket id':
                    id_col_idx = i
                    break
            
            # Build mapping: ID -> row number (1-indexed, accounting for header)
            id_to_row = {}
            for row_idx, row in enumerate(values[1:], start=2):  # Start at row 2 (after header)
                if len(row) > id_col_idx and row[id_col_idx]:
                    id_to_row[str(row[id_col_idx])] = row_idx
                    
            logger.info(f"📊 Found {len(id_to_row)} existing records in {sheet_name}")
            return id_to_row
            
        except Exception as e:
            logger.warning(f"Could not get existing data from {sheet_name}: {str(e)}")
            return {}
    
    def upsert_data(self, spreadsheet_id: str, sheet_name: str, data: List[List]) -> bool:
        """Upsert data to Google Sheet (update existing, insert new)"""
        try:
            if not data or len(data) < 2:
                logger.warning("No data to upsert")
                return False
                
            headers = data[0]
            rows = data[1:]
            
            # Get existing data mapping
            existing_data = self.get_existing_data(spreadsheet_id, sheet_name)
            
            # Find ID column
            id_col_idx = 0
            for i, header in enumerate(headers):
                if 'id' in header.lower() or 'ticket id' in header.lower():
                    id_col_idx = i
                    break
            
            # Separate updates and inserts
            updates = []
            inserts = []
            
            for row in rows:
                if len(row) > id_col_idx and str(row[id_col_idx]) in existing_data:
                    # Update existing record
                    row_num = existing_data[str(row[id_col_idx])]
                    
                    # Convert column number to letter for large ranges
                    def col_num_to_letter(n):
                        result = ""
                        while n > 0:
                            n -= 1
                            result = chr(65 + n % 26) + result
                            n //= 26
                        return result
                    
                    end_col = col_num_to_letter(len(row))
                    updates.append({
                        'range': f"{sheet_name}!A{row_num}:{end_col}{row_num}",
                        'values': [row]
                    })
                else:
                    # Insert new record
                    inserts.append(row)
            
            # Perform updates in batches (Google Sheets API limit is 500 requests per batch)
            if updates:
                batch_size = 500
                for i in range(0, len(updates), batch_size):
                    batch = updates[i:i+batch_size]
                    batch_update_data = {
                        'valueInputOption': 'RAW',
                        'data': batch
                    }

                    self.service.spreadsheets().values().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=batch_update_data
                    ).execute()

                    logger.info(f"📝 Updated batch {i//batch_size + 1}: {len(batch)} records")

                logger.info(f"✅ Total updated: {len(updates)} existing records")
            
            # Perform inserts
            if inserts:
                # Find the last row with data
                try:
                    result = self.service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=f"{sheet_name}!A:A"
                    ).execute()
                    last_row = len(result.get('values', [])) + 1
                except:
                    last_row = len(existing_data) + 2  # Header + existing data + 1
                
                # If this is the first time, write headers first
                if not existing_data:
                    self.service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=f"{sheet_name}!A1",
                        valueInputOption='RAW',
                        body={'values': [headers]}
                    ).execute()
                    last_row = 2
                
                # Insert new records - use column number to letter conversion for large ranges
                def col_num_to_letter(n):
                    """Convert column number to letter (A, B, ..., Z, AA, AB, ...)"""
                    result = ""
                    while n > 0:
                        n -= 1
                        result = chr(65 + n % 26) + result
                        n //= 26
                    return result
                
                end_col = col_num_to_letter(len(headers))

                # Ensure sheet has enough rows before inserting
                rows_needed = last_row + len(inserts)
                self._ensure_sheet_size(spreadsheet_id, sheet_name, rows_needed, len(headers))

                # Insert in batches to avoid hitting API limits (10,000 cells per request)
                batch_size = 1000  # 1000 rows at a time
                total_inserted = 0

                for i in range(0, len(inserts), batch_size):
                    batch = inserts[i:i+batch_size]
                    current_last_row = last_row + i
                    insert_range = f"{sheet_name}!A{current_last_row}:{end_col}{current_last_row+len(batch)-1}"

                    self.service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=insert_range,
                        valueInputOption='RAW',
                        body={'values': batch}
                    ).execute()

                    total_inserted += len(batch)
                    logger.info(f"➕ Inserted batch {i//batch_size + 1}: {len(batch)} records")

                logger.info(f"✅ Total inserted: {total_inserted} new records")
            
            # Clean up old data (beyond 365 days)
            self._cleanup_old_data(spreadsheet_id, sheet_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Upsert failed: {str(e)}")
            return False
    
    def _ensure_sheet_size(self, spreadsheet_id: str, sheet_name: str, rows_needed: int, cols_needed: int):
        """Ensure the sheet has enough rows and columns"""
        try:
            # Get sheet metadata to find sheet ID
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheet_id = None
            current_rows = 0
            current_cols = 0

            for sheet in sheet_metadata.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    current_rows = sheet['properties']['gridProperties'].get('rowCount', 1000)
                    current_cols = sheet['properties']['gridProperties'].get('columnCount', 26)
                    break

            if sheet_id is None:
                logger.warning(f"Sheet '{sheet_name}' not found for resizing")
                return

            # Calculate if we need to expand
            needs_resize = False
            new_rows = current_rows
            new_cols = current_cols

            if rows_needed > current_rows:
                new_rows = max(rows_needed + 1000, current_rows * 2)  # Add buffer
                needs_resize = True

            if cols_needed > current_cols:
                new_cols = max(cols_needed + 10, current_cols * 2)  # Add buffer
                needs_resize = True

            if needs_resize:
                logger.info(f"📏 Expanding sheet '{sheet_name}' from {current_rows}x{current_cols} to {new_rows}x{new_cols}")

                request = {
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            'gridProperties': {
                                'rowCount': new_rows,
                                'columnCount': new_cols
                            }
                        },
                        'fields': 'gridProperties(rowCount,columnCount)'
                    }
                }

                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={'requests': [request]}
                ).execute()

                logger.info(f"✅ Sheet expanded successfully")

        except Exception as e:
            logger.error(f"Failed to resize sheet: {str(e)}")

    def _cleanup_old_data(self, spreadsheet_id: str, sheet_name: str):
        """Remove data older than 365 days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=365)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
            # Get all data to identify old rows
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:Z"
            ).execute()
            
            values = result.get('values', [])
            if len(values) < 2:
                return
                
            headers = values[0]
            
            # Find Create date column
            date_col_idx = None
            for i, header in enumerate(headers):
                if 'create date' in header.lower():
                    date_col_idx = i
                    break
            
            if date_col_idx is None:
                return
            
            # Find rows to delete (older than 365 days)
            rows_to_delete = []
            for row_idx, row in enumerate(values[1:], start=2):
                if len(row) > date_col_idx and row[date_col_idx]:
                    try:
                        row_date = pd.to_datetime(row[date_col_idx])
                        if row_date < cutoff_date:
                            rows_to_delete.append(row_idx)
                    except:
                        continue
            
            # Delete old rows (in reverse order to maintain row numbers)
            if rows_to_delete:
                requests = []
                for row_num in reversed(rows_to_delete):
                    requests.append({
                        'deleteDimension': {
                            'range': {
                                'sheetId': 0,  # Assumes first sheet
                                'dimension': 'ROWS',
                                'startIndex': row_num - 1,  # 0-indexed
                                'endIndex': row_num
                            }
                        }
                    })
                
                # Execute deletions in batches
                for i in range(0, len(requests), 10):
                    batch = requests[i:i+10]
                    self.service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body={'requests': batch}
                    ).execute()
                    time.sleep(0.1)  # Rate limiting
                
                logger.info(f"🗑️ Cleaned up {len(rows_to_delete)} old records from {sheet_name}")
                
        except Exception as e:
            logger.warning(f"Cleanup failed: {str(e)}")
    
    def export_data(self, 
                   ticket_df: Optional[pd.DataFrame] = None,
                   chat_df: Optional[pd.DataFrame] = None,
                   spreadsheet_id: Optional[str] = None,
                   spreadsheet_title: str = "Support Analytics Dashboard") -> Optional[str]:
        """
        Export ticket and chat data to Google Sheets with upsert functionality
        
        Args:
            ticket_df: Processed ticket dataframe
            chat_df: Processed chat dataframe  
            spreadsheet_id: Existing spreadsheet ID (creates new if None)
            spreadsheet_title: Title for new spreadsheet
            
        Returns:
            Spreadsheet ID if successful, None otherwise
        """
        if not self.authenticate():
            return None
        
        try:
            # Create spreadsheet if not provided
            if not spreadsheet_id:
                spreadsheet_id = self.create_spreadsheet(spreadsheet_title)
                if not spreadsheet_id:
                    return None
            
            success_count = 0
            
            # Export tickets
            if ticket_df is not None and not ticket_df.empty:
                logger.info("📋 Exporting ticket data...")
                ticket_data = self.prepare_data_for_sheets(ticket_df, 'tickets')
                if self.upsert_data(spreadsheet_id, 'Tickets', ticket_data):
                    success_count += 1
            
            # Export chats
            if chat_df is not None and not chat_df.empty:
                logger.info("💬 Exporting chat data...")
                chat_data = self.prepare_data_for_sheets(chat_df, 'chats')
                if self.upsert_data(spreadsheet_id, 'Chats', chat_data):
                    success_count += 1
            
            if success_count > 0:
                sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
                logger.info(f"✅ Successfully exported to Google Sheets: {sheet_url}")
                return spreadsheet_id
            else:
                logger.error("No data was successfully exported")
                return None
                
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            return None
    
    def log_sync_run(self, spreadsheet_id: str, run_data: Dict) -> bool:
        """Log sync run to Sync_Log sheet"""
        try:
            # Prepare sync log data
            sync_headers = [
                'Timestamp', 'Run_ID', 'Status', 'Analytics_Type', 'Date_Range',
                'Files_Processed', 'Records_Processed', 'Duration_MS', 'Duration_Readable',
                'Sheets_Updated', 'Spreadsheet_URL', 'Error_Count', 'Warning_Count',
                'Processing_Details', 'Last_Updated'
            ]
            
            # Format duration as readable string
            duration_ms = run_data.get('total_duration_ms', 0)
            if duration_ms:
                if duration_ms < 1000:
                    duration_readable = f"{duration_ms}ms"
                elif duration_ms < 60000:
                    duration_readable = f"{duration_ms/1000:.1f}s"
                else:
                    duration_readable = f"{duration_ms/60000:.1f}m"
            else:
                duration_readable = "N/A"
            
            # Count log entries by level
            log_entries = run_data.get('log_entries', [])
            error_count = sum(1 for entry in log_entries if entry.get('level') == 'ERROR')
            warning_count = sum(1 for entry in log_entries if entry.get('level') == 'WARNING')
            
            # Create processing details summary
            processing_details = []
            for entry in log_entries[-10:]:  # Last 10 entries
                details_entry = f"[{entry.get('stage', 'UNKNOWN')}] {entry.get('message', '')}"
                processing_details.append(details_entry)
            details_text = " | ".join(processing_details)
            
            # Truncate details if too long
            if len(details_text) > 45000:
                details_text = details_text[:45000] + "...[TRUNCATED]"
            
            sync_row = [
                run_data.get('start_time', ''),
                run_data.get('run_id', ''),
                run_data.get('status', 'UNKNOWN'),
                run_data.get('analytics_type', 'tickets'),
                run_data.get('date_range', ''),
                ', '.join(run_data.get('files_processed', [])),
                str(run_data.get('records_processed', 0)),
                str(duration_ms),
                duration_readable,
                str(run_data.get('sheets_updated', False)),
                run_data.get('spreadsheet_url', ''),
                str(error_count),
                str(warning_count),
                details_text,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            # Check if Sync_Log sheet has headers
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range="Sync_Log!A1:O1"
                ).execute()
                
                existing_headers = result.get('values', [])
                if not existing_headers:
                    # Add headers
                    self.service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range="Sync_Log!A1:O1",
                        valueInputOption='RAW',
                        body={'values': [sync_headers]}
                    ).execute()
            except:
                # Sheet might not exist, headers will be added with data
                pass
            
            # Find next empty row
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range="Sync_Log!A:A"
                ).execute()
                last_row = len(result.get('values', [])) + 1
            except:
                last_row = 2  # Start after headers
            
            # Add the sync log entry
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"Sync_Log!A{last_row}:O{last_row}",
                valueInputOption='RAW',
                body={'values': [sync_row]}
            ).execute()
            
            logger.info(f"📝 Logged sync run to Sync_Log sheet (row {last_row})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log sync run: {str(e)}")
            return False
    
    def log_dashboard_metrics(self, spreadsheet_id: str, metrics_data: Dict) -> bool:
        """Log high-level dashboard metrics to Dashboard_Metrics sheet"""
        try:
            # Prepare dashboard metrics headers
            metrics_headers = [
                'Timestamp', 'Run_ID', 'Analytics_Type', 'Date_Range', 'Period_Description',
                # Volume Metrics
                'Total_Records', 'Total_Tickets', 'Total_Chats', 'Weekday_Records', 'Weekend_Records',
                # Response Time Metrics (Tickets)
                'Avg_Response_Time_Hours', 'Median_Response_Time_Hours', 'Min_Response_Time_Hours', 'Max_Response_Time_Hours',
                'Weekend_Avg_Response_Hours', 'Weekday_Avg_Response_Hours',
                # Agent Performance (Tickets)
                'Top_Volume_Agent', 'Top_Volume_Count', 'Fastest_Agent', 'Fastest_Response_Hours',
                'Agent_Count', 'Agents_List',
                # Chat Metrics
                'Total_Bot_Chats', 'Total_Human_Chats', 'Bot_Transfer_Rate', 'Bot_Resolution_Rate',
                'Avg_Chat_Duration_Minutes', 'Bot_Satisfaction_Rate', 'Human_Satisfaction_Rate',
                # Geographic & Time
                'Top_Country', 'Top_Country_Count', 'Peak_Hour', 'Peak_Hour_Count',
                # Quality Metrics
                'Business_Hours_Percentage', 'Response_Under_1Hour_Percentage', 'Response_Under_4Hour_Percentage',
                # Data Quality
                'Records_With_Response_Time', 'Records_Missing_Data', 'Data_Quality_Score',
                'Last_Updated'
            ]
            
            # Build metrics row from data
            metrics_row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Timestamp
                metrics_data.get('run_id', ''),
                metrics_data.get('analytics_type', ''),
                metrics_data.get('date_range', ''),
                metrics_data.get('period_description', ''),
                
                # Volume metrics
                str(metrics_data.get('total_records', 0)),
                str(metrics_data.get('total_tickets', 0)),
                str(metrics_data.get('total_chats', 0)),
                str(metrics_data.get('weekday_records', 0)),
                str(metrics_data.get('weekend_records', 0)),
                
                # Response time metrics
                str(metrics_data.get('avg_response_time_hours', '')),
                str(metrics_data.get('median_response_time_hours', '')),
                str(metrics_data.get('min_response_time_hours', '')),
                str(metrics_data.get('max_response_time_hours', '')),
                str(metrics_data.get('weekend_avg_response_hours', '')),
                str(metrics_data.get('weekday_avg_response_hours', '')),
                
                # Agent performance
                metrics_data.get('top_volume_agent', ''),
                str(metrics_data.get('top_volume_count', 0)),
                metrics_data.get('fastest_agent', ''),
                str(metrics_data.get('fastest_response_hours', '')),
                str(metrics_data.get('agent_count', 0)),
                metrics_data.get('agents_list', ''),
                
                # Chat metrics
                str(metrics_data.get('total_bot_chats', 0)),
                str(metrics_data.get('total_human_chats', 0)),
                str(metrics_data.get('bot_transfer_rate', '')),
                str(metrics_data.get('bot_resolution_rate', '')),
                str(metrics_data.get('avg_chat_duration_minutes', '')),
                str(metrics_data.get('bot_satisfaction_rate', '')),
                str(metrics_data.get('human_satisfaction_rate', '')),
                
                # Geographic & time
                metrics_data.get('top_country', ''),
                str(metrics_data.get('top_country_count', 0)),
                str(metrics_data.get('peak_hour', '')),
                str(metrics_data.get('peak_hour_count', 0)),
                
                # Quality metrics
                str(metrics_data.get('business_hours_percentage', '')),
                str(metrics_data.get('response_under_1hour_percentage', '')),
                str(metrics_data.get('response_under_4hour_percentage', '')),
                
                # Data quality
                str(metrics_data.get('records_with_response_time', 0)),
                str(metrics_data.get('records_missing_data', 0)),
                str(metrics_data.get('data_quality_score', '')),
                
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Last updated
            ]
            
            # Check if Dashboard_Metrics sheet has headers
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range="Dashboard_Metrics!A1:AZ1"
                ).execute()
                
                existing_headers = result.get('values', [])
                if not existing_headers:
                    # Add headers
                    self.service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range="Dashboard_Metrics!A1:AZ1",
                        valueInputOption='RAW',
                        body={'values': [metrics_headers]}
                    ).execute()
            except:
                # Sheet might not exist, headers will be added with data
                pass
            
            # Find next empty row
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range="Dashboard_Metrics!A:A"
                ).execute()
                last_row = len(result.get('values', [])) + 1
            except:
                last_row = 2  # Start after headers
            
            # Add the dashboard metrics entry
            end_col_letter = 'AZ'  # Covers all our columns
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"Dashboard_Metrics!A{last_row}:{end_col_letter}{last_row}",
                valueInputOption='RAW',
                body={'values': [metrics_row]}
            ).execute()
            
            logger.info(f"📊 Logged dashboard metrics to Dashboard_Metrics sheet (row {last_row})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log dashboard metrics: {str(e)}")
            return False

def export_to_google_sheets(results_dir: Path, 
                          spreadsheet_id: Optional[str] = None,
                          credentials_path: str = 'credentials.json') -> Optional[str]:
    """
    Convenience function to export processed data from results directory
    
    Args:
        results_dir: Path to results directory containing processed CSV files
        spreadsheet_id: Existing spreadsheet ID (optional)
        credentials_path: Path to Google credentials file
        
    Returns:
        Spreadsheet ID if successful, None otherwise
    """
    exporter = GoogleSheetsExporter(credentials_path)
    
    # Load processed data
    ticket_df = None
    chat_df = None
    
    ticket_file = results_dir / 'tickets_transformed.csv'
    chat_file = results_dir / 'chats_transformed.csv'
    
    if ticket_file.exists():
        try:
            ticket_df = pd.read_csv(ticket_file, low_memory=False)
            logger.info(f"📋 Loaded {len(ticket_df):,} ticket records")
        except Exception as e:
            logger.warning(f"Could not load ticket data: {e}")
    
    if chat_file.exists():
        try:
            chat_df = pd.read_csv(chat_file, low_memory=False)
            logger.info(f"💬 Loaded {len(chat_df):,} chat records")
        except Exception as e:
            logger.warning(f"Could not load chat data: {e}")
    
    if ticket_df is None and chat_df is None:
        logger.error("No valid data files found for export")
        return None
    
    # Generate spreadsheet title with timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d')
    title = f"Support Analytics Dashboard - {timestamp}"
    
    return exporter.export_data(
        ticket_df=ticket_df,
        chat_df=chat_df, 
        spreadsheet_id=spreadsheet_id,
        spreadsheet_title=title
    )

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python google_sheets_exporter.py <results_directory> [spreadsheet_id]")
        sys.exit(1)
    
    results_path = Path(sys.argv[1])
    spreadsheet_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = export_to_google_sheets(results_path, spreadsheet_id)
    if result:
        print(f"✅ Export successful: https://docs.google.com/spreadsheets/d/{result}")
    else:
        print("❌ Export failed")