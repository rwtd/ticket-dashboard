#!/usr/bin/env python3
"""
Ticket Analytics Tool
Focused ticket analytics without chat processing
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

from common_utils import (
    create_argument_parser, detect_data_sources, get_date_range,
    create_output_directory, print_analysis_header, print_data_source_summary,
    save_dashboard_file, save_summary_file, save_csv_file
)
from ticket_processor import TicketDataProcessor
from dashboard_builder import DashboardBuilder

class TicketAnalytics:
    """Ticket-focused analytics application"""
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.ticket_processor = None
        self.dashboard_builder = DashboardBuilder()
        
    def run(self) -> None:
        """Main application entry point"""
        try:
            # Parse arguments
            parser = create_argument_parser()
            args = parser.parse_args()
            
            # Detect available ticket data
            sources = self._detect_ticket_sources()
            
            if not args.quiet:
                print_data_source_summary({'tickets': sources.get('tickets', [])})
            
            if not sources.get('tickets'):
                print("❌ No ticket CSV files found in ./tickets/ directory")
                return
            
            # Get date range (with timezone for tickets)
            start_dt, end_dt, label = get_date_range(args, use_timezone=True)
            
            if not args.quiet:
                date_range = None
                if start_dt and end_dt:
                    date_range = f"{start_dt:%Y-%m-%d %H:%M %Z} → {end_dt:%Y-%m-%d %H:%M %Z}"
                print_analysis_header(label, date_range)
            
            # Create output directory
            output_dir = create_output_directory(self.base_dir, args.output_dir)
            
            # Process ticket data
            self.ticket_processor = TicketDataProcessor(schedule_file=args.schedule_file)
            ticket_analytics = self._process_tickets(sources['tickets'], start_dt, end_dt, label, args)
            
            # Generate dashboard
            self._generate_dashboard(ticket_analytics, label, args, output_dir)
            
            if not args.quiet:
                print(f"\n🎯 Ticket analytics saved in {output_dir}")
                
                # Optional Google Sheets export
                if getattr(args, 'export_to_sheets', False):
                    try:
                        from google_sheets_exporter import export_to_google_sheets
                        print("\n📊 Exporting to Google Sheets...")
                        spreadsheet_id = export_to_google_sheets(
                            results_dir=Path(output_dir),
                            spreadsheet_id=getattr(args, 'sheets_id', None),
                            credentials_path=getattr(args, 'credentials_path', 'credentials.json')
                        )
                        if spreadsheet_id:
                            print(f"✅ Google Sheets export: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
                        else:
                            print("⚠️ Google Sheets export failed - check credentials and permissions")
                    except ImportError as e:
                        print(f"⚠️ Google Sheets export unavailable: {e}")
                    except Exception as e:
                        print(f"⚠️ Google Sheets export failed: {e}")
                
        except Exception as e:
            print(f"❌ {e}")
            sys.exit(1)
    
    def _detect_ticket_sources(self) -> Dict:
        """Detect available ticket CSV files"""
        ticket_dir = self.base_dir / "tickets"
        if not ticket_dir.exists():
            return {'tickets': []}
        
        ticket_files = []
        for pattern in ["*.csv"]:
            ticket_files.extend(ticket_dir.glob(pattern))
        
        return {'tickets': ticket_files}
    
    def _process_tickets(self, ticket_files: List[Path], start_dt, end_dt, label: str, args) -> Dict:
        """Process ticket data and generate analytics"""
        print("\n📋 Processing ticket data...")
        
        # Load and process data
        self.ticket_processor.load_data(ticket_files)
        self.ticket_processor.process_data()
        
        # Filter by date range
        analysis_df, original_count, filtered_count = self.ticket_processor.filter_date_range(start_dt, end_dt)
        
        if start_dt and end_dt:
            print(f"Date filtering: {original_count:,} → {filtered_count:,} tickets")
        
        # Generate analytics
        analytics = self.ticket_processor.generate_analytics(analysis_df, args)
        analytics['label'] = label
        analytics['processed_df'] = self.ticket_processor.df
        analytics['analysis_df'] = analysis_df
        
        return analytics
    
    def _generate_dashboard(self, ticket_analytics: Dict, label: str, args, output_dir: Path) -> None:
        """Generate ticket dashboard files"""
        
        # Ticket dashboard
        ticket_html = self.dashboard_builder.build_ticket_dashboard(ticket_analytics, label, args)
        save_dashboard_file(output_dir, "ticket_analytics_dashboard.html", ticket_html)
        
        # Ticket summary
        ticket_summary = self.ticket_processor.create_summary_text(ticket_analytics['analysis_df'], label)
        save_summary_file(output_dir, "ticket_analytics_summary.txt", ticket_summary)
        
        # Save processed ticket CSV
        save_csv_file(output_dir, "tickets_transformed.csv", ticket_analytics['processed_df'])
        
        # Create simple index file
        index_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Ticket Analytics - {output_dir.name}</title>
    <meta charset="utf-8">
    <style>{self.dashboard_builder.css}</style>
</head>
<body>
    <h1>📋 Ticket Analytics Dashboard<br>
        <small style="font-size:0.6em;color:#666">{output_dir.name}</small>
    </h1>
    
    <div class="section">
        <h2>🔍 Available Reports</h2>
        <div class="section">
            <h3>📋 <a href="ticket_analytics_dashboard.html">Ticket Analytics Dashboard</a></h3>
            <p>Response times, agent performance, weekend analysis, pipeline breakdown</p>
            <p><small>📄 <a href="ticket_analytics_summary.txt">Text Summary</a> | 
            📊 <a href="tickets_transformed.csv">Processed Data (CSV)</a></small></p>
        </div>
    </div>
    
    <div class="section" style="text-align:center;color:#666;font-size:0.9em;">
        <p>Generated by Ticket Analytics Tool</p>
    </div>
</body>
</html>
        """
        
        save_dashboard_file(output_dir, "index.html", index_html)

def main():
    """Application entry point"""
    app = TicketAnalytics()
    app.run()

if __name__ == "__main__":
    main()