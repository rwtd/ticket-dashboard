#!/usr/bin/env python3
"""
Analyze tickets for specific companies over the last 12 months.
Searches by company name, contact email, and email domain.
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import re
import statistics

# Company search criteria
COMPANIES = {
    "DoorDash": {
        "names": ["DoorDash", "Door Dash"],
        "emails": ["mx-acquisition-serpwow-account@doordash.com"],
        "domains": ["@doordash.com"]
    },
    "Agency Analytics": {
        "names": ["Agency Analytics", "AgencyAnalytics"],
        "emails": ["blake.acheson@agencyanalytics.com"],
        "domains": ["@agencyanalytics.com"]
    },
    "Yext": {
        "names": ["Yext"],
        "emails": ["trajectdata-user@yext.com"],
        "domains": ["@yext.com"]
    },
    "SG Elektronik AG": {
        "names": ["SG Elektronik", "SG Elektronik AG"],
        "emails": ["timo.luttermann75@gmail.com"],
        "domains": ["@gmail.com"]  # Less reliable, will need name match too
    },
    "Salesforce": {
        "names": ["Salesforce", "SalesForce"],
        "emails": ["mcae-team-qbert@salesforce.com"],
        "domains": ["@salesforce.com"]
    },
    "DesertCart": {
        "names": ["DesertCart", "Desert Cart"],
        "emails": ["ankit.biyani@desertcart.ae"],
        "domains": ["@desertcart.ae", "@desertcart.com"]
    }
}

def parse_date(date_str):
    """Parse HubSpot date format to datetime."""
    if not date_str or date_str.strip() == "":
        return None
    try:
        # HubSpot format: "2024-09-25 14:30:45 CDT" or "2024-09-25 14:30"
        date_part = date_str.split(" CDT")[0].split(" EDT")[0].strip()
        # Try with seconds first, then without
        try:
            return datetime.strptime(date_part, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.strptime(date_part, "%Y-%m-%d %H:%M")
    except:
        return None

def matches_company(row, company_name, criteria):
    """Check if ticket matches company criteria."""
    # Extract fields
    company_field = row.get("Associated Company (Primary)", "").lower()
    contact_emails = row.get("All associated contact emails", "").lower()

    # Check company name match
    for name in criteria["names"]:
        if name.lower() in company_field:
            return True, f"Company name: {name}"

    # Check specific email match
    for email in criteria["emails"]:
        if email.lower() in contact_emails:
            return True, f"Contact email: {email}"

    # Check domain match (but require company name for gmail)
    for domain in criteria["domains"]:
        if domain.lower() in contact_emails:
            # For generic domains like gmail, also check company name
            if domain == "@gmail.com":
                for name in criteria["names"]:
                    if name.lower() in company_field:
                        return True, f"Domain + name: {domain} + {name}"
            else:
                return True, f"Email domain: {domain}"

    return False, None

def parse_response_time(time_str):
    """Parse response time in HH:mm:ss format to hours."""
    if not time_str or time_str.strip() == "":
        return None
    try:
        # Format: "HH:mm:ss" or "H:mm:ss"
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours + (minutes / 60.0) + (seconds / 3600.0)
    except:
        pass
    return None

def main():
    # Calculate 12 months ago from the export date (25 Sep 2025)
    export_date = datetime(2025, 9, 25)
    twelve_months_ago = export_date - timedelta(days=365)

    # Results storage
    company_tickets = defaultdict(list)
    match_reasons = defaultdict(list)

    # Read CSV
    csv_file = "tickets/ticket-export-25092025.csv"

    print(f"Analyzing tickets from the last 12 months ({twelve_months_ago.strftime('%Y-%m-%d')} onwards)...")
    print("=" * 80)

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        total_processed = 0
        total_in_period = 0

        for row in reader:
            total_processed += 1

            # Parse create date
            create_date = parse_date(row.get("Create date", ""))
            if not create_date or create_date < twelve_months_ago:
                continue

            total_in_period += 1

            # Check against each company
            for company_name, criteria in COMPANIES.items():
                matched, reason = matches_company(row, company_name, criteria)
                if matched:
                    # Parse response time
                    response_time_str = row.get("Time to first agent email reply (HH:mm:ss)", "")
                    response_time_hours = parse_response_time(response_time_str)

                    company_tickets[company_name].append({
                        "ticket_id": row.get("Ticket ID", ""),
                        "ticket_name": row.get("Ticket name", ""),
                        "create_date": create_date,
                        "company": row.get("Associated Company (Primary)", ""),
                        "emails": row.get("All associated contact emails", ""),
                        "reason": reason,
                        "response_time_hours": response_time_hours,
                        "response_time_str": response_time_str
                    })
                    match_reasons[company_name].append(reason)

    # Print results
    print(f"\nTotal tickets processed: {total_processed:,}")
    print(f"Tickets in last 12 months: {total_in_period:,}")
    print("=" * 80)
    print("\n📊 COMPANY TICKET COUNTS (Last 12 Months)\n")

    # Sort by ticket count
    sorted_companies = sorted(COMPANIES.keys(),
                             key=lambda x: len(company_tickets[x]),
                             reverse=True)

    for company_name in sorted_companies:
        tickets = company_tickets[company_name]
        count = len(tickets)

        print(f"\n{company_name}")
        print(f"  Total Tickets: {count}")

        if count > 0:
            # Show date range
            dates = [t["create_date"] for t in tickets]
            oldest = min(dates)
            newest = max(dates)
            print(f"  Date Range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")

            # Calculate response time statistics
            response_times = [t["response_time_hours"] for t in tickets if t["response_time_hours"] is not None]
            if response_times:
                median_response = statistics.median(response_times)
                avg_response = statistics.mean(response_times)
                print(f"  Response Times:")
                print(f"    - Median: {median_response:.2f} hours")
                print(f"    - Average: {avg_response:.2f} hours")
                print(f"    - Tickets with response time: {len(response_times)}/{count}")
            else:
                print(f"  Response Times: No data available")

            # Show match breakdown
            reason_counts = defaultdict(int)
            for reason in match_reasons[company_name]:
                reason_counts[reason] += 1

            print(f"  Match Types:")
            for reason, reason_count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"    - {reason}: {reason_count} tickets")

            # Show sample tickets (first 3)
            print(f"  Sample Tickets:")
            for ticket in tickets[:3]:
                print(f"    - #{ticket['ticket_id']}: {ticket['ticket_name'][:60]}...")
                print(f"      Company: {ticket['company']}")
                print(f"      Emails: {ticket['emails'][:80]}...")

    # Export detailed results
    output_file = "company_tickets_analysis.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['company', 'ticket_id', 'ticket_name', 'create_date',
                     'associated_company', 'contact_emails', 'match_reason',
                     'response_time_hours', 'response_time_hms']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for company_name in sorted_companies:
            for ticket in company_tickets[company_name]:
                writer.writerow({
                    'company': company_name,
                    'ticket_id': ticket['ticket_id'],
                    'ticket_name': ticket['ticket_name'],
                    'create_date': ticket['create_date'].strftime('%Y-%m-%d %H:%M:%S'),
                    'associated_company': ticket['company'],
                    'contact_emails': ticket['emails'],
                    'match_reason': ticket['reason'],
                    'response_time_hours': ticket['response_time_hours'] if ticket['response_time_hours'] else '',
                    'response_time_hms': ticket['response_time_str']
                })

    print(f"\n\n✅ Detailed results exported to: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
