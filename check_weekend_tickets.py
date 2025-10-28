#!/usr/bin/env python3
"""
Quick diagnostic script to check weekend tickets on Oct 18-19, 2025
"""
import pandas as pd
import pytz
from datetime import datetime
from firestore_db import FirestoreDatabase

# Date range for Oct 13-20, 2025
eastern = pytz.timezone('US/Eastern')
start_date = eastern.localize(datetime(2025, 10, 13, 0, 0, 0))
end_date = eastern.localize(datetime(2025, 10, 20, 23, 59, 59))

print(f"📅 Checking tickets from {start_date} to {end_date}")
print("=" * 80)

# Get data from Firestore
db = FirestoreDatabase()
tickets_df = db.get_tickets(start_date=start_date, end_date=end_date)

if tickets_df is None or len(tickets_df) == 0:
    print("❌ No tickets found in Firestore for this date range")
    exit(1)

print(f"✅ Retrieved {len(tickets_df)} tickets from Firestore")

# Convert Create date to datetime if needed
tickets_df['Create date'] = pd.to_datetime(tickets_df['Create date'], errors='coerce')

# Add Weekend_Ticket flag if missing
if 'Weekend_Ticket' not in tickets_df.columns:
    def _is_weekend(dt):
        """Check if timestamp falls within weekend period: Friday 6PM EDT - Monday 5AM EDT"""
        if pd.isna(dt):
            return False
        # Convert to EDT timezone
        dt_edt = dt.astimezone(eastern) if dt.tzinfo else eastern.localize(dt)
        weekday = dt_edt.weekday()  # Monday=0, Sunday=6
        current_time = dt_edt.time()
        
        # Friday after 6PM
        if weekday == 4 and current_time >= pd.Timestamp('18:00').time():
            return True
        # Saturday and Sunday (all day)
        if weekday in [5, 6]:
            return True
        # Monday before 5AM
        if weekday == 0 and current_time < pd.Timestamp('05:00').time():
            return True
        return False
    
    tickets_df['Weekend_Ticket'] = tickets_df['Create date'].apply(_is_weekend)
    print(f"✅ Added Weekend_Ticket flag")

# Filter to only Oct 18-19
tickets_df['Date'] = tickets_df['Create date'].dt.date
oct_18_19 = tickets_df[tickets_df['Date'].isin([datetime(2025, 10, 18).date(), datetime(2025, 10, 19).date()])]

print("\n" + "=" * 80)
print("📊 RESULTS FOR OCTOBER 18-19, 2025")
print("=" * 80)

if len(oct_18_19) == 0:
    print("⚠️  No tickets found for Oct 18-19")
else:
    print(f"\nTotal tickets on Oct 18-19: {len(oct_18_19)}")
    
    # Group by date
    date_breakdown = oct_18_19.groupby('Date').agg({
        'Weekend_Ticket': ['count', 'sum']
    })
    date_breakdown.columns = ['Total', 'Weekend']
    date_breakdown['Weekday'] = date_breakdown['Total'] - date_breakdown['Weekend']
    
    print("\nBreakdown by date:")
    print(date_breakdown)
    
    # Overall summary
    total_weekend = oct_18_19['Weekend_Ticket'].sum()
    total_weekday = len(oct_18_19) - total_weekend
    
    print(f"\n📈 SUMMARY:")
    print(f"  Weekend tickets: {total_weekend}")
    print(f"  Weekday tickets: {total_weekday}")
    print(f"  Total: {len(oct_18_19)}")
    
    # Show some sample tickets
    print(f"\n📋 Sample weekend tickets:")
    weekend_samples = oct_18_19[oct_18_19['Weekend_Ticket'] == True].head(5)
    for idx, row in weekend_samples.iterrows():
        dt_str = row['Create date'].strftime('%Y-%m-%d %H:%M:%S %Z') if pd.notna(row['Create date']) else 'N/A'
        ticket_id = row.get('Ticket ID', 'N/A')
        print(f"  - Ticket {ticket_id}: {dt_str}")

# Also check overall for the week
print("\n" + "=" * 80)
print("📊 FULL WEEK BREAKDOWN (Oct 13-20)")
print("=" * 80)

# Filter to support team only
support_agents = ['Bhushan', 'Girly', 'Nova', 'Francis']
owner_col = 'Case Owner' if 'Case Owner' in tickets_df.columns else 'Ticket owner'
if owner_col in tickets_df.columns:
    support_tickets = tickets_df[tickets_df[owner_col].isin(support_agents)]
else:
    support_tickets = tickets_df

print(f"\nSupport team tickets: {len(support_tickets)}")
print(f"  Weekend: {support_tickets['Weekend_Ticket'].sum()}")
print(f"  Weekday: {len(support_tickets) - support_tickets['Weekend_Ticket'].sum()}")

print("\n✅ Done!")