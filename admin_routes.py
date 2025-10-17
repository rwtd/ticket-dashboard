#!/usr/bin/env python3
"""
Admin Interface for Ticket Dashboard
Provides configuration, testing, and sync management
Refactored for Firestore architecture (Oct 2025)
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, Response
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
# Note: Admin routes will be disabled if ADMIN_PASSWORD is not set
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
ADMIN_ENABLED = bool(ADMIN_PASSWORD)

if not ADMIN_ENABLED:
    logger.warning("ADMIN_PASSWORD not set - admin interface will be disabled")

def require_auth(f):
    """Decorator to require authentication for admin routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== AUTHENTICATION ====================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if not ADMIN_ENABLED:
        return "Admin interface is disabled. Set ADMIN_PASSWORD environment variable to enable.", 503
    
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

# ==================== DASHBOARD ====================

@admin_bp.route('/')
@require_auth
def dashboard():
    """Admin dashboard - main page"""
    # Get current configuration
    config = {
        'hubspot_configured': bool(os.environ.get('HUBSPOT_API_KEY')),
        'livechat_configured': bool(os.environ.get('LIVECHAT_PAT')),
        'sheets_configured': bool(os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')),  # Keep for template compatibility
        'firestore_configured': True,  # We're using Firestore now
        'sheets_export_id': os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID', ''),
        'sync_interval': int(os.environ.get('DATA_SYNC_INTERVAL_HOURS', 4)),
        'retention_days': int(os.environ.get('DATA_RETENTION_DAYS', 365))
    }

    # Get sync state
    sync_state = _load_sync_state()

    return render_template('admin/dashboard.html',
                         config=config,
                         sync_state=sync_state)

# ==================== TESTING & CONNECTION ====================

@admin_bp.route('/test-connections', methods=['POST'])
@require_auth
def test_connections():
    """Test API connections and database"""
    results = {
        'hubspot': {'status': 'not_configured', 'message': ''},
        'livechat': {'status': 'not_configured', 'message': ''},
        'firestore': {'status': 'not_configured', 'message': ''},
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

    # Test Firestore
    try:
        from firestore_db import get_database
        db = get_database()
        tickets_df = db.get_tickets()
        chats_df = db.get_chats()
        
        tickets_count = len(tickets_df) if tickets_df is not None else 0
        chats_count = len(chats_df) if chats_df is not None else 0
        
        results['firestore'] = {
            'status': 'success',
            'message': f'Connected! {tickets_count:,} tickets, {chats_count:,} chats'
        }
    except Exception as e:
        results['firestore'] = {'status': 'error', 'message': str(e)}

    # Test Google Sheets Export
    sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
    creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')
    if sheets_id and os.path.exists(creds_path):
        try:
            from export_firestore_to_sheets import FirestoreToSheetsExporter
            exporter = FirestoreToSheetsExporter(sheets_id, creds_path)
            if exporter.authenticate():
                results['sheets'] = {
                    'status': 'success',
                    'message': f'Export ready! Spreadsheet ID: {sheets_id[:20]}...'
                }
            else:
                results['sheets'] = {'status': 'error', 'message': 'Authentication failed'}
        except Exception as e:
            results['sheets'] = {'status': 'error', 'message': str(e)}
    elif sheets_id:
        results['sheets'] = {'status': 'error', 'message': f'Credentials file not found: {creds_path}'}

    return jsonify(results)

# ==================== SYNC OPERATIONS ====================

@admin_bp.route('/trigger-sync', methods=['POST'])
@require_auth
def trigger_sync():
    """Manually trigger a data sync from APIs to Firestore"""
    sync_type = request.json.get('type', 'incremental')  # 'full' or 'incremental'

    try:
        from firestore_sync_service import FirestoreSyncService
        import threading

        # Check if all credentials are configured
        hubspot_key = os.environ.get('HUBSPOT_API_KEY')
        livechat_pat = os.environ.get('LIVECHAT_PAT')

        if not all([hubspot_key, livechat_pat]):
            return jsonify({
                'status': 'error',
                'message': 'Missing API credentials. Please configure HubSpot and LiveChat.'
            }), 400

        if sync_type == 'full':
            logger.info("Admin triggered full sync from APIs")
            
            # Run sync in background thread to avoid timeout
            def run_sync_background():
                try:
                    service = FirestoreSyncService(hubspot_key, livechat_pat)
                    service.run_full_sync()
                    logger.info("Background full sync completed successfully")
                except Exception as e:
                    logger.error(f"Background sync failed: {e}", exc_info=True)
            
            sync_thread = threading.Thread(target=run_sync_background, daemon=True)
            sync_thread.start()
            
            return jsonify({
                'status': 'success',
                'message': 'Full sync started in background (5-10 minutes). Check logs for progress.'
            })
        else:
            # Incremental sync - run synchronously (should be fast)
            service = FirestoreSyncService(hubspot_key, livechat_pat)
            logger.info("Admin triggered incremental sync")
            service.run_incremental_sync()

            return jsonify({
                'status': 'success',
                'message': 'Incremental sync completed successfully!'
            })

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Sync failed: {str(e)}'
        }), 500

