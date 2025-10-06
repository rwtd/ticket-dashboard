#!/usr/bin/env python3
"""
Admin Interface for Ticket Dashboard
Provides configuration, testing, and sync management
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Simple authentication (use environment variable for password)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')  # Change in production!

def require_auth(f):
    """Decorator to require authentication for admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template('admin/login.html', error='Invalid password')

    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    """Logout admin"""
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@require_auth
def dashboard():
    """Admin dashboard - main page"""
    # Get current configuration
    config = {
        'hubspot_configured': bool(os.environ.get('HUBSPOT_API_KEY')),
        'livechat_configured': bool(os.environ.get('LIVECHAT_PAT')),
        'sheets_configured': bool(os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')),
        'sync_interval': os.environ.get('DATA_SYNC_INTERVAL_HOURS', '4'),
        'retention_days': os.environ.get('DATA_RETENTION_DAYS', '365')
    }

    # Get sync state
    sync_state = _load_sync_state()

    return render_template('admin/dashboard.html', config=config, sync_state=sync_state)

@admin_bp.route('/test-connections', methods=['POST'])
@require_auth
def test_connections():
    """Test API connections"""
    results = {
        'hubspot': {'status': 'not_configured', 'message': ''},
        'livechat': {'status': 'not_configured', 'message': ''},
        'sheets': {'status': 'not_configured', 'message': ''}
    }

    # Test HubSpot
    hubspot_key = os.environ.get('HUBSPOT_API_KEY')
    if hubspot_key:
        try:
            from hubspot_fetcher import HubSpotTicketFetcher
            fetcher = HubSpotTicketFetcher(hubspot_key)
            if fetcher.test_connection():
                owners = fetcher.fetch_owners()
                results['hubspot'] = {
                    'status': 'success',
                    'message': f'Connected! Found {len(owners)} owners/agents'
                }
            else:
                results['hubspot'] = {'status': 'error', 'message': 'Authentication failed'}
        except Exception as e:
            results['hubspot'] = {'status': 'error', 'message': str(e)}

    # Test LiveChat
    livechat_pat = os.environ.get('LIVECHAT_PAT')
    if livechat_pat:
        try:
            from livechat_fetcher import LiveChatFetcher
            if ':' in livechat_pat:
                username, password = livechat_pat.split(':', 1)
                fetcher = LiveChatFetcher(username, password)
            else:
                fetcher = LiveChatFetcher(livechat_pat, '')

            if fetcher.test_connection():
                agents = fetcher.list_agents()
                results['livechat'] = {
                    'status': 'success',
                    'message': f'Connected! Found {len(agents)} agents'
                }
            else:
                results['livechat'] = {'status': 'error', 'message': 'Authentication failed'}
        except Exception as e:
            results['livechat'] = {'status': 'error', 'message': str(e)}

    # Test Google Sheets
    sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
    creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')
    if sheets_id and os.path.exists(creds_path):
        try:
            from google_sheets_exporter import GoogleSheetsExporter
            exporter = GoogleSheetsExporter(creds_path)
            if exporter.authenticate():
                results['sheets'] = {
                    'status': 'success',
                    'message': f'Connected! Spreadsheet ID: {sheets_id[:20]}...'
                }
            else:
                results['sheets'] = {'status': 'error', 'message': 'Authentication failed'}
        except Exception as e:
            results['sheets'] = {'status': 'error', 'message': str(e)}
    elif sheets_id:
        results['sheets'] = {'status': 'error', 'message': f'Credentials file not found: {creds_path}'}

    return jsonify(results)

@admin_bp.route('/trigger-sync', methods=['POST'])
@require_auth
def trigger_sync():
    """Manually trigger a data sync"""
    sync_type = request.json.get('type', 'incremental')  # 'full' or 'incremental'

    try:
        # Import here to avoid circular dependencies
        from data_sync_service import DataSyncService

        # Check if all credentials are configured
        hubspot_key = os.environ.get('HUBSPOT_API_KEY')
        livechat_pat = os.environ.get('LIVECHAT_PAT')
        sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')

        if not all([hubspot_key, livechat_pat, sheets_id]):
            return jsonify({
                'status': 'error',
                'message': 'Missing API credentials. Please configure all services first.'
            }), 400

        # Initialize service
        service = DataSyncService(
            hubspot_api_key=hubspot_key,
            livechat_pat=livechat_pat,
            sheets_spreadsheet_id=sheets_id,
            sheets_credentials_path=creds_path
        )

        # Run sync
        logger.info(f"Admin triggered {sync_type} sync")

        if sync_type == 'full':
            success = service.run_full_sync()
        else:
            success = service.run_incremental_sync()

        if success:
            return jsonify({
                'status': 'success',
                'message': f'{sync_type.capitalize()} sync completed successfully!'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'{sync_type.capitalize()} sync completed with errors. Check logs.'
            }), 500

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Sync failed: {str(e)}'
        }), 500

