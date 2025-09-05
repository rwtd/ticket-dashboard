#!/bin/bash
# Auto-sync startup script for ticket dashboard

echo "🚀 Starting Ticket Dashboard Auto-Sync Monitor"
echo "📊 Target Sheet: https://docs.google.com/spreadsheets/d/1fDek0n36V1oFAofYDzSsfvOeVu6hTjWjq-9zcy_JxEk"
echo "📂 Monitoring: ./tickets and ./chats directories"
echo "👁️  Mode: Real-time file monitoring (watchdog)"
echo ""

# Start the monitor with your sheet ID
python auto_sync_monitor.py --spreadsheet-id "1fDek0n36V1oFAofYDzSsfvOeVu6hTjWjq-9zcy_JxEk"