@admin_bp.route('/trigger-sheets-export', methods=['POST'])
@require_auth
def trigger_sheets_export():
    """Manually trigger export from Firestore to Google Sheets"""
    try:
        from export_firestore_to_sheets import FirestoreToSheetsExporter
        import threading

        sheets_id = os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID')
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json')

        if not sheets_id:
            return jsonify({
                'status': 'error',
                'message': 'Google Sheets not configured. Set GOOGLE_SHEETS_SPREADSHEET_ID.'
            }), 400

        logger.info("Admin triggered Firestore to Sheets export")
        
        # Run export in background
        def run_export_background():
            try:
                exporter = FirestoreToSheetsExporter(sheets_id, creds_path)
                result = exporter.run_export()
                if result['success']:
                    logger.info(f"Export completed: {result['tickets_count']} tickets, {result['chats_count']} chats")
                else:
                    logger.error(f"Export failed: {result.get('error')}")
            except Exception as e:
                logger.error(f"Export background task failed: {e}", exc_info=True)
        
        export_thread = threading.Thread(target=run_export_background, daemon=True)
        export_thread.start()

        return jsonify({
            'status': 'success',
            'message': 'Export started in background. Check logs for progress.'
        })

    except Exception as e:
        logger.error(f"Export trigger failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Export failed: {str(e)}'
        }), 500

# ==================== DATA STATUS ====================

@admin_bp.route('/data-status')
@require_auth
def data_status():
    """Get database status - Firestore vs local CSVs"""
    try:
        import pandas as pd
        
        status = {
            'firestore': {'tickets': 0, 'chats': 0},
            'local': {'tickets': 0, 'chats': 0, 'ticket_files': [], 'chat_files': []},
            'recommendations': []
        }
        
        # Get Firestore data
        try:
            from firestore_db import get_database
            db = get_database()
            
            tickets_df = db.get_tickets()
            if tickets_df is not None and not tickets_df.empty:
                status['firestore']['tickets'] = len(tickets_df)
            
            chats_df = db.get_chats()
            if chats_df is not None and not chats_df.empty:
                status['firestore']['chats'] = len(chats_df)
        except Exception as e:
            logger.error(f"Failed to fetch from Firestore: {e}")
        
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
        if status['firestore']['tickets'] > 0 and status['firestore']['chats'] > 0:
            status['recommendations'].append({
                'type': 'success',
                'message': '✅ Firestore data looks good! Ready for analytics.'
            })
        else:
            status['recommendations'].append({
                'type': 'warning',
                'message': '⚠️ Firestore appears empty. Run a Full Sync to populate it.'
            })
        
        if status['local']['tickets'] > 0 or status['local']['chats'] > 0:
            status['recommendations'].append({
                'type': 'info',
                'message': f"📁 Local CSV backup: {status['local']['tickets']:,} tickets, {status['local']['chats']:,} chats"
            })
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Data status check failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ==================== CONFIGURATION ====================

@admin_bp.route('/configuration')
@require_auth
def configuration():
    """View and edit configuration"""
    config = {
        'HUBSPOT_API_KEY': _mask_secret(os.environ.get('HUBSPOT_API_KEY', '')),
        'LIVECHAT_PAT': _mask_secret(os.environ.get('LIVECHAT_PAT', '')),
        'GOOGLE_SHEETS_SPREADSHEET_ID': os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID', ''),
        'GOOGLE_SHEETS_CREDENTIALS_PATH': os.environ.get('GOOGLE_SHEETS_CREDENTIALS_PATH', 'service_account_credentials.json'),
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
        for key, value in updates.items():
            if value:  # Only update if value provided
                env_vars[key] = value
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
            'message': 'Configuration saved successfully!'
        })

    except Exception as e:
        logger.error(f"Failed to save configuration: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to save configuration: {str(e)}'
        }), 500

# ==================== FILE MANAGEMENT ====================

