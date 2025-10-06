#!/usr/bin/env python3
"""
Diagnose Google Sheets Data
Compares data in Google Sheets vs local CSV files to identify discrepancies
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    """Compare Google Sheets data with local CSV files"""
    
    print("=" * 70)
    print("🔍 GOOGLE SHEETS DATA DIAGNOSTIC")
    print("=" * 70)
    
    # Check environment variables
    sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
    creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')
    
    if not sheets_id:
        print("\n❌ GOOGLE_SHEETS_SPREADSHEET_ID not set!")
        print("Run: export GOOGLE_SHEETS_SPREADSHEET_ID='your_sheet_id'")
        return False
    
    if not Path(creds_path).exists():
        print(f"\n❌ Credentials file not found: {creds_path}")
        return False
    
    print(f"\n✅ Configuration:")
    print(f"   Spreadsheet ID: {sheets_id}")
    print(f"   Credentials: {creds_path}")
    
    # Connect to Google Sheets
    try:
        from google_sheets_data_source import GoogleSheetsDataSource
        
        print("\n📊 Connecting to Google Sheets...")
        sheets_source = GoogleSheetsDataSource(creds_path, sheets_id)
        
        if not sheets_source.authenticate():
            print("❌ Authentication failed!")
            return False
        
        print("✅ Connected successfully!")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    # Get data from Google Sheets
    print("\n" + "=" * 70)
    print("📥 FETCHING DATA FROM GOOGLE SHEETS")
    print("=" * 70)
    
    sheets_tickets = sheets_source.get_tickets()
    sheets_chats = sheets_source.get_chats()
    
    print(f"\n🎫 Tickets in Google Sheets: {len(sheets_tickets) if sheets_tickets is not None else 0:,}")
    if sheets_tickets is not None and not sheets_tickets.empty:
        min_date = sheets_tickets['Create date'].min()
        max_date = sheets_tickets['Create date'].max()
        print(f"   Date range: {min_date} to {max_date}")
        print(f"   Columns: {len(sheets_tickets.columns)}")
        
        # Show pipeline breakdown
        if 'Pipeline' in sheets_tickets.columns:
            pipeline_counts = sheets_tickets['Pipeline'].value_counts()
            print(f"\n   Pipeline breakdown:")
            for pipeline, count in pipeline_counts.items():
                print(f"      • {pipeline}: {count:,}")
    else:
        print("   ⚠️ No ticket data found!")
    
    print(f"\n💬 Chats in Google Sheets: {len(sheets_chats) if sheets_chats is not None else 0:,}")
    if sheets_chats is not None and not sheets_chats.empty:
        min_date = sheets_chats['chat_creation_date_adt'].min()
        max_date = sheets_chats['chat_creation_date_adt'].max()
        print(f"   Date range: {min_date} to {max_date}")
        print(f"   Columns: {len(sheets_chats.columns)}")
    else:
        print("   ⚠️ No chat data found!")
    
    # Compare with local CSV files
    print("\n" + "=" * 70)
    print("📁 COMPARING WITH LOCAL CSV FILES")
    print("=" * 70)
    
    tickets_dir = Path('tickets')
    chats_dir = Path('chats')
    
    # Count local ticket files
    local_tickets_count = 0
    if tickets_dir.exists():
        csv_files = list(tickets_dir.glob('*.csv'))
        print(f"\n📋 Local ticket files: {len(csv_files)}")
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, low_memory=False)
                local_tickets_count += len(df)
                print(f"   • {csv_file.name}: {len(df):,} records")
            except Exception as e:
                print(f"   • {csv_file.name}: Error reading - {e}")
        
        print(f"\n   Total local tickets: {local_tickets_count:,}")
    else:
        print("\n📋 No local tickets directory found")
    
    # Count local chat files
    local_chats_count = 0
    if chats_dir.exists():
        csv_files = list(chats_dir.glob('*.csv'))
        print(f"\n💬 Local chat files: {len(csv_files)}")
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file, low_memory=False)
                local_chats_count += len(df)
                print(f"   • {csv_file.name}: {len(df):,} records")
            except Exception as e:
                print(f"   • {csv_file.name}: Error reading - {e}")
        
        print(f"\n   Total local chats: {local_chats_count:,}")
    else:
        print("\n💬 No local chats directory found")
    
    # Summary comparison
    print("\n" + "=" * 70)
    print("📊 SUMMARY COMPARISON")
    print("=" * 70)
    
    sheets_ticket_count = len(sheets_tickets) if sheets_tickets is not None else 0
    sheets_chat_count = len(sheets_chats) if sheets_chats is not None else 0
    
    print(f"\n🎫 Tickets:")
    print(f"   Google Sheets: {sheets_ticket_count:,}")
    print(f"   Local CSV files: {local_tickets_count:,}")
    if local_tickets_count > 0:
        diff_pct = ((sheets_ticket_count - local_tickets_count) / local_tickets_count) * 100
        print(f"   Difference: {sheets_ticket_count - local_tickets_count:,} ({diff_pct:+.1f}%)")
    
    print(f"\n💬 Chats:")
    print(f"   Google Sheets: {sheets_chat_count:,}")
    print(f"   Local CSV files: {local_chats_count:,}")
    if local_chats_count > 0:
        diff_pct = ((sheets_chat_count - local_chats_count) / local_chats_count) * 100
        print(f"   Difference: {sheets_chat_count - local_chats_count:,} ({diff_pct:+.1f}%)")
    
    # Recommendations
    print("\n" + "=" * 70)
    print("💡 RECOMMENDATIONS")
    print("=" * 70)
    
    if sheets_ticket_count == 0 and local_tickets_count > 0:
        print("\n⚠️ Google Sheets has NO ticket data but local CSV files exist!")
        print("   Action: Run a full sync to populate Google Sheets")
        print("   Command: python data_sync_service.py --full")
        print("   Or use Admin Panel: http://localhost:5000/admin → Full Sync")
    
    elif sheets_ticket_count < local_tickets_count * 0.5:
        print("\n⚠️ Google Sheets has significantly less data than local CSV files!")
        print("   Possible reasons:")
        print("   1. Only an incremental sync has been run (fetches new data only)")
        print("   2. Rolling window is active (only keeps last 365 days)")
        print("   3. API sync hasn't fetched all historical data yet")
        print("\n   Action: Run a full sync to fetch all historical data")
        print("   Command: python data_sync_service.py --full")
    
    elif sheets_ticket_count > 0:
        print("\n✅ Google Sheets data looks good!")
        print("   Google Sheets is populated and ready to use")
        if sheets_ticket_count < local_tickets_count:
            print(f"   Note: Sheets has {local_tickets_count - sheets_ticket_count:,} fewer records")
            print("   This is normal if using rolling 365-day window")
    
    print("\n" + "=" * 70)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)