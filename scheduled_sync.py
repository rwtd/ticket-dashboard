#!/usr/bin/env python3
"""
Scheduled Sync Endpoint for Cloud Run
Designed to be triggered by Cloud Scheduler every few hours
"""

import os
import sys
import logging
from datetime import datetime
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/sync', methods=['POST', 'GET'])
def run_sync():
    """
    Endpoint triggered by Cloud Scheduler for automated syncs
    Runs incremental sync to keep Firestore current
    """
    try:
        logger.info("🔄 Scheduled sync triggered")
        
        # Get required environment variables
        hubspot_key = os.environ.get('HUBSPOT_API_KEY')
        livechat_pat = os.environ.get('LIVECHAT_PAT')
        
        if not all([hubspot_key, livechat_pat]):
            logger.error("Missing required API credentials")
            return jsonify({
                'status': 'error',
                'message': 'Missing API credentials'
            }), 500
        
        # Import sync service
        from firestore_sync_service import FirestoreSyncService
        
        # Initialize and run incremental sync
        service = FirestoreSyncService(
            hubspot_api_key=hubspot_key,
            livechat_pat=livechat_pat
        )
        
        # Run incremental sync (fast, only new/updated records)
        ticket_count = service.sync_tickets(incremental=True)
        chat_count = service.sync_chats(incremental=True)
        
        logger.info(f"✅ Sync complete: {ticket_count} tickets, {chat_count} chats")
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'tickets_synced': ticket_count,
            'chats_synced': chat_count
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/sync/full', methods=['POST'])
def run_full_sync():
    """
    Endpoint for manual full sync (all data)
    This should be used sparingly (initial setup, data recovery)
    """
    try:
        logger.info("🔄 Full sync triggered")
        
        hubspot_key = os.environ.get('HUBSPOT_API_KEY')
        livechat_pat = os.environ.get('LIVECHAT_PAT')
        
        if not all([hubspot_key, livechat_pat]):
            return jsonify({
                'status': 'error',
                'message': 'Missing API credentials'
            }), 500
        
        from firestore_sync_service import FirestoreSyncService
        
        service = FirestoreSyncService(
            hubspot_api_key=hubspot_key,
            livechat_pat=livechat_pat
        )
        
        # Run full sync (last 365 days)
        success = service.run_full_sync()
        
        if success:
            return jsonify({
                'status': 'success',
                'timestamp': datetime.utcnow().isoformat(),
                'message': 'Full sync completed'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Full sync failed - check logs'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Full sync failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/health')
def health():
    """Health check for Cloud Scheduler"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)