@admin_bp.route('/upload-csv', methods=['POST'])
@require_auth
def upload_csv():
    """Handle CSV file upload for tickets or chats (backup/fallback)"""
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file provided'}), 400
        
        file = request.files['file']
        file_type = request.form.get('file_type', 'tickets')

        if file.filename == '' or not file.filename.lower().endswith('.csv'):
            return jsonify({'status': 'error', 'message': 'Only CSV files are allowed'}), 400
        
        # Secure filename and add timestamp
        from werkzeug.utils import secure_filename
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{original_filename}"
        
        # Determine upload directory
        if file_type == 'tickets':
            upload_dir = Path('tickets')
        elif file_type == 'chats':
            upload_dir = Path('chats')
        else:
            return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400
        
        upload_dir.mkdir(exist_ok=True)
        
        # Save and validate
        file_path = upload_dir / filename
        file.save(str(file_path))
        
        try:
            import pandas as pd
            df = pd.read_csv(file_path)
            record_count = len(df)
            
            logger.info(f"Uploaded {file_type} CSV: {filename} ({record_count} records)")
            
            return jsonify({
                'status': 'success',
                'message': f'File uploaded: {record_count} records detected.',
                'filename': filename,
                'records': record_count
            })
        except Exception as e:
            file_path.unlink()
            return jsonify({
                'status': 'error',
                'message': f'Invalid CSV file: {str(e)}'
            }), 400
            
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }), 500

@admin_bp.route('/list-uploaded-files')
@require_auth
def list_uploaded_files():
    """List all uploaded CSV files"""
    try:
        import pandas as pd
        files = {'tickets': [], 'chats': []}
        
        for file_type, directory in [('tickets', Path('tickets')), ('chats', Path('chats'))]:
            if directory.exists():
                for csv_file in sorted(directory.glob('*.csv'), reverse=True):
                    try:
                        df = pd.read_csv(csv_file, low_memory=False)
                        files[file_type].append({
                            'name': csv_file.name,
                            'size': csv_file.stat().st_size,
                            'modified': datetime.fromtimestamp(csv_file.stat().st_mtime).isoformat(),
                            'records': len(df)
                        })
                    except:
                        files[file_type].append({
                            'name': csv_file.name,
                            'size': csv_file.stat().st_size,
                            'modified': datetime.fromtimestamp(csv_file.stat().st_mtime).isoformat(),
                            'records': 0
                        })
        
        return jsonify(files)
        
    except Exception as e:
        logger.error(f"Failed to list files: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/delete-uploaded-file', methods=['POST'])
@require_auth
def delete_uploaded_file():
    """Delete an uploaded CSV file"""
    try:
        data = request.json
        filename = data.get('filename')
        file_type = data.get('file_type')
        
        if not filename or not file_type:
            return jsonify({'status': 'error', 'message': 'Missing filename or file_type'}), 400
        
        # Determine directory
        if file_type == 'tickets':
            file_path = Path('tickets') / filename
        elif file_type == 'chats':
            file_path = Path('chats') / filename
        else:
            return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400
        
        # Security check
        if not file_path.exists() or not file_path.is_file():
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        
        file_path.unlink()
        logger.info(f"Deleted {file_type} file: {filename}")
        
        return jsonify({
            'status': 'success',
            'message': f'File deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"File deletion failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Deletion failed: {str(e)}'
        }), 500

# ==================== FIRESTORE LOGS ====================

@admin_bp.route('/logs/recent')
@require_auth
def get_recent_logs():
    """Get recent logs from Firestore"""
    try:
        from firestore_logger import FirestoreLogger
        firestore_logger = FirestoreLogger()
        
        # Get logs from last 24 hours
        logs = firestore_logger.get_recent_logs(hours=24, limit=500)
        
        return jsonify({
            'status': 'success',
            'logs': logs,
            'count': len(logs)
        })
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_bp.route('/logs/clear-old', methods=['POST'])
@require_auth
def clear_old_logs():
    """Clear logs older than retention period"""
    try:
        from firestore_logger import FirestoreLogger
        firestore_logger = FirestoreLogger()
        
        deleted_count = firestore_logger.cleanup_old_logs(days=7)
        
        return jsonify({
            'status': 'success',
            'message': f'Deleted {deleted_count} old log entries',
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.error(f"Failed to clear logs: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ==================== HELPER FUNCTIONS ====================

def _mask_secret(value):
    """Mask secret values for display"""
    if not value:
        return ''
    if len(value) < 8:
        return '***'
    return value[:4] + '***' + value[-4:]

def _load_sync_state():
    """Load sync state from file"""
    try:
        sync_state_file = Path('sync_state.json')
        if sync_state_file.exists():
            with open(sync_state_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load sync state: {e}")
    
    return {
        'last_ticket_sync': None,
        'last_chat_sync': None,
        'last_full_sync': None
    }
