#!/usr/bin/env python3
"""
Test script to sync a small batch of tickets with first_agent_reply_date to Google Sheets
"""
from dotenv import load_dotenv
import os
import pandas as pd
from datetime import datetime, timedelta
import pytz

load_dotenv()

from hubspot_fetcher import HubSpotTicketFetcher
from google_sheets_exporter import GoogleSheetsExporter

# Fetch just 50 recent tickets
api_key = os.environ.get('HUBSPOT_API_KEY')
fetcher = HubSpotTicketFetcher(api_key)

from_date = datetime.now(pytz.UTC) - timedelta(days=30)
df_raw = fetcher.fetch_tickets(since_date=from_date, max_tickets=50)

print(f"✅ Fetched {len(df_raw)} tickets")
print(f"Columns: {list(df_raw.columns)}")

# Apply column mapping
column_mapping = {
    'subject': 'Subject',
    'hs_pipeline': 'Pipeline',
    'hs_pipeline_stage': 'Pipeline Stage',
    'createdate': 'Create date',
    'hs_lastmodifieddate': 'Last Modified Date',
    'closed_date': 'Close date',
    'hubspot_owner_id': 'Case Owner',
    'first_agent_reply_date': 'First agent email response date',
    'hs_ticket_priority': 'Priority',
    'content': 'Description',
    'ticket_id': 'Ticket ID'
}

df_processed = df_raw.copy()
df_processed.rename(columns=column_mapping, inplace=True)

# Check the new column
if 'First agent email response date' in df_processed.columns:
    non_null = df_processed['First agent email response date'].notna().sum()
    print(f"\n✅ 'First agent email response date' column exists")
    print(f"   Non-null values: {non_null} out of {len(df_processed)}")

    # Show sample
    if non_null > 0:
        print("\n   Sample records with response date:")
        sample = df_processed[df_processed['First agent email response date'].notna()][
            ['Ticket ID', 'Create date', 'First agent email response date']
        ].head(3)
        print(sample.to_string(index=False))

# Now try to upload to a TEST sheet tab
print("\n📤 Testing Google Sheets upload...")
spreadsheet_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
exporter = GoogleSheetsExporter(spreadsheet_id=spreadsheet_id)

# Save to CSV first
test_file = '/tmp/test_tickets_with_response_date.csv'
df_processed.to_csv(test_file, index=False)
print(f"💾 Saved test data to {test_file}")

print("\nTo upload to Google Sheets, use:")
print(f"  python -c \"from google_sheets_exporter import GoogleSheetsExporter; ")
print(f"  exporter = GoogleSheetsExporter('{spreadsheet_id}'); ")
print(f"  exporter.upload_tickets_from_csv('{test_file}')\"")
