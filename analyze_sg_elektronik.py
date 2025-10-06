#!/usr/bin/env python3
"""
Detailed analysis of SG Elektronik AG tickets.
"""

import csv
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

def parse_date(date_str):
    """Parse HubSpot date format to datetime."""
    if not date_str or date_str.strip() == "":
        return None
    try:
        date_part = date_str.split(" CDT")[0].split(" EDT")[0].strip()
        try:
            return datetime.strptime(date_part, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.strptime(date_part, "%Y-%m-%d %H:%M")
    except:
        return None

def parse_response_time(time_str):
    """Parse response time in HH:mm:ss format to hours."""
    if not time_str or time_str.strip() == "":
        return None
    try:
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
    # Search criteria for SG Elektronik / True Speakers
    search_terms = [
        "sg elektronik",
        "sg-elektronik",
        "true speakers",
        "timo.luttermann75@gmail.com",
        "timo.luttermann1996@gmail.com",
        "yannick.klinke1994@gmail.com"
    ]

    csv_file = "tickets/ticket-export-25092025.csv"
    export_date = datetime(2025, 9, 25)
    twelve_months_ago = export_date - timedelta(days=365)

    tickets = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Check if matches any search term
            company = row.get("Associated Company (Primary)", "").lower()
            emails = row.get("All associated contact emails", "").lower()
            ticket_name = row.get("Ticket name", "").lower()

            match = False
            match_reason = ""

            for term in search_terms:
                if term in company:
                    match = True
                    match_reason = f"Company: {term}"
                    break
                if term in emails:
                    match = True
                    match_reason = f"Email: {term}"
                    break

            if match:
                create_date = parse_date(row.get("Create date", ""))
                response_time_str = row.get("Time to first agent email reply (HH:mm:ss)", "")
                response_time_hours = parse_response_time(response_time_str)

                tickets.append({
                    "ticket_id": row.get("Ticket ID", ""),
                    "ticket_name": row.get("Ticket name", ""),
                    "create_date": create_date,
                    "close_date": parse_date(row.get("Close date", "")),
                    "company": row.get("Associated Company (Primary)", ""),
                    "emails": row.get("All associated contact emails", ""),
                    "owner": row.get("Ticket owner", ""),
                    "status": row.get("Ticket status", ""),
                    "category": row.get("Category", ""),
                    "subcategory": row.get("Subcategory", ""),
                    "pipeline": row.get("Pipeline", ""),
                    "description": row.get("Ticket description", ""),
                    "response_time_hours": response_time_hours,
                    "response_time_str": response_time_str,
                    "match_reason": match_reason,
                    "in_12_months": create_date and create_date >= twelve_months_ago
                })

    # Sort by date
    tickets.sort(key=lambda x: x["create_date"] if x["create_date"] else datetime.min, reverse=True)

    # Filter for last 12 months
    recent_tickets = [t for t in tickets if t["in_12_months"]]

    print("=" * 100)
    print("📊 SG ELEKTRONIK AG - DETAILED TICKET ANALYSIS")
    print("=" * 100)

    print(f"\nTotal tickets found: {len(tickets)}")
    print(f"Tickets in last 12 months: {len(recent_tickets)}")

    if not recent_tickets:
        print("\n⚠️  No tickets found in the last 12 months")
        print("\nAll historical tickets:")
        for ticket in tickets[:10]:
            if ticket["create_date"]:
                print(f"\n  {ticket['create_date'].strftime('%Y-%m-%d')} - {ticket['ticket_name']}")
        return

    # Date range
    dates = [t["create_date"] for t in recent_tickets if t["create_date"]]
    if dates:
        print(f"\nDate Range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}")

    # Response times
    response_times = [t["response_time_hours"] for t in recent_tickets if t["response_time_hours"] is not None]
    if response_times:
        print(f"\n⏱️  Response Times:")
        print(f"  Median: {statistics.median(response_times):.2f} hours")
        print(f"  Average: {statistics.mean(response_times):.2f} hours")
        print(f"  Coverage: {len(response_times)}/{len(recent_tickets)} tickets")

    # Category breakdown
    categories = defaultdict(int)
    for ticket in recent_tickets:
        cat = ticket["category"] or "No category"
        categories[cat] += 1

    if categories:
        print(f"\n📋 Ticket Categories:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cat}: {count}")

    # Subcategory breakdown
    subcategories = defaultdict(int)
    for ticket in recent_tickets:
        subcat = ticket["subcategory"] or "No subcategory"
        if subcat != "No subcategory":
            subcategories[subcat] += 1

    if subcategories:
        print(f"\n🏷️  Ticket Subcategories:")
        for subcat, count in sorted(subcategories.items(), key=lambda x: x[1], reverse=True):
            print(f"  {subcat}: {count}")

    # Owner breakdown
    owners = defaultdict(int)
    for ticket in recent_tickets:
        owner = ticket["owner"] or "Unassigned"
        owners[owner] += 1

    if owners:
        print(f"\n👤 Ticket Owners:")
        for owner, count in sorted(owners.items(), key=lambda x: x[1], reverse=True):
            print(f"  {owner}: {count}")

    # Analyze ticket "flavor" - what are they asking about?
    print(f"\n📝 TICKET THEMES & PATTERNS:")
    print("=" * 100)

    parsing_errors = 0
    bot_inquiries = 0
    aws_sdk = 0
    success_manager = 0
    updates = 0

    for ticket in recent_tickets:
        name = ticket["ticket_name"].lower()
        desc = (ticket["description"] or "").lower()

        if "parsing error" in name or "parsing error" in desc:
            parsing_errors += 1
        if "bot chat" in name or "inquiry from bot" in name:
            bot_inquiries += 1
        if "aws sdk" in name or "aws sdk" in desc:
            aws_sdk += 1
        if "success manager" in name or "success manager" in desc:
            success_manager += 1
        if "updates from" in name:
            updates += 1

    print(f"  Parsing Errors: {parsing_errors} tickets")
    print(f"  Bot Chat Inquiries: {bot_inquiries} tickets")
    print(f"  AWS SDK Updates: {aws_sdk} tickets")
    print(f"  Success Manager Outreach: {success_manager} tickets")
    print(f"  General Updates: {updates} tickets")

    # Detailed ticket list
    print(f"\n📋 DETAILED TICKET LIST (Last 12 Months):")
    print("=" * 100)

    for i, ticket in enumerate(recent_tickets, 1):
        print(f"\n{i}. {ticket['ticket_name']}")
        if ticket["create_date"]:
            print(f"   Created: {ticket['create_date'].strftime('%Y-%m-%d')}")
        if ticket["close_date"]:
            print(f"   Closed: {ticket['close_date'].strftime('%Y-%m-%d')}")
        print(f"   Owner: {ticket['owner']}")
        print(f"   Status: {ticket['status']}")
        if ticket["category"]:
            print(f"   Category: {ticket['category']}")
        if ticket["subcategory"]:
            print(f"   Subcategory: {ticket['subcategory']}")
        if ticket["response_time_str"]:
            print(f"   Response Time: {ticket['response_time_str']}")
        if ticket["description"]:
            desc_preview = ticket["description"][:200].replace('\n', ' ')
            print(f"   Preview: {desc_preview}...")

    # Export to CSV
    output_file = "sg_elektronik_tickets.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ticket_id', 'ticket_name', 'create_date', 'close_date', 'owner',
                     'status', 'category', 'subcategory', 'pipeline', 'response_time_hours',
                     'response_time_hms', 'company', 'emails', 'description']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ticket in recent_tickets:
            writer.writerow({
                'ticket_id': ticket['ticket_id'],
                'ticket_name': ticket['ticket_name'],
                'create_date': ticket['create_date'].strftime('%Y-%m-%d %H:%M:%S') if ticket['create_date'] else '',
                'close_date': ticket['close_date'].strftime('%Y-%m-%d %H:%M:%S') if ticket['close_date'] else '',
                'owner': ticket['owner'],
                'status': ticket['status'],
                'category': ticket['category'],
                'subcategory': ticket['subcategory'],
                'pipeline': ticket['pipeline'],
                'response_time_hours': ticket['response_time_hours'] if ticket['response_time_hours'] else '',
                'response_time_hms': ticket['response_time_str'],
                'company': ticket['company'],
                'emails': ticket['emails'],
                'description': ticket['description']
            })

    print(f"\n\n✅ Detailed results exported to: {output_file}")
    print("=" * 100)

if __name__ == "__main__":
    main()
