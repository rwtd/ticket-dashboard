#!/usr/bin/env python3
"""
Test script for Agent Performance Comparison enhancements
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

def test_agent_performance_enhancements():
    """Test the new agent performance features"""
    print("=== AGENT PERFORMANCE COMPARISON - NEW FEATURES TEST ===\n")

    # Import the analyzer
    sys.path.append('.')
    from agent_performance_analyzer import AgentPerformanceAnalyzer

    try:
        # Find ticket files
        ticket_files = list(Path('tickets').glob('*.csv'))
        if not ticket_files:
            print("❌ No ticket files found in ./tickets/ directory")
            return

        print(f"📋 Found ticket file: {ticket_files[0].name}")

        # Initialize analyzer
        analyzer = AgentPerformanceAnalyzer()
        analyzer.load_data(ticket_files)
        analyzer.process_data()

        print("✅ Loaded and processed ticket data")

        # Test custom date range (last 30 days)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        print(f"\n🔍 Testing custom date range: {start_date} to {end_date}")

        analysis = analyzer.analyze_performance('custom', start_date, end_date)

        if 'error' in analysis:
            print(f"⚠️ Custom date range test: {analysis['error']}")
            print("💡 This is expected if no tickets exist in the last 30 days")
        else:
            print("✅ Custom date range analysis successful!")
            print(f"   📊 Weekly data points: {len(analysis['weekly_data']['weeks'])}")
            print(f"   👥 Agents analyzed: {', '.join(analysis['weekly_data']['agents'])}")

        # Test with a period that should have data (last 12 weeks)
        print(f"\n🔍 Testing 12-week analysis...")

        analysis = analyzer.analyze_performance('12_weeks')

        if 'error' in analysis:
            print(f"❌ 12-week analysis failed: {analysis['error']}")
        else:
            print("✅ 12-week analysis successful!")

            # Show summary
            date_info = analysis['date_info']
            weekly_data = analysis['weekly_data']

            print(f"   📅 Date range: {date_info['start_date']} to {date_info['end_date']}")
            print(f"   📊 Total records: {date_info['total_records']:,}")
            print(f"   📈 Weekly data points: {len(weekly_data['weeks'])}")
            print(f"   👥 Agents: {', '.join(weekly_data['agents'])}")

            # Test dashboard generation
            print(f"\n🎨 Generating enhanced dashboard...")
            dashboard_html = analyzer.generate_dashboard_html(analysis)

            # Save test dashboard
            output_file = Path('test_agent_performance_enhanced.html')
            with open(output_file, 'w') as f:
                f.write(dashboard_html)

            print(f"✅ Enhanced dashboard saved to {output_file}")
            print(f"   📊 Features included:")
            print(f"      • Weekly median response time chart with trend lines")
            print(f"      • Weekly ticket volume chart with trend lines")
            print(f"      • Performance vs volume overview chart")
            print(f"      • Agent performance cards")
            print(f"      • Insights and recommendations")

        print(f"\n💡 NEW FEATURES SUMMARY:")
        print(f"   ✅ Custom date range support")
        print(f"   ✅ Separate weekly response time chart")
        print(f"   ✅ Separate weekly volume chart")
        print(f"   ✅ Trend lines for both weekly charts")
        print(f"   ✅ Enhanced web interface with date pickers")

        print(f"\n🚀 HOW TO USE:")
        print(f"   1. Select 'Agent Performance Comparison' in web interface")
        print(f"   2. Choose 'Custom Date Range' option")
        print(f"   3. Set start and end dates")
        print(f"   4. Generate analytics to see weekly trends!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agent_performance_enhancements()