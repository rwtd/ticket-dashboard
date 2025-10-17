#!/usr/bin/env python3
"""
Firestore to Google Sheets Export
Syncs Firestore data to Google Sheets for external stakeholder viewing
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from firestore_db import get_database


class FirestoreToSheetsExporter:
    """Export Firestore data to Google Sheets with upsert logic"""
    
    def __init__(self, spreadsheet_id: str, credentials_path: str = 'service_account_credentials.json'):
        """
        Initialize exporter
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            credentials_path: Path to service account credentials JSON
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.service = None
        self.db = None
        
    def authenticate(self) -> bool:
        """Authenticate with Google Sheets API"""
        try:
            if not Path(self.credentials_path).exists():
                print(f"❌ Credentials file not found: {self.credentials_path}")
                return False
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            self.service = build('sheets', 'v4', credentials=credentials)
            print(f"✅ Authenticated with Google Sheets API")
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def connect_firestore(self) -> bool:
        """Connect to Firestore database"""
        try:
            self.db = get_database()
            print(f"✅ Connected to Firestore")
            return True
        except Exception as e:
            print(f"❌ Firestore connection failed: {e}")
            return False
    
    def prepare_dataframe_for_sheets(self, df: pd.DataFrame) -> list:
        """
        Convert DataFrame to list of lists for Sheets API
        Handles datetime conversion and None values
        """
        if df is None or df.empty:
            return []
        
        # Convert datetime columns to strings
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Replace NaN/None with empty string
        df = df.fillna('')
        
        # Convert to list of lists (header + data)
        values = [df.columns.tolist()] + df.values.tolist()
        return values
    
    def clear_sheet(self, sheet_name: str):
        """Clear all data from a sheet"""
        try:
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:ZZ"
            ).execute()
            print(f"  ✓ Cleared sheet: {sheet_name}")
        except HttpError as e:
            if e.resp.status == 400:
                # Sheet doesn't exist, create it
                self.create_sheet(sheet_name)
            else:
                raise
    
    def create_sheet(self, sheet_name: str):
        """Create a new sheet in the spreadsheet"""
        try:
            request_body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=request_body
            ).execute()
            print(f"  ✓ Created sheet: {sheet_name}")
        except HttpError as e:
            if 'already exists' not in str(e):
                raise
    
    def write_to_sheet(self, sheet_name: str, values: list):
        """Write data to a sheet"""
        if not values:
            print(f"  ⚠️  No data to write to {sheet_name}")
            return
        
        try:
            body = {
                'values': values
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                body=body
            ).execute()
            
            rows_updated = result.get('updatedRows', 0)
            print(f"  ✓ Wrote {rows_updated} rows to {sheet_name}")
            
        except Exception as e:
            print(f"  ❌ Failed to write to {sheet_name}: {e}")
            raise
    
    def format_sheet_headers(self, sheet_name: str):
        """Format the header row (bold, frozen)"""
        try:
            # Get sheet ID
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_id = None
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break
            
            if sheet_id is None:
                return
            
            requests = [
                # Bold header row
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {
                                    'bold': True
                                }
                            }
                        },
                        'fields': 'userEnteredFormat.textFormat.bold'
                    }
                },
                # Freeze header row
                {
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            'gridProperties': {
                                'frozenRowCount': 1
                            }
                        },
                        'fields': 'gridProperties.frozenRowCount'
                    }
                }
            ]
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            print(f"  ✓ Formatted headers for {sheet_name}")
            
        except Exception as e:
            print(f"  ⚠️  Header formatting failed: {e}")
    
    def add_metadata_sheet(self, tickets_count: int, chats_count: int):
        """Add a metadata sheet with sync information"""
        metadata = [
            ['Firestore to Google Sheets Export'],
            [''],
            ['Last Updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Tickets Count', tickets_count],
            ['Chats Count', chats_count],
            [''],
            ['Data Source', 'Firestore Database'],
            ['Export Type', 'Full Mirror (Upsert)'],
            ['Update Frequency', 'Daily'],
            [''],
            ['Notes', 'This spreadsheet mirrors the Firestore database'],
            ['', 'Data is automatically synced daily'],
            ['', 'Do not edit - changes will be overwritten']
        ]
        
        try:
            # Clear and write metadata
            self.clear_sheet('Metadata')
            self.write_to_sheet('Metadata', metadata)
            
            # Format metadata sheet
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_id = None
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == 'Metadata':
                    sheet_id = sheet['properties']['sheetId']
                    break
            
            if sheet_id:
                requests = [
                    # Bold first row
                    {
                        'repeatCell': {
                            'range': {
                                'sheetId': sheet_id,
                                'startRowIndex': 0,
                                'endRowIndex': 1
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'textFormat': {
                                        'bold': True,
                                        'fontSize': 14
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat.textFormat'
                        }
                    }
                ]
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': requests}
                ).execute()
            
            print(f"  ✓ Added metadata sheet")
            
        except Exception as e:
            print(f"  ⚠️  Metadata sheet creation failed: {e}")
    
    def export_tickets(self) -> int:
        """Export tickets from Firestore to Sheets"""
        print("\n📋 Exporting Tickets...")
        
        try:
            # Get tickets from Firestore
            tickets_df = self.db.get_tickets()
            
            if tickets_df is None or tickets_df.empty:
                print("  ⚠️  No tickets found in Firestore")
                return 0
            
            print(f"  ✓ Retrieved {len(tickets_df)} tickets from Firestore")
            
            # Prepare data for Sheets
            values = self.prepare_dataframe_for_sheets(tickets_df)
            
            # Clear and write to Sheets
            self.clear_sheet('Tickets')
            self.write_to_sheet('Tickets', values)
            self.format_sheet_headers('Tickets')
            
            return len(tickets_df)
            
        except Exception as e:
            print(f"  ❌ Ticket export failed: {e}")
            raise
    
    def export_chats(self) -> int:
        """Export chats from Firestore to Sheets"""
        print("\n💬 Exporting Chats...")
        
        try:
            # Get chats from Firestore
            chats_df = self.db.get_chats()
            
            if chats_df is None or chats_df.empty:
                print("  ⚠️  No chats found in Firestore")
                return 0
            
            print(f"  ✓ Retrieved {len(chats_df)} chats from Firestore")
            
            # Prepare data for Sheets
            values = self.prepare_dataframe_for_sheets(chats_df)
            
            # Clear and write to Sheets
            self.clear_sheet('Chats')
            self.write_to_sheet('Chats', values)
            self.format_sheet_headers('Chats')
            
            return len(chats_df)
            
        except Exception as e:
            print(f"  ❌ Chat export failed: {e}")
            raise
    
    def run_export(self) -> dict:
        """
        Run full export process
        
        Returns:
            dict: Export results with counts and status
        """
        print("=" * 60)
        print("🔄 Starting Firestore → Google Sheets Export")
        print("=" * 60)
        
        # Authenticate
        if not self.authenticate():
            return {'success': False, 'error': 'Authentication failed'}
        
        # Connect to Firestore
        if not self.connect_firestore():
            return {'success': False, 'error': 'Firestore connection failed'}
        
        try:
            # Export tickets
            tickets_count = self.export_tickets()
            
            # Export chats
            chats_count = self.export_chats()
            
            # Add metadata
            print("\n📊 Adding Metadata...")
            self.add_metadata_sheet(tickets_count, chats_count)
            
            # Success summary
            print("\n" + "=" * 60)
            print("✅ Export Complete!")
            print("=" * 60)
            print(f"📋 Tickets exported: {tickets_count:,}")
            print(f"💬 Chats exported: {chats_count:,}")
            print(f"📊 Spreadsheet: https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}")
            print("=" * 60)
            
            return {
                'success': True,
                'tickets_count': tickets_count,
                'chats_count': chats_count,
                'spreadsheet_id': self.spreadsheet_id,
                'spreadsheet_url': f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}",
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"\n❌ Export failed: {e}")
            return {'success': False, 'error': str(e)}


def main():
    """Main entry point"""
    # Configuration
    SPREADSHEET_ID = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID', '1KVAQLE2vL3z2CpRH_CIqA26ABhr0Oeuu2b7GUrTTjBY')
    CREDENTIALS_PATH = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')
    
    # Create exporter
    exporter = FirestoreToSheetsExporter(
        spreadsheet_id=SPREADSHEET_ID,
        credentials_path=CREDENTIALS_PATH
    )
    
    # Run export
    result = exporter.run_export()
    
    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()