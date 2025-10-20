#!/usr/bin/env python3
"""
Diagnose why widgets show no data on Cloud Run
Checks Firestore data for required columns
"""

import pandas as pd
from firestore_db import get_database
from datetime import datetime, timedelta
import pytz

def check_ticket_data():
    """Check if ticket data has required columns for widgets"""
    print("\n" + "="*60)
    print("CHECKING TICKET DATA")
    print("="*60)
    
    try:
        db = get_database()
        if db.db is None:
            print("❌ Firestore not available")
            return
        
        # Get recent tickets
        end_dt = datetime.now(pytz.UTC)
        start_dt = end_dt - timedelta(weeks=12)
        
        df = db.get_tickets(start_date=start_dt, end_date=end_dt, limit=100)
        
        if df.empty:
            print("❌ No tickets found in Firestore")
            return
        
        print(f"✅ Found {len(df)} tickets")
        print(f"\n📋 Columns in Firestore:")
        for col in sorted(df.columns):
            print(f"  - {col}")
        
        # Check required columns for widgets
        required_cols = {
            'weekly_response_breakdown': ['Create date', 'First Response Time (Hours)', 'Weekend_Ticket'],
            'agent_ticket_volume_distribution': ['Case Owner', 'Weekend_Ticket'],
            'agent_response_time_comparison': ['Case Owner', 'First Response Time (Hours)', 'Pipeline'],
            'pipeline_distribution_by_agent': ['Case Owner', 'Pipeline'],
            'pipeline_response_time_heatmap': ['Case Owner', 'Pipeline', 'First Response Time (Hours)']
        }
        
        print(f"\n🔍 Widget Column Requirements:")
        for widget, cols in required_cols.items():
            missing = [c for c in cols if c not in df.columns]
            if missing:
                print(f"  ❌ {widget}: MISSING {missing}")
            else:
                print(f"  ✅ {widget}: All columns present")
        
        # Check data types and sample values
        print(f"\n📊 Sample Data:")
        if 'Weekend_Ticket' in df.columns:
            print(f"  Weekend_Ticket: {df['Weekend_Ticket'].value_counts().to_dict()}")
        if 'Pipeline' in df.columns:
            print(f"  Pipeline values: {df['Pipeline'].unique()[:10]}")
        if 'Case Owner' in df.columns:
            print(f"  Case Owner values: {df['Case Owner'].unique()[:10]}")
        if 'First Response Time (Hours)' in df.columns:
            valid_response_times = df['First Response Time (Hours)'].notna().sum()
            print(f"  First Response Time: {valid_response_times}/{len(df)} have values")
            
    except Exception as e:
        print(f"❌ Error checking ticket data: {e}")
        import traceback
        traceback.print_exc()

def check_chat_data():
    """Check if chat data has required columns for widgets"""
    print("\n" + "="*60)
    print("CHECKING CHAT DATA")
    print("="*60)
    
    try:
        db = get_database()
        if db.db is None:
            print("❌ Firestore not available")
            return
        
        # Get recent chats
        end_dt = datetime.now(pytz.UTC)
        start_dt = end_dt - timedelta(weeks=12)
        
        df = db.get_chats(start_date=start_dt, end_date=end_dt, limit=100)
        
        if df.empty:
            print("❌ No chats found in Firestore")
            return
        
        print(f"✅ Found {len(df)} chats")
        print(f"\n📋 Columns in Firestore:")
        for col in sorted(df.columns):
            print(f"  - {col}")
        
        # Check required columns for widgets
        required_cols = {
            'daily_chat_trends_performance': ['chat_creation_date_adt', 'rating_value', 'bot_transfer'],
            'chat_weekly_volume_breakdown': ['chat_creation_date_adt', 'agent_type'],
            'bot_volume_duration': ['agent_type', 'display_agent', 'duration_minutes'],
            'human_volume_duration': ['agent_type', 'human_agents', 'duration_minutes']
        }
        
        print(f"\n🔍 Widget Column Requirements:")
        for widget, cols in required_cols.items():
            missing = [c for c in cols if c not in df.columns]
            if missing:
                print(f"  ❌ {widget}: MISSING {missing}")
            else:
                print(f"  ✅ {widget}: All columns present")
        
        # Check for duplicates
        if 'chat_id' in df.columns:
            duplicates = df['chat_id'].duplicated().sum()
            print(f"\n⚠️ Duplicate chat_ids: {duplicates}/{len(df)}")
        
        # Check data types and sample values
        print(f"\n📊 Sample Data:")
        if 'agent_type' in df.columns:
            print(f"  agent_type: {df['agent_type'].value_counts().to_dict()}")
        if 'rating_value' in df.columns:
            rated = df['rating_value'].notna().sum()
            print(f"  rating_value: {rated}/{len(df)} have ratings")
        if 'bot_transfer' in df.columns:
            transfers = df['bot_transfer'].sum() if df['bot_transfer'].dtype == 'bool' else df['bot_transfer'].value_counts().to_dict()
            print(f"  bot_transfer: {transfers}")
            
    except Exception as e:
        print(f"❌ Error checking chat data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_ticket_data()
    check_chat_data()
    
    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)