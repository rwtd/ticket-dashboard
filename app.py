#!/usr/bin/env python3
"""
Ticket Dashboard Web UI
A simple Flask web interface for the ticket analytics dashboard
"""

import os
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import tempfile
import requests
import pandas as pd

# Import our analytics components
from ticket_processor import TicketDataProcessor
from chat_processor import ChatDataProcessor
from dashboard_builder import DashboardBuilder
from agent_performance_analyzer import AgentPerformanceAnalyzer
from individual_agent_analyzer import IndividualAgentAnalyzer
from export_utils import DashboardExporter
from processing_logger import get_processing_logger
from common_utils import (
    parse_date_string, get_date_range, create_output_directory,
    save_dashboard_file, save_summary_file, save_csv_file
)
from google_sheets_exporter import GoogleSheetsExporter

app = Flask(__name__)
app.secret_key = 'ticket-dashboard-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configuration
UPLOAD_FOLDER = Path(__file__).parent / 'uploads'
RESULTS_FOLDER = Path(__file__).parent / 'results'
TICKETS_FOLDER = Path(__file__).parent / 'tickets'
CHATS_FOLDER = Path(__file__).parent / 'chats'
ALLOWED_EXTENSIONS = {'csv'}

# Ensure directories exist
UPLOAD_FOLDER.mkdir(exist_ok=True)
RESULTS_FOLDER.mkdir(exist_ok=True)
TICKETS_FOLDER.mkdir(exist_ok=True)
CHATS_FOLDER.mkdir(exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main dashboard interface"""
    # Get list of existing ticket files
    ticket_files = []
    if TICKETS_FOLDER.exists():
        for file in TICKETS_FOLDER.glob('*.csv'):
            ticket_files.append({
                'name': file.name,
                'size': file.stat().st_size,
                'modified': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'type': 'ticket'
            })
    
    # Get list of existing chat files
    chat_files = []
    if CHATS_FOLDER.exists():
        for file in CHATS_FOLDER.glob('*.csv'):
            chat_files.append({
                'name': file.name,
                'size': file.stat().st_size,
                'modified': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'type': 'chat'
            })
    
    # Get list of uploaded files
    uploaded_files = []
    for file in UPLOAD_FOLDER.glob('*.csv'):
        uploaded_files.append({
            'name': file.name,
            'size': file.stat().st_size,
            'modified': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
            'type': 'uploaded'
        })
    
    # Get list of recent results
    recent_results = []
    for result_dir in sorted(RESULTS_FOLDER.glob('*'), reverse=True)[:5]:
        if result_dir.is_dir():
            recent_results.append({
                'name': result_dir.name,
                'created': datetime.fromtimestamp(result_dir.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'path': str(result_dir.relative_to(Path(__file__).parent))
            })
    
    return render_template('index.html', 
                         ticket_files=ticket_files,
                         chat_files=chat_files,
                         uploaded_files=uploaded_files,
                         recent_results=recent_results)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = filename.rsplit('.', 1)
        filename = f"{name}_{timestamp}.{ext}"
        
        file_path = UPLOAD_FOLDER / filename
        file.save(str(file_path))
        flash(f'File "{filename}" uploaded successfully')
    else:
        flash('Invalid file type. Please upload a CSV file.')
    
    return redirect(url_for('index'))

@app.route('/analyze', methods=['POST'])
def analyze():
    """Process analytics request"""
    try:
        data = request.get_json()
        
        # Get parameters
        date_type = data.get('dateType', 'all')
        start_date = data.get('startDate')
        end_date = data.get('endDate')
        week_date = data.get('weekDate')
        day_date = data.get('dayDate')
        data_source = data.get('dataSource', 'existing')
        analytics_type = data.get('analyticsType', 'tickets')  # 'tickets', 'chats', 'agent_performance', or 'combined'
        selected_files = data.get('selectedFiles', [])
        include_delayed = data.get('includeDelayed', False)
        performance_period = data.get('performancePeriod', 'all')
        
        # Handle agent performance comparison separately
        if analytics_type == 'agent_performance':
            custom_start_date = data.get('customStartDate')
            custom_end_date = data.get('customEndDate')
            return handle_agent_performance_analysis(data_source, selected_files, performance_period, custom_start_date, custom_end_date)
        
        # Handle individual agent analysis separately
        if analytics_type == 'individual_agent':
            individual_period = data.get('individualPeriod', 'all')
            selected_agent = data.get('selectedAgent', '')
            return handle_individual_agent_analysis(data_source, selected_files, individual_period, selected_agent)
        
        # Determine which files to use based on analytics type and data source
        file_paths = []
        
        if data_source == 'uploaded':
            file_paths = [UPLOAD_FOLDER / f for f in selected_files if f.endswith('.csv')]
        else:
            # Handle different analytics types
            if analytics_type == 'tickets':
                source_dir = TICKETS_FOLDER
            elif analytics_type == 'chats':
                source_dir = CHATS_FOLDER
            elif analytics_type == 'combined':
                # For combined analysis, we need both directories
                pass  # Will be handled in the combined section
            else:
                return jsonify({'error': 'Invalid analytics type'}), 400
            
            if analytics_type != 'combined':
                if selected_files:
                    file_paths = [source_dir / f for f in selected_files if f.endswith('.csv')]
                else:
                    file_paths = list(source_dir.glob('*.csv'))
        
        if not file_paths and analytics_type != 'combined':
            available_files = list(source_dir.glob('*.csv')) if 'source_dir' in locals() else []
            return jsonify({
                'error': f'No CSV files found for {analytics_type} analysis',
                'debug': f'Checked directory: {source_dir if "source_dir" in locals() else "N/A"}, Available files: {[f.name for f in available_files]}'
            }), 400
        
        # Process date parameters
        start_dt = None
        end_dt = None
        label = "All Time"
        
        if date_type == 'week' and week_date:
            try:
                # Convert YYYY-MM-DD to datetime object
                start = datetime.strptime(week_date, '%Y-%m-%d')
                if start.weekday() != 0:
                    return jsonify({'error': 'Week date must be a Monday'}), 400
                
                import pytz
                atlantic = pytz.timezone("Canada/Atlantic")
                start_dt = atlantic.localize(start.replace(hour=6, minute=0, second=0))
                end_dt = start_dt + timedelta(days=7, seconds=-1)
                label = f"Week of {start:%B %d, %Y}"
            except ValueError as e:
                return jsonify({'error': f'Invalid week date: {e}'}), 400
                
        elif date_type == 'day' and day_date:
            try:
                # Convert YYYY-MM-DD to datetime object
                day = datetime.strptime(day_date, '%Y-%m-%d')
                import pytz
                atlantic = pytz.timezone("Canada/Atlantic")
                start_dt = atlantic.localize(day.replace(hour=0, minute=0, second=0))
                end_dt = atlantic.localize(day.replace(hour=23, minute=59, second=59))
                label = f"Day of {day:%B %d, %Y}"
            except ValueError as e:
                return jsonify({'error': f'Invalid day date: {e}'}), 400
                
        elif date_type == 'custom' and start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                
                if end < start:
                    return jsonify({'error': 'End date must be after start date'}), 400
                
                import pytz
                atlantic = pytz.timezone("Canada/Atlantic")
                start_dt = atlantic.localize(start.replace(hour=0, minute=0, second=0))
                end_dt = atlantic.localize(end.replace(hour=23, minute=59, second=59))
                label = f"Custom range {start:%B %d, %Y} – {end:%B %d, %Y}"
            except ValueError as e:
                return jsonify({'error': f'Invalid date format: {e}'}), 400
        
        # Process the data based on analytics type
        if analytics_type == 'tickets':
            # Debug information
            print(f"Debug: Processing {len(file_paths)} ticket files:")
            for fp in file_paths:
                print(f"  - {fp}: exists={fp.exists()}, size={fp.stat().st_size if fp.exists() else 'N/A'}")
            
            processor = TicketDataProcessor()
            try:
                processor.load_data(file_paths)
                processor.process_data()
            except Exception as e:
                print(f"Error in ticket processing: {e}")
                return jsonify({'error': f'Failed to process ticket data: {str(e)}'}), 500
            
            # Filter by date range
            analysis_df, original_count, filtered_count = processor.filter_date_range(start_dt, end_dt)
            
            if len(analysis_df) == 0:
                # Get data range for helpful error message
                data_range_msg = "No data range available"
                if hasattr(processor, 'df') and processor.df is not None and len(processor.df) > 0:
                    try:
                        if analytics_type == 'tickets':
                            min_date = processor.df['Create date'].min()
                            max_date = processor.df['Create date'].max()
                        else:  # chats
                            min_date = processor.df['chat_creation_date_adt'].min()
                            max_date = processor.df['chat_creation_date_adt'].max()
                        data_range_msg = f"Available data: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
                    except:
                        data_range_msg = "Data range unavailable"

                return jsonify({
                    'error': f'No {analytics_type} found for the specified date range. {data_range_msg}',
                    'suggestion': 'Try selecting a date within your data range, or use "All Time" to see all available data.'
                }), 400
            
            # Create a mock args object for analytics generation
            class MockArgs:
                def __init__(self):
                    self.include_delayed_table = include_delayed
                    self.schedule_file = 'config/schedule.yaml'
            
            args = MockArgs()
            
            # Generate analytics
            analytics = processor.generate_analytics(analysis_df, args)
            analytics['label'] = label
            analytics['processed_df'] = processor.df
            analytics['analysis_df'] = analysis_df
            
            dashboard_type = 'ticket'
            summary_text = processor.create_summary_text(analysis_df, label)
            
        elif analytics_type == 'chats':
            # Debug information
            print(f"Debug: Processing {len(file_paths)} chat files:")
            for fp in file_paths:
                print(f"  - {fp}: exists={fp.exists()}, size={fp.stat().st_size if fp.exists() else 'N/A'}")
            
            processor = ChatDataProcessor()
            try:
                processor.load_data(file_paths)
                processor.process_data()
            except Exception as e:
                print(f"Error in chat processing: {e}")
                return jsonify({'error': f'Failed to process chat data: {str(e)}'}), 500
            
            # Filter by date range
            analysis_df, original_count, filtered_count = processor.filter_date_range(start_dt, end_dt)
            
            if len(analysis_df) == 0:
                # Get data range for helpful error message
                data_range_msg = "No data range available"
                if hasattr(processor, 'df') and processor.df is not None and len(processor.df) > 0:
                    try:
                        if analytics_type == 'tickets':
                            min_date = processor.df['Create date'].min()
                            max_date = processor.df['Create date'].max()
                        else:  # chats
                            min_date = processor.df['chat_creation_date_adt'].min()
                            max_date = processor.df['chat_creation_date_adt'].max()
                        data_range_msg = f"Available data: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
                    except:
                        data_range_msg = "Data range unavailable"

                return jsonify({
                    'error': f'No {analytics_type} found for the specified date range. {data_range_msg}',
                    'suggestion': 'Try selecting a date within your data range, or use "All Time" to see all available data.'
                }), 400
            
            # Create a mock args object for analytics generation
            class MockArgs:
                def __init__(self):
                    self.include_delayed_table = include_delayed
                    self.schedule_file = 'config/schedule.yaml'
            
            args = MockArgs()
            
            # Generate analytics
            analytics = processor.generate_analytics(analysis_df, args)
            analytics['label'] = label
            analytics['processed_df'] = processor.df
            analytics['analysis_df'] = analysis_df
            
            dashboard_type = 'chat'
            summary_text = processor.create_summary_text(analysis_df, label)
            
        elif analytics_type == 'combined':
            # Combined analytics: process both tickets and chats
            print(f"Debug: Processing combined analytics")
            
            # Get both ticket and chat files from separate lists if provided
            ticket_files = []
            chat_files = []
            
            # Use separate file lists if provided (new approach)
            frontend_ticket_files = data.get('ticketFiles', [])
            frontend_chat_files = data.get('chatFiles', [])
            
            if data_source == 'uploaded':
                # For uploaded files, use provided lists or fallback to pattern matching
                if frontend_ticket_files or frontend_chat_files:
                    ticket_files = [UPLOAD_FOLDER / f for f in frontend_ticket_files if (UPLOAD_FOLDER / f).exists()]
                    chat_files = [UPLOAD_FOLDER / f for f in frontend_chat_files if (UPLOAD_FOLDER / f).exists()]
                else:
                    # Fallback: distinguish by filename patterns
                    for file in selected_files:
                        file_path = UPLOAD_FOLDER / file
                        if file_path.exists() and file.endswith('.csv'):
                            filename_lower = file.lower()
                            if any(keyword in filename_lower for keyword in ['ticket', 'support', 'case']):
                                ticket_files.append(file_path)
                            elif any(keyword in filename_lower for keyword in ['chat', 'livechat', 'conversation']):
                                chat_files.append(file_path)
                            else:
                                ticket_files.append(file_path)
            else:
                # For existing files, use separate lists from frontend
                if frontend_ticket_files or frontend_chat_files:
                    ticket_files = [TICKETS_FOLDER / f for f in frontend_ticket_files if (TICKETS_FOLDER / f).exists()]
                    chat_files = [CHATS_FOLDER / f for f in frontend_chat_files if (CHATS_FOLDER / f).exists()]
                else:
                    # Fallback: auto-detect all files
                    ticket_files = list(TICKETS_FOLDER.glob('*.csv'))
                    chat_files = list(CHATS_FOLDER.glob('*.csv'))
            
            print(f"Debug: Found {len(ticket_files)} ticket files and {len(chat_files)} chat files")
            print(f"Debug: Ticket files: {[f.name for f in ticket_files]}")
            print(f"Debug: Chat files: {[f.name for f in chat_files]}")
            
            # Process tickets
            ticket_analytics = None
            ticket_processor = None
            if ticket_files:
                try:
                    ticket_processor = TicketDataProcessor()
                    ticket_processor.load_data(ticket_files)
                    ticket_processor.process_data()
                    
                    # Filter by date range
                    ticket_analysis_df, _, _ = ticket_processor.filter_date_range(start_dt, end_dt)
                    
                    if len(ticket_analysis_df) > 0:
                        # Create mock args
                        class MockArgs:
                            def __init__(self):
                                self.include_delayed_table = include_delayed
                                self.schedule_file = 'config/schedule.yaml'
                        
                        args = MockArgs()
                        ticket_analytics = ticket_processor.generate_analytics(ticket_analysis_df, args)
                        ticket_analytics['label'] = label
                        ticket_analytics['processed_df'] = ticket_processor.df
                        ticket_analytics['analysis_df'] = ticket_analysis_df
                        
                        print(f"✅ Processed {len(ticket_analysis_df)} ticket records")
                except Exception as e:
                    print(f"Warning: Ticket processing failed: {e}")
            
            # Process chats
            chat_analytics = None
            chat_processor = None
            if chat_files:
                try:
                    chat_processor = ChatDataProcessor()
                    chat_processor.load_data(chat_files)
                    chat_processor.process_data()
                    
                    # Filter by date range
                    chat_analysis_df, _, _ = chat_processor.filter_date_range(start_dt, end_dt)
                    
                    if len(chat_analysis_df) > 0:
                        # Create mock args
                        class MockArgs:
                            def __init__(self):
                                self.include_delayed_table = include_delayed
                                self.schedule_file = 'config/schedule.yaml'
                        
                        args = MockArgs()
                        chat_analytics = chat_processor.generate_analytics(chat_analysis_df, args)
                        chat_analytics['label'] = label
                        chat_analytics['processed_df'] = chat_processor.df
                        chat_analytics['analysis_df'] = chat_analysis_df
                        
                        print(f"✅ Processed {len(chat_analysis_df)} chat records")
                except Exception as e:
                    print(f"Warning: Chat processing failed: {e}")
            
            if not ticket_analytics and not chat_analytics:
                return jsonify({'error': 'No valid data found for combined analysis'}), 400
            
            # Store both analytics for dashboard generation
            analytics = {
                'ticket_analytics': ticket_analytics,
                'chat_analytics': chat_analytics,
                'label': label
            }
            
            dashboard_type = 'combined'
            summary_text = f"Combined Analytics Report for {label}\n\n"
            if ticket_analytics:
                summary_text += ticket_processor.create_summary_text(ticket_analytics['analysis_df'], label) + "\n\n"
            if chat_analytics:
                summary_text += chat_processor.create_summary_text(chat_analytics['analysis_df'], label)
        
        else:
            return jsonify({'error': 'Invalid analytics type'}), 400
        
        # Create output directory
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_dir = RESULTS_FOLDER / timestamp
        output_dir.mkdir(exist_ok=True)
        
        # Generate dashboard based on type
        dashboard_builder = DashboardBuilder()
        if dashboard_type == 'ticket':
            dashboard_html = dashboard_builder.build_ticket_dashboard(analytics, label, args)
            save_dashboard_file(output_dir, "ticket_analytics_dashboard.html", dashboard_html)
            save_summary_file(output_dir, "ticket_analytics_summary.txt", summary_text)
            save_csv_file(output_dir, "tickets_transformed.csv", analytics['processed_df'])
        elif dashboard_type == 'chat':
            dashboard_html = dashboard_builder.build_chat_dashboard(analytics, label, args)
            save_dashboard_file(output_dir, "chat_analytics_dashboard.html", dashboard_html)
            save_summary_file(output_dir, "chat_analytics_summary.txt", summary_text)
            save_csv_file(output_dir, "chats_transformed.csv", analytics['processed_df'])
        elif dashboard_type == 'combined':
            # Generate both ticket and chat dashboards
            ticket_dashboard_html = None
            chat_dashboard_html = None
            
            if analytics['ticket_analytics']:
                args = type('MockArgs', (), {
                    'include_delayed_table': include_delayed,
                    'schedule_file': 'config/schedule.yaml'
                })()
                ticket_dashboard_html = dashboard_builder.build_ticket_dashboard(analytics['ticket_analytics'], label, args)
                save_dashboard_file(output_dir, "ticket_analytics_dashboard.html", ticket_dashboard_html)
                save_csv_file(output_dir, "tickets_transformed.csv", analytics['ticket_analytics']['processed_df'])
            
            if analytics['chat_analytics']:
                args = type('MockArgs', (), {
                    'include_delayed_table': include_delayed,
                    'schedule_file': 'config/schedule.yaml'
                })()
                chat_dashboard_html = dashboard_builder.build_chat_dashboard(analytics['chat_analytics'], label, args)
                save_dashboard_file(output_dir, "chat_analytics_dashboard.html", chat_dashboard_html)
                save_csv_file(output_dir, "chats_transformed.csv", analytics['chat_analytics']['processed_df'])
            
            # Save combined summary
            save_summary_file(output_dir, "combined_analytics_summary.txt", summary_text)
            
            # Use the ticket dashboard as the main one if available
            dashboard_html = ticket_dashboard_html or chat_dashboard_html
        
        # Create dynamic index file based on dashboard type
        if dashboard_type == 'combined':
            # Combined index with both ticket and chat sections
            title_text = "📊 Combined Analytics Results"
            reports_section = ""
            
            if analytics.get('ticket_analytics'):
                total_tickets = len(analytics['ticket_analytics']['analysis_df'])
                reports_section += f"""
                <div class="section">
                    <h3>📋 <a href="ticket_analytics_dashboard.html">Ticket Analytics Dashboard</a></h3>
                    <p>Response times, agent performance, weekend analysis, pipeline breakdown</p>
                    <p><strong>Records:</strong> {total_tickets:,} tickets</p>
                    <p><small>📊 <a href="tickets_transformed.csv">Processed Data (CSV)</a></small></p>
                </div>"""
            
            if analytics.get('chat_analytics'):
                total_chats = len(analytics['chat_analytics']['analysis_df'])
                reports_section += f"""
                <div class="section">
                    <h3>💬 <a href="chat_analytics_dashboard.html">Chat Analytics Dashboard</a></h3>
                    <p>Bot performance, satisfaction analysis, transfer rates, volume trends</p>
                    <p><strong>Records:</strong> {total_chats:,} chats</p>
                    <p><small>📊 <a href="chats_transformed.csv">Processed Data (CSV)</a></small></p>
                </div>"""
            
            total_records = sum([
                len(analytics['ticket_analytics']['analysis_df']) if analytics.get('ticket_analytics') else 0,
                len(analytics['chat_analytics']['analysis_df']) if analytics.get('chat_analytics') else 0
            ])
            total_files = len(ticket_files) + len(chat_files)
            
        elif dashboard_type == 'ticket':
            title_text = "📋 Ticket Analytics Results"
            total_records = len(analysis_df)
            total_files = len(file_paths)
            reports_section = f"""
            <div class="section">
                <h3>📋 <a href="ticket_analytics_dashboard.html">Ticket Analytics Dashboard</a></h3>
                <p>Response times, agent performance, weekend analysis, pipeline breakdown</p>
                <p><small>📄 <a href="ticket_analytics_summary.txt">Text Summary</a> | 
                📊 <a href="tickets_transformed.csv">Processed Data (CSV)</a></small></p>
            </div>"""
            
        elif dashboard_type == 'chat':
            title_text = "💬 Chat Analytics Results"
            total_records = len(analysis_df)
            total_files = len(file_paths)
            reports_section = f"""
            <div class="section">
                <h3>💬 <a href="chat_analytics_dashboard.html">Chat Analytics Dashboard</a></h3>
                <p>Bot performance, satisfaction analysis, transfer rates, volume trends</p>
                <p><small>📄 <a href="chat_analytics_summary.txt">Text Summary</a> | 
                📊 <a href="chats_transformed.csv">Processed Data (CSV)</a></small></p>
            </div>"""
        
        index_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{dashboard_type.title()} Analytics - {timestamp}</title>
    <meta charset="utf-8">
    <style>{dashboard_builder.css}</style>
</head>
<body>
    <h1>{title_text}<br>
        <small style="font-size:0.6em;color:#666">{timestamp}</small>
    </h1>
    
    <div class="section">
        <h2>📊 Analysis Summary</h2>
        <p><strong>Period:</strong> {label}</p>
        <p><strong>Files Processed:</strong> {total_files}</p>
        <p><strong>Records Analyzed:</strong> {total_records:,}</p>
        {f'<p><strong>Date Filtering:</strong> Applied for {label}</p>' if start_dt and end_dt else ''}
    </div>
    
    <div class="section">
        <h2>🔍 Available Reports</h2>
        {reports_section}
        {f'<div class="section"><h3>📝 <a href="combined_analytics_summary.txt">Combined Summary Report</a></h3><p>Comprehensive text summary of both ticket and chat analytics</p></div>' if dashboard_type == 'combined' else ''}
    </div>
    
    <div class="section" style="text-align:center;color:#666;font-size:0.9em;">
        <p>Generated by Ticket Analytics Dashboard</p>
    </div>
</body>
</html>
        """
        
        save_dashboard_file(output_dir, "index.html", index_html)
        
        # Export to Google Sheets if credentials are available
        try:
            # Check for Google Sheets credentials
            creds_path = None
            for path in ['credentials.json', 'service_account_credentials.json']:
                if Path(path).exists():
                    creds_path = path
                    break
            
            if creds_path:
                print(f"📊 Exporting to Google Sheets using {creds_path}")
                
                # Initialize logger for this processing run
                logger = get_processing_logger()
                run_id = logger.start_processing_run(analytics_type, label)
                
                # Initialize Google Sheets exporter
                sheets_exporter = GoogleSheetsExporter(creds_path)
                
                # Export data based on type
                if dashboard_type == 'combined':
                    ticket_df = analytics.get('ticket_analytics', {}).get('processed_df')
                    chat_df = analytics.get('chat_analytics', {}).get('processed_df')
                    
                    spreadsheet_id = sheets_exporter.export_data(
                        ticket_df=ticket_df,
                        chat_df=chat_df,
                        spreadsheet_title=f"Support Analytics Dashboard - {label}"
                    )
                    
                    logger.log_success('SHEETS_SYNC', f'Successfully exported combined data to Google Sheets: {spreadsheet_id}')
                    
                elif dashboard_type == 'ticket':
                    spreadsheet_id = sheets_exporter.export_data(
                        ticket_df=analytics['processed_df'],
                        spreadsheet_title=f"Ticket Analytics - {label}"
                    )
                    logger.log_success('SHEETS_SYNC', f'Successfully exported ticket data to Google Sheets: {spreadsheet_id}')
                    
                elif dashboard_type == 'chat':
                    spreadsheet_id = sheets_exporter.export_data(
                        chat_df=analytics['processed_df'],
                        spreadsheet_title=f"Chat Analytics - {label}"
                    )
                    logger.log_success('SHEETS_SYNC', f'Successfully exported chat data to Google Sheets: {spreadsheet_id}')
                
                logger.end_processing_run('COMPLETED')
                print(f"✅ Successfully exported to Google Sheets: {spreadsheet_id}")
                
            else:
                print("⚠️ No Google Sheets credentials found - skipping export")
                
        except Exception as e:
            print(f"❌ Google Sheets export failed: {str(e)}")
            if 'logger' in locals() and 'run_id' in locals():
                logger.log_error('SHEETS_SYNC', f'Google Sheets export failed: {str(e)}')
                logger.end_processing_run('FAILED')
        
        # Prepare response data based on dashboard type
        response_data = {}
        
        # Add Google Sheets URL if export succeeded
        if 'spreadsheet_id' in locals():
            google_sheets_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            response_data['google_sheets_url'] = google_sheets_url
            response_data['google_sheets_id'] = spreadsheet_id
        
        if dashboard_type == 'combined':
            # For combined, calculate totals
            total_records = 0
            total_files = 0
            
            if analytics.get('ticket_analytics'):
                total_records += len(analytics['ticket_analytics']['analysis_df'])
                total_files += len(ticket_files)
            
            if analytics.get('chat_analytics'):
                total_records += len(analytics['chat_analytics']['analysis_df'])
                total_files += len(chat_files)
            
            dashboard_filename = "index.html"  # Combined uses index as main dashboard
            
            response_data.update({
                'success': True,
                'message': f'Combined analysis completed successfully',
                'result_path': f'results/{timestamp}',
                'records_processed': total_records,
                'files_processed': total_files,
                'dashboard_url': f'/results/{timestamp}/{dashboard_filename}',
                'has_tickets': analytics.get('ticket_analytics') is not None,
                'has_chats': analytics.get('chat_analytics') is not None
            })
            
            return jsonify(response_data)
        else:
            dashboard_filename = f"{dashboard_type}_analytics_dashboard.html"
            
            response_data.update({
                'success': True,
                'message': f'Analysis completed successfully',
                'result_path': f'results/{timestamp}',
                'records_processed': len(analysis_df),
                'files_processed': len(file_paths),
                'dashboard_url': f'/results/{timestamp}/{dashboard_filename}'
            })
            
            return jsonify(response_data)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        app.logger.error(f"Analysis error: {error_details}")
        return jsonify({'error': str(e), 'details': error_details}), 500

@app.route('/results/<path:filename>')
def serve_results(filename):
    """Serve result files"""
    try:
        file_path = RESULTS_FOLDER / filename
        if file_path.exists() and file_path.is_file():
            return send_file(str(file_path))
        else:
            return "File not found", 404
    except Exception as e:
        return str(e), 500

@app.route('/delete_upload/<filename>')
def delete_upload(filename):
    """Delete uploaded file"""
    try:
        file_path = UPLOAD_FOLDER / secure_filename(filename)
        if file_path.exists():
            file_path.unlink()
            flash(f'File "{filename}" deleted successfully')
        else:
            flash(f'File "{filename}" not found')
    except Exception as e:
        flash(f'Error deleting file: {e}')
    
    return redirect(url_for('index'))

def handle_agent_performance_analysis(data_source, selected_files, performance_period, custom_start_date=None, custom_end_date=None):
    """Handle agent performance comparison analysis"""
    try:
        # Determine which files to use
        file_paths = []
        
        if data_source == 'uploaded':
            file_paths = [UPLOAD_FOLDER / f for f in selected_files if f.endswith('.csv')]
        else:
            # Use ticket files for agent performance
            if selected_files:
                file_paths = [TICKETS_FOLDER / f for f in selected_files if f.endswith('.csv')]
            else:
                file_paths = list(TICKETS_FOLDER.glob('*.csv'))
        
        if not file_paths:
            return jsonify({'error': 'No CSV files found for agent performance analysis'}), 400
        
        # Initialize analyzer
        analyzer = AgentPerformanceAnalyzer()
        
        # Load and process data
        analyzer.load_data(file_paths)
        analyzer.process_data()
        
        # Perform analysis
        analysis = analyzer.analyze_performance(performance_period, custom_start_date, custom_end_date)
        
        if 'error' in analysis:
            return jsonify({'error': analysis['error']}), 400
        
        # Generate HTML dashboard
        dashboard_html = analyzer.generate_dashboard_html(analysis)
        
        # Create output directory
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_dir = RESULTS_FOLDER / timestamp
        output_dir.mkdir(exist_ok=True)
        
        # Save dashboard
        save_dashboard_file(output_dir, 'agent_performance_dashboard.html', dashboard_html)
        
        # Generate summary text
        insights = analysis['summary']
        period_desc = analyzer._get_period_description(performance_period)
        date_info = analysis['date_info']
        
        summary_text = f"""
AGENT PERFORMANCE COMPARISON SUMMARY
===================================
Period: {period_desc}
Date Range: {date_info['start_date']} to {date_info['end_date']}
Total Records: {date_info['total_records']:,}
Weekday Records: {date_info['weekday_records']:,}
Non-LiveChat Records: {date_info['non_livechat_records']:,}

PERFORMANCE HIGHLIGHTS:
- Volume Leader: {insights['volume_leader']['agent']} ({insights['volume_leader']['tickets']} tickets, {insights['volume_leader']['percentage']:.1f}%)
- Speed Champion: {insights['speed_leader']['agent']} ({insights['speed_leader']['median_minutes']:.0f} minutes median)
- Most Consistent: {insights['consistency_leader']['agent']} ({insights['consistency_leader']['std_hours']:.2f}h std deviation)

AGENT BREAKDOWN:
"""
        
        for agent in analysis['agent_stats']:
            summary_text += f"""
{agent['Agent']}:
  Total Tickets: {agent['Total_Tickets']} ({agent['Percentage']:.1f}%)
  Median Response: {agent['Median_Response_Hours']:.2f}h ({agent['Median_Response_Hours']*60:.0f} minutes)
  Average Response: {agent['Avg_Response_Hours']:.2f}h
  Consistency (Std Dev): {agent['Std_Response_Hours']:.2f}h
"""
        
        save_summary_file(output_dir, 'agent_performance_summary.txt', summary_text)
        
        # Create index file
        index_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Agent Performance Analysis Results</title></head>
        <body style="font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h1 style="color: #333; margin-bottom: 20px;">🎯 Agent Performance Analysis Complete</h1>
                <div style="background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #2d5a2d; margin: 0 0 10px 0;">Analysis Period: {period_desc}</h3>
                    <p style="color: #2d5a2d; margin: 5px 0;"><strong>Date Range:</strong> {date_info['start_date']} to {date_info['end_date']}</p>
                    <p style="color: #2d5a2d; margin: 5px 0;"><strong>Records Analyzed:</strong> {date_info['non_livechat_records']:,} tickets</p>
                </div>
                <div style="margin: 30px 0;">
                    <a href="agent_performance_dashboard.html" style="display: inline-block; background: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin-right: 10px;">📊 View Interactive Dashboard</a>
                    <a href="agent_performance_summary.txt" style="display: inline-block; background: #2196F3; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">📄 View Text Summary</a>
                </div>
                <div style="background: #f0f8ff; padding: 15px; border-radius: 5px; margin-top: 20px;">
                    <h4 style="color: #1e6ba8; margin-top: 0;">Quick Insights:</h4>
                    <ul style="color: #1e6ba8;">
                        <li><strong>Volume Leader:</strong> {insights['volume_leader']['agent']} ({insights['volume_leader']['tickets']} tickets)</li>
                        <li><strong>Speed Champion:</strong> {insights['speed_leader']['agent']} ({insights['speed_leader']['median_minutes']:.0f} min median)</li>
                        <li><strong>Most Consistent:</strong> {insights['consistency_leader']['agent']} ({insights['consistency_leader']['std_hours']:.2f}h std dev)</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        save_dashboard_file(output_dir, 'index.html', index_html)
        
        return jsonify({
            'success': True,
            'message': f'Agent performance analysis completed for {period_desc}',
            'dashboard_url': f'/results/{output_dir.name}/agent_performance_dashboard.html',
            'summary_url': f'/results/{output_dir.name}/agent_performance_summary.txt',
            'results_url': f'/results/{output_dir.name}/index.html'
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Agent performance analysis error: {error_details}")
        return jsonify({'error': f'Agent performance analysis failed: {str(e)}'}), 500

def handle_individual_agent_analysis(data_source, selected_files, individual_period, selected_agent):
    """Handle individual agent vs team comparison analysis."""
    try:
        if not selected_agent:
            return jsonify({'error': 'No agent selected for analysis'}), 400
            
        # Determine file paths
        file_paths = []
        
        if data_source == 'uploaded':
            file_paths = [UPLOAD_FOLDER / f for f in selected_files if f.endswith('.csv')]
        else:
            # Use ticket files for individual agent analysis
            if selected_files:
                file_paths = [TICKETS_FOLDER / f for f in selected_files if f.endswith('.csv')]
            else:
                file_paths = list(TICKETS_FOLDER.glob('*.csv'))
        
        if not file_paths:
            return jsonify({'error': 'No CSV files found'}), 400
        
        # Create analyzer and load data
        analyzer = IndividualAgentAnalyzer()
        analyzer.load_data(file_paths)
        analyzer.process_data()
        
        # Perform analysis
        analysis = analyzer.analyze_individual_vs_team(selected_agent, individual_period)
        
        if 'error' in analysis:
            return jsonify({'error': analysis['error']}), 400
        
        # Generate dashboard HTML
        dashboard_html = analyzer.generate_dashboard_html(analysis)
        
        # Create output directory
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_dir = RESULTS_FOLDER / timestamp
        output_dir.mkdir(exist_ok=True)
        
        # Save dashboard
        save_dashboard_file(output_dir, 'individual_agent_dashboard.html', dashboard_html)
        
        # Save processed data as CSV for consistency with other dashboards
        save_csv_file(output_dir, 'tickets_transformed.csv', analyzer.processed_data)
        
        # Generate summary text
        insights = analysis['summary']
        period_desc = analyzer._get_period_description(individual_period)
        individual = analysis['individual_stats']
        team = analysis['team_stats']
        comparison = analysis['comparison']
        
        summary_text = f"""Individual Agent vs Team Analysis - {period_desc}
{'=' * 60}

Agent: {selected_agent}
Period: {analysis['date_range']}

PERFORMANCE SUMMARY:
  Volume: {individual['volume']} tickets ({individual['volume_percentage']:.1f}% of team)
  Average Response: {individual['avg_response_hours']:.2f}h (Team: {team['avg_response_hours']:.2f}h)
  Median Response: {individual['median_response_hours']:.2f}h (Team: {team['median_response_hours']:.2f}h)

PERFORMANCE COMPARISON:
  Speed: {comparison['speed']}

KEY INSIGHTS:
"""
        
        for insight in insights:
            summary_text += f"  • {insight}\n"
        
        save_summary_file(output_dir, 'individual_agent_summary.txt', summary_text)
        
        # Create index file
        index_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{selected_agent} vs Team Analysis - {period_desc}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; text-align: center; }}
                .links {{ display: flex; gap: 20px; justify-content: center; margin-top: 30px; }}
                .links a {{ padding: 12px 24px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; }}
                .links a:hover {{ background: #2980b9; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>👤 {selected_agent} vs Team Analysis</h1>
                <p><strong>Period:</strong> {period_desc}</p>
                <p><strong>Date Range:</strong> {analysis['date_range']}</p>
                <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                
                <div class="links">
                    <a href="individual_agent_dashboard.html">📊 View Dashboard</a>
                    <a href="individual_agent_summary.txt">📄 View Summary</a>
                    <a href="tickets_transformed.csv">💾 Download Data (CSV)</a>
                </div>
            </div>
        </body>
        </html>
        """
        
        save_dashboard_file(output_dir, 'index.html', index_html)
        
        return jsonify({
            'success': True,
            'message': f'Individual agent analysis completed for {selected_agent} ({period_desc})',
            'dashboard_url': f'/results/{output_dir.name}/individual_agent_dashboard.html',
            'summary_url': f'/results/{output_dir.name}/individual_agent_summary.txt',
            'results_url': f'/results/{output_dir.name}/index.html'
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Individual agent analysis error: {error_details}")
        return jsonify({'error': f'Individual agent analysis failed: {str(e)}'}), 500

@app.route('/api/results')
def get_results():
    """API endpoint to get all analysis results from the results folder."""
    try:
        results = []
        
        # Scan the results folder for analysis directories
        if RESULTS_FOLDER.exists():
            for result_dir in sorted(RESULTS_FOLDER.iterdir(), reverse=True):
                if result_dir.is_dir() and result_dir.name != 'results':  # Skip nested results folder
                    result_info = analyze_result_directory(result_dir)
                    if result_info:
                        results.append(result_info)
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def analyze_result_directory(result_dir: Path) -> dict:
    """Analyze a results directory to determine its type and available files."""
    try:
        name = result_dir.name
        
        # Get creation time
        created = datetime.fromtimestamp(result_dir.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        # Determine analysis type based on files present
        files = list(result_dir.glob('*.html'))
        analysis_type = 'Unknown'
        
        if any('individual_agent_dashboard' in f.name for f in files):
            analysis_type = 'Individual Agent'
        elif any('agent_performance_dashboard' in f.name for f in files):
            analysis_type = 'Agent Performance'
        elif any('chat_analytics_dashboard' in f.name for f in files):
            analysis_type = 'Chat Analytics'
        elif any('ticket_analytics_dashboard' in f.name for f in files):
            analysis_type = 'Ticket Analytics'
        
        # Check for CSV files
        has_csv = any(result_dir.glob('*.csv'))
        
        return {
            'name': name,
            'path': name,
            'type': analysis_type,
            'created': created,
            'hasCSV': has_csv
        }
        
    except Exception as e:
        print(f"Error analyzing result directory {result_dir}: {e}")
        return None

@app.route('/export/<result_id>/<dashboard_type>/<export_format>')
def export_dashboard(result_id, dashboard_type, export_format):
    """Export dashboard in specified format"""
    try:
        result_dir = RESULTS_FOLDER / result_id
        if not result_dir.exists():
            return jsonify({'error': 'Result directory not found'}), 404
        
        exporter = DashboardExporter(result_dir)
        
        # Get additional parameters from query string
        width = int(request.args.get('width', 1920))
        height = int(request.args.get('height', 1080))
        credentials_path = request.args.get('credentials_path')
        
        # Perform export
        result = exporter.export_dashboard(
            dashboard_type=dashboard_type,
            export_format=export_format,
            width=width,
            height=height,
            credentials_path=credentials_path
        )
        
        if result['success']:
            if export_format == 'google_docs':
                return jsonify({
                    'success': True,
                    'url': result['url'],
                    'format': result['format']
                })
            else:
                # For PNG/PDF, return file for download
                return send_file(
                    result['file_path'],
                    as_attachment=True,
                    download_name=os.path.basename(result['file_path'])
                )
        else:
            return jsonify({'error': result.get('error', 'Export failed')}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results')
def list_results():
    """List all available results for export"""
    results = []
    
    for result_dir in sorted(RESULTS_FOLDER.glob('*'), reverse=True):
        if result_dir.is_dir():
            analysis = analyze_result_directory(result_dir)
            if analysis:
                # Add available dashboard types
                dashboard_files = {}
                if (result_dir / 'ticket_analytics_dashboard.html').exists():
                    dashboard_files['ticket'] = 'Ticket Analytics'
                if (result_dir / 'chat_analytics_dashboard.html').exists():
                    dashboard_files['chat'] = 'Chat Analytics'
                if (result_dir / 'agent_performance_dashboard.html').exists():
                    dashboard_files['agent_performance'] = 'Agent Performance'
                if (result_dir / 'individual_agent_dashboard.html').exists():
                    dashboard_files['individual_agent'] = 'Individual Agent'
                if (result_dir / 'index.html').exists():
                    dashboard_files['combined'] = 'Combined View'
                
                analysis['dashboards'] = dashboard_files
                results.append(analysis)
    
    return jsonify({'results': results})

@app.route('/check_gdocs_config')
def check_gdocs_config():
    """Check if Google Docs credentials are configured"""
    try:
        credentials_path = Path(__file__).parent / 'credentials.json'
        token_path = Path(__file__).parent / 'token.json'
        
        # Check if credentials file exists and is valid JSON
        if credentials_path.exists():
            try:
                with open(credentials_path, 'r') as f:
                    import json
                    creds = json.load(f)
                    # Basic validation of credentials structure
                    if 'installed' in creds or 'web' in creds:
                        return jsonify({'configured': True})
            except (json.JSONDecodeError, KeyError):
                pass
        
        return jsonify({'configured': False})
        
    except Exception as e:
        return jsonify({'configured': False, 'error': str(e)})

@app.route('/upload_gdocs_credentials', methods=['POST'])
def upload_gdocs_credentials():
    """Upload Google Docs API credentials"""
    try:
        if 'credentials' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        file = request.files['credentials']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'File must be a JSON file'})
        
        # Validate JSON structure
        try:
            import json
            content = file.read()
            creds = json.loads(content)
            
            # Basic validation
            if 'installed' not in creds and 'web' not in creds:
                return jsonify({'success': False, 'error': 'Invalid credentials format'})
            
            # Save credentials file
            credentials_path = Path(__file__).parent / 'credentials.json'
            with open(credentials_path, 'wb') as f:
                f.write(content)
            
            return jsonify({'success': True})
            
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'Invalid JSON file'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test_gdocs_connection')
def test_gdocs_connection():
    """Test Google Docs API connection"""
    try:
        from export_utils import export_to_google_docs
        
        # Try to create a test document
        test_content = "<h1>Test Document</h1><p>This is a test document created to verify Google Docs integration.</p>"
        doc_url = export_to_google_docs(test_content, "Dashboard Export Test")
        
        if doc_url:
            return jsonify({'success': True, 'test_doc_url': doc_url})
        else:
            return jsonify({'success': False, 'error': 'Failed to create test document'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reset_gdocs_credentials', methods=['POST'])
def reset_gdocs_credentials():
    """Reset Google Docs credentials"""
    try:
        credentials_path = Path(__file__).parent / 'credentials.json'
        token_path = Path(__file__).parent / 'token.json'
        
        # Remove credentials and token files
        if credentials_path.exists():
            credentials_path.unlink()
        
        if token_path.exists():
            token_path.unlink()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/processing-logs')
def get_processing_logs():
    """Get recent processing logs"""
    try:
        logger = get_processing_logger()
        recent_runs = logger.get_recent_runs(limit=20)
        
        # Convert to dict for JSON response
        runs_data = []
        for run in recent_runs:
            run_dict = {
                'run_id': run.run_id,
                'start_time': run.start_time,
                'end_time': run.end_time,
                'status': run.status,
                'analytics_type': run.analytics_type,
                'date_range': run.date_range,
                'files_processed': run.files_processed,
                'records_processed': run.records_processed,
                'sheets_updated': run.sheets_updated,
                'spreadsheet_url': run.spreadsheet_url,
                'total_duration_ms': run.total_duration_ms,
                'log_entries': []
            }
            
            # Add log entries
            for entry in (run.log_entries or [])[-20:]:  # Last 20 entries
                run_dict['log_entries'].append({
                    'timestamp': entry.timestamp,
                    'level': entry.level,
                    'stage': entry.stage,
                    'message': entry.message,
                    'details': entry.details
                })
            
            runs_data.append(run_dict)
        
        return jsonify({
            'success': True,
            'runs': runs_data,
            'current_run': logger.get_current_run().run_id if logger.get_current_run() else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/live-logs')
def get_live_logs():
    """Get live log updates"""
    try:
        since = request.args.get('since')
        logger = get_processing_logger()
        
        live_logs = logger.get_live_logs(since_timestamp=since)
        current_run = logger.get_current_run()
        
        logs_data = []
        for entry in live_logs:
            logs_data.append({
                'timestamp': entry.timestamp,
                'level': entry.level,
                'stage': entry.stage,
                'message': entry.message,
                'details': entry.details
            })
        
        return jsonify({
            'success': True,
            'logs': logs_data,
            'current_run': {
                'run_id': current_run.run_id,
                'status': current_run.status,
                'analytics_type': current_run.analytics_type,
                'start_time': current_run.start_time,
                'records_processed': current_run.records_processed
            } if current_run else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logs')
def logs_page():
    """Render logs page"""
    return render_template('logs.html')

@app.route('/test-ai')
def test_ai():
    """Test AI visibility"""
    return send_file('test_ai_visibility.html')

# AI Assistant / Gemini API Integration

def call_gemini_api(api_key, prompt, system_prompt=None):
    """Call Google Gemini API"""
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        # Build the request body - Gemini uses role-based messages
        contents = []
        
        # If system prompt provided, combine with user prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {prompt}"
        else:
            full_prompt = prompt
        
        contents.append({
            "role": "user",
            "parts": [{"text": full_prompt}]
        })
        
        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
            }
        }
        
        # Add API key to URL
        url += f"?key={api_key}"
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                return "No response generated"
        else:
            return f"API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Error calling Gemini API: {str(e)}"

def get_data_summary(file_paths, data_type):
    """Get a summary of data files for AI context"""
    try:
        summaries = []
        
        for file_path in file_paths:
            full_path = Path('tickets' if data_type == 'tickets' else 'chats') / file_path
            if full_path.exists():
                df = pd.read_csv(full_path, nrows=5)  # Just read first 5 rows for structure
                summary = f"""
File: {file_path}
Rows: {len(df)} (sample)
Columns: {', '.join(df.columns.tolist()[:10])}{'...' if len(df.columns) > 10 else ''}
Sample data: {df.head(2).to_dict('records')}
"""
                summaries.append(summary)
        
        return '\n'.join(summaries)
    except Exception as e:
        return f"Error reading data files: {str(e)}"

@app.route('/api/test-gemini', methods=['POST'])
def test_gemini():
    """Test Gemini API connection"""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        
        if not api_key:
            return jsonify({"status": "error", "message": "API key is required"})
        
        # Simple test prompt
        response = call_gemini_api(api_key, "Hello, please respond with 'Connection successful!'")
        
        if "Connection successful" in response or "successful" in response.lower():
            return jsonify({"status": "success", "message": "API connection working"})
        else:
            return jsonify({"status": "error", "message": f"Unexpected response: {response}"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/conversation-history', methods=['GET'])
def get_conversation_history():
    """Get conversation history for management UI"""
    try:
        from conversation_manager import get_conversation_manager
        
        conv_manager = get_conversation_manager()
        conversations = conv_manager.list_recent_conversations(limit=20)
        stats = conv_manager.get_conversation_stats()
        
        return jsonify({
            "status": "success",
            "conversations": conversations,
            "stats": stats
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    """Handle AI chat messages"""
    try:
        data = request.get_json()
        message = data.get('message')
        api_key = data.get('api_key')
        ticket_files = data.get('ticket_files', [])
        chat_files = data.get('chat_files', [])
        conversation_history = data.get('conversation_history', [])
        
        if not message or not api_key:
            return jsonify({"status": "error", "message": "Message and API key are required"})
        
        # Use Enhanced DuckDB Query Engine with Google Sheets integration
        try:
            from enhanced_query_engine import create_enhanced_query_engine
            from query_engine import format_query_response  # Keep existing formatter
            from conversation_manager import get_conversation_manager
            
            # Get or create conversation ID
            conversation_id = data.get('conversation_id')
            conv_manager = get_conversation_manager()
            
            if not conversation_id:
                conversation_id = conv_manager.create_conversation()
            
            # Create enhanced query engine instance with Google Sheets support
            sheets_credentials = 'service_account_credentials.json' if Path('service_account_credentials.json').exists() else None
            query_engine = create_enhanced_query_engine(api_key, sheets_credentials)
            
            # Restore conversation context from persistent storage
            stored_context = conv_manager.get_conversation_context(conversation_id, limit=5)
            if stored_context:
                query_engine.conversation_context = stored_context
            
            # Execute the natural language query
            result = query_engine.query(message)
            
            # Format the response for chat display
            response = format_query_response(result)
            
            # Save the conversation exchange
            data_insights = result.get('summary', '')
            sql_query = result.get('sql', '')
            conv_manager.add_message(
                conversation_id=conversation_id,
                user_message=message,
                ai_response=response,
                sql_query=sql_query,
                data_insights=data_insights
            )
        
        except Exception as query_error:
            print(f"Query engine failed: {query_error}")
            # Provide helpful fallback
            response = f"""I can analyze your support data using natural language queries! 

Available datasets: tickets, chats

Try asking:
• "What are the average response times?"
• "Which agent handles the most tickets?"
• "Show me ticket volume by month"
• "How many tickets were created in May 2025?"
• "What's the breakdown by ticket owner?"

Error details: {str(query_error)}"""
        
        if response.startswith("Error"):
            return jsonify({"status": "error", "message": response})
        
        return jsonify({
            "status": "success", 
            "response": response,
            "conversation_id": conversation_id if 'conversation_id' in locals() else None
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)