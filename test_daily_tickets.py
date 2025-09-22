#!/usr/bin/env python3
"""
Test script to demonstrate daily ticket analytics issue and solution
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def check_ticket_data():
    """Check what dates have ticket data available"""
    print("=== DAILY TICKET ANALYTICS - DATA AVAILABILITY CHECK ===\n")

    # Load ticket data
    ticket_files = list(Path('tickets').glob('*.csv'))
    if not ticket_files:
        print("❌ No ticket files found in ./tickets/ directory")
        return

    print(f"📋 Loading ticket data from: {ticket_files[0].name}")
    df = pd.read_csv(ticket_files[0], low_memory=False)

    # Convert date column
    df['Create date'] = pd.to_datetime(df['Create date'])

    print(f"✅ Loaded {len(df)} total tickets")
    print(f"📅 Data Range: {df['Create date'].min().strftime('%Y-%m-%d')} to {df['Create date'].max().strftime('%Y-%m-%d')}")
    print()

    # Check recent dates
    print("🔍 RECENT DATES ANALYSIS:")
    recent_dates = ['2025-09-15', '2025-09-16', '2025-09-17', '2025-09-18']

    for date_str in recent_dates:
        date_obj = pd.to_datetime(date_str).date()
        tickets_on_date = df[df['Create date'].dt.date == date_obj]
        count = len(tickets_on_date)

        if count > 0:
            status = "✅ HAS DATA"
            sample_times = tickets_on_date['Create date'].head(3).dt.strftime('%H:%M').tolist()
            print(f"  {date_str}: {count:2d} tickets {status} (sample times: {', '.join(sample_times)})")
        else:
            status = "❌ NO DATA"
            print(f"  {date_str}: {count:2d} tickets {status}")

    print()

    # Find busiest days
    print("📊 TOP 5 BUSIEST DAYS:")
    daily_counts = df.groupby(df['Create date'].dt.date).size().sort_values(ascending=False)
    for i, (date, count) in enumerate(daily_counts.head(5).items(), 1):
        print(f"  {i}. {date}: {count} tickets")

    print()

    # Recommendations
    print("💡 RECOMMENDATIONS:")
    print("   ✅ For testing daily charts, use these dates with data:")
    working_dates = daily_counts[daily_counts > 10].head(3)
    for date, count in working_dates.items():
        print(f"      • {date.strftime('%d%m%Y')} ({date}) - {count} tickets")

    print()
    print("   ❌ September 18, 2025 will fail because:")
    print("      • No tickets exist on that date")
    print("      • Data only goes up to September 17, 2025")

    print()
    print("🚀 COMMAND LINE EXAMPLES:")
    print("   # These will work:")
    for date, count in working_dates.items():
        date_str = date.strftime('%d%m%Y')
        print(f"   python ticket_analytics.py --day {date_str}  # {count} tickets")

    print()
    print("   # This will fail (no data):")
    print("   python ticket_analytics.py --day 18092025  # 0 tickets")

if __name__ == "__main__":
    check_ticket_data()