@admin_bp.route('/sync-logs')
@require_auth
def sync_logs():
    """View sync logs"""
    sync_state = _load_sync_state()

    # Load recent logs from sync_state file
    logs = []
    if sync_state:
        logs.append({
            'timestamp': sync_state.get('last_ticket_sync', 'Never'),
            'type': 'Ticket Sync',
            'status': 'Success'
        })
        logs.append({
            'timestamp': sync_state.get('last_chat_sync', 'Never'),
            'type': 'Chat Sync',
            'status': 'Success'
        })
        logs.append({
            'timestamp': sync_state.get('last_full_sync', 'Never'),
            'type': 'Full Sync',
            'status': 'Success'
        })

    return render_template('admin/sync_logs.html', logs=logs)

@admin_bp.route('/configuration')
@require_auth
def configuration():
    """View and edit configuration"""
    config = {
        'HUBSPOT_API_KEY': _mask_secret(os.environ.get('HUBSPOT_API_KEY', '')),
        'LIVECHAT_PAT': _mask_secret(os.environ.get('LIVECHAT_PAT', '')),
        'GOOGLE_SHEETS_SPREADSHEET_ID': os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID', ''),
        'GOOGLE_SHEETS_CREDENTIALS_PATH': os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json'),
        'DATA_SYNC_INTERVAL_HOURS': os.environ.get('DATA_SYNC_INTERVAL_HOURS', '4'),
        'DATA_RETENTION_DAYS': os.environ.get('DATA_RETENTION_DAYS', '365'),
        'GEMINI_API_KEY': _mask_secret(os.environ.get('GEMINI_API_KEY', ''))
    }

    return render_template('admin/configuration.html', config=config)

@admin_bp.route('/update-config', methods=['POST'])
@require_auth
def update_config():
    """Update configuration (saves to .env file)"""
    try:
        updates = request.json

        # Load or create .env file
        env_file = Path('.env')
        env_vars = {}

        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value

        # Update with new values
        # Empty values from form mean "don't change" (keep existing)
        # Non-empty values replace existing
        for key, value in updates.items():
            if value:  # Only update if value provided
                env_vars[key] = value
                # Also update in current environment for immediate effect
                os.environ[key] = value

        # Write back to .env
        with open(env_file, 'w') as f:
            f.write("# Ticket Dashboard Configuration\n")
            f.write(f"# Updated: {datetime.now().isoformat()}\n\n")
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        logger.info(f"Configuration updated: {list(updates.keys())}")

        return jsonify({
            'status': 'success',
            'message': 'Configuration saved successfully! Changes will take effect immediately for new operations. For some changes, you may need to restart the application.'
        })

    except Exception as e:
        logger.error(f"Failed to save configuration: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to save configuration: {str(e)}'
        }), 500

