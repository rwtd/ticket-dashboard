#!/usr/bin/env python3
"""
Conversation History Manager for Support Analytics AI
Provides persistent conversation storage and retrieval
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

class ConversationManager:
    """Manages persistent conversation history for AI assistant"""
    
    def __init__(self, storage_path: str = "conversations.jsonl", max_age_days: int = 30):
        """Initialize conversation manager"""
        self.storage_path = Path(storage_path)
        self.max_age_days = max_age_days
        
    def create_conversation(self, user_id: Optional[str] = None) -> str:
        """Create a new conversation and return conversation ID"""
        conversation_id = str(uuid.uuid4())[:8]  # Short ID
        
        conversation = {
            'conversation_id': conversation_id,
            'user_id': user_id or 'anonymous',
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'messages': [],
            'context_summary': '',
            'query_count': 0
        }
        
        self._save_conversation(conversation)
        return conversation_id
    
    def add_message(self, conversation_id: str, user_message: str, ai_response: str, 
                   sql_query: Optional[str] = None, data_insights: Optional[str] = None):
        """Add a message exchange to the conversation"""
        conversation = self._load_conversation(conversation_id)
        
        if not conversation:
            # Create new conversation if doesn't exist
            conversation_id = self.create_conversation()
            conversation = self._load_conversation(conversation_id)
        
        message_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'ai_response': ai_response,
            'sql_query': sql_query,
            'data_insights': data_insights
        }
        
        conversation['messages'].append(message_entry)
        conversation['last_updated'] = datetime.now().isoformat()
        conversation['query_count'] += 1
        
        # Update context summary (keep last 3 exchanges)
        recent_messages = conversation['messages'][-3:]
        context_summary = []
        for msg in recent_messages:
            context_summary.append(f"Q: {msg['user_message'][:100]}...")
            context_summary.append(f"A: {msg['ai_response'][:100]}...")
        
        conversation['context_summary'] = '\n'.join(context_summary)
        
        self._save_conversation(conversation)
        return conversation_id
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get full conversation by ID"""
        return self._load_conversation(conversation_id)
    
    def get_conversation_context(self, conversation_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """Get recent conversation context for AI prompts"""
        conversation = self._load_conversation(conversation_id)
        if not conversation:
            return []
        
        # Return last N message exchanges
        recent_messages = conversation['messages'][-limit:]
        context = []
        
        for msg in recent_messages:
            context.append({
                'question': msg['user_message'],
                'summary': msg['data_insights'] or msg['ai_response'][:200],
                'timestamp': msg['timestamp']
            })
        
        return context
    
    def list_recent_conversations(self, user_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent conversations for a user"""
        conversations = []
        
        if not self.storage_path.exists():
            return conversations
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        conv = json.loads(line.strip())
                        
                        # Filter by user if specified
                        if user_id and conv.get('user_id') != user_id:
                            continue
                        
                        # Create summary for listing
                        summary = {
                            'conversation_id': conv['conversation_id'],
                            'created_at': conv['created_at'],
                            'last_updated': conv['last_updated'],
                            'query_count': conv['query_count'],
                            'preview': conv['messages'][0]['user_message'][:100] + '...' if conv['messages'] else 'Empty conversation'
                        }
                        conversations.append(summary)
            
            # Sort by last updated, most recent first
            conversations.sort(key=lambda x: x['last_updated'], reverse=True)
            return conversations[:limit]
            
        except Exception as e:
            logging.error(f"Error listing conversations: {e}")
            return []
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation (mark as deleted)"""
        conversation = self._load_conversation(conversation_id)
        if not conversation:
            return False
        
        conversation['deleted'] = True
        conversation['deleted_at'] = datetime.now().isoformat()
        self._save_conversation(conversation)
        return True
    
    def cleanup_old_conversations(self):
        """Remove conversations older than max_age_days"""
        if not self.storage_path.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
        cutoff_iso = cutoff_date.isoformat()
        
        try:
            # Read all conversations
            active_conversations = []
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        conv = json.loads(line.strip())
                        # Keep if not deleted and within age limit
                        if not conv.get('deleted', False) and conv['last_updated'] > cutoff_iso:
                            active_conversations.append(conv)
            
            # Rewrite file with only active conversations
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                for conv in active_conversations:
                    json.dump(conv, f, ensure_ascii=False)
                    f.write('\n')
                    
            logging.info(f"Cleaned up conversations, kept {len(active_conversations)}")
            
        except Exception as e:
            logging.error(f"Error cleaning up conversations: {e}")
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get statistics about conversations"""
        stats = {
            'total_conversations': 0,
            'active_conversations': 0,
            'total_queries': 0,
            'recent_activity': []
        }
        
        if not self.storage_path.exists():
            return stats
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        conv = json.loads(line.strip())
                        stats['total_conversations'] += 1
                        stats['total_queries'] += conv.get('query_count', 0)
                        
                        if not conv.get('deleted', False):
                            stats['active_conversations'] += 1
                            
                        # Recent activity (last 7 days)
                        last_updated = datetime.fromisoformat(conv['last_updated'])
                        if (datetime.now() - last_updated).days <= 7:
                            stats['recent_activity'].append({
                                'conversation_id': conv['conversation_id'],
                                'last_updated': conv['last_updated'],
                                'query_count': conv.get('query_count', 0)
                            })
            
        except Exception as e:
            logging.error(f"Error getting conversation stats: {e}")
        
        return stats
    
    def _load_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific conversation from storage"""
        if not self.storage_path.exists():
            return None
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        conv = json.loads(line.strip())
                        if conv['conversation_id'] == conversation_id and not conv.get('deleted', False):
                            return conv
        except Exception as e:
            logging.error(f"Error loading conversation {conversation_id}: {e}")
        
        return None
    
    def _save_conversation(self, conversation: Dict[str, Any]):
        """Save conversation to storage (append new or update existing)"""
        try:
            conversation_id = conversation['conversation_id']
            
            # Read all existing conversations
            conversations = []
            if self.storage_path.exists():
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            existing_conv = json.loads(line.strip())
                            # Skip the conversation we're updating
                            if existing_conv['conversation_id'] != conversation_id:
                                conversations.append(existing_conv)
            
            # Add the updated conversation
            conversations.append(conversation)
            
            # Write all conversations back to file
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                for conv in conversations:
                    json.dump(conv, f, ensure_ascii=False)
                    f.write('\n')
                
        except Exception as e:
            logging.error(f"Error saving conversation: {e}")

# Global conversation manager instance
conversation_manager = ConversationManager()

def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance"""
    return conversation_manager