def _load_sync_state():
    """Load sync state from file"""
    sync_file = Path('sync_state.json')
    if sync_file.exists():
        try:
            with open(sync_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def _mask_secret(value):
    """Mask secret values for display"""
    if not value:
        return ''
    if len(value) < 8:
        return '***'
    return value[:4] + '***' + value[-4:]

@admin_bp.route('/data-status')
@require_auth
def data_status():
    """Get data source status - compare Google Sheets vs local CSVs"""
    try:
        from google_sheets_data_source import GoogleSheetsDataSource
        import pandas as pd
        
        sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')
        
        status = {
            'sheets_configured': bool(sheets_id and Path(creds_path).exists()),
            'sheets': {'tickets': 0, 'chats': 0, 'tickets_date_range': None, 'chats_date_range': None},
            'local': {'tickets': 0, 'chats': 0, 'ticket_files': [], 'chat_files': []},
            'recommendations': []
        }
        
        # Get Google Sheets data
        if status['sheets_configured']:
            try:
                sheets_source = GoogleSheetsDataSource(
                    spreadsheet_id=sheets_id,
                    credentials_path=creds_path
                )
                if sheets_source.authenticate():
                    # Fetch tickets
                    try:
                        sheets_tickets = sheets_source.get_tickets()
                        if sheets_tickets is not None and not sheets_tickets.empty:
                            status['sheets']['tickets'] = len(sheets_tickets)
                            if 'Create date' in sheets_tickets.columns:
                                min_date = sheets_tickets['Create date'].min()
                                max_date = sheets_tickets['Create date'].max()
                                status['sheets']['tickets_date_range'] = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
                    except Exception as e:
                        logger.error(f"Failed to fetch tickets from Google Sheets: {e}")

                    # Fetch chats
                    try:
                        sheets_chats = sheets_source.get_chats()
                        if sheets_chats is not None and not sheets_chats.empty:
                            status['sheets']['chats'] = len(sheets_chats)
                            if 'chat_creation_date_adt' in sheets_chats.columns:
                                # Filter out NaT values before finding min/max
                                valid_dates = sheets_chats['chat_creation_date_adt'].dropna()
                                if not valid_dates.empty:
                                    min_date = valid_dates.min()
                                    max_date = valid_dates.max()
                                    status['sheets']['chats_date_range'] = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
                    except Exception as e:
                        logger.error(f"Failed to fetch chats from Google Sheets: {e}")
            except Exception as e:
                logger.error(f"Failed to authenticate with Google Sheets: {e}")
        
        # Get local CSV data
        tickets_dir = Path('tickets')
        chats_dir = Path('chats')
        
        if tickets_dir.exists():
            for csv_file in tickets_dir.glob('*.csv'):
                try:
                    df = pd.read_csv(csv_file, low_memory=False)
                    status['local']['tickets'] += len(df)
                    status['local']['ticket_files'].append({
                        'name': csv_file.name,
                        'records': len(df)
                    })
                except:
                    pass
        
        if chats_dir.exists():
            for csv_file in chats_dir.glob('*.csv'):
                try:
                    df = pd.read_csv(csv_file, low_memory=False)
                    status['local']['chats'] += len(df)
                    status['local']['chat_files'].append({
                        'name': csv_file.name,
                        'records': len(df)
                    })
                except:
                    pass
        
        # Generate recommendations
        if status['sheets']['tickets'] == 0 and status['local']['tickets'] > 0:
            status['recommendations'].append({
                'type': 'error',
                'message': f"Google Sheets has NO ticket data but {status['local']['tickets']:,} records exist in local CSV files. Run a Full Sync to populate Google Sheets."
            })
        elif status['sheets']['tickets'] < status['local']['tickets'] * 0.5 and status['local']['tickets'] > 0:
            status['recommendations'].append({
                'type': 'warning',
                'message': f"Google Sheets has {status['sheets']['tickets']:,} tickets but local CSV files have {status['local']['tickets']:,}. Consider running a Full Sync to ensure all data is captured."
            })
        
        if status['sheets']['chats'] == 0 and status['local']['chats'] > 0:
            status['recommendations'].append({
                'type': 'error',
                'message': f"Google Sheets has NO chat data but {status['local']['chats']:,} records exist in local CSV files. Run a Full Sync to populate Google Sheets."
            })
        
        if not status['sheets_configured']:
            status['recommendations'].append({
                'type': 'error',
                'message': 'Google Sheets is not configured. Set up credentials in Configuration page to enable automated sync.'
            })
        
        if status['sheets']['tickets'] > 0 or status['sheets']['chats'] > 0:
            if not status['recommendations']:
                status['recommendations'].append({
                    'type': 'success',
                    'message': '✅ Google Sheets data looks good! The system is ready for analytics.'
                })
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Data status check failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
