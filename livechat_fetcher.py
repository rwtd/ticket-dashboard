#!/usr/bin/env python3
"""
LiveChat API Fetcher
Fetches chat data from LiveChat API v3.5 with pagination and incremental sync support
"""

import os
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time
import pytz

logger = logging.getLogger(__name__)


class LiveChatFetcher:
    """Fetch chat data from LiveChat API v3.5"""

    def __init__(self, username: str, password: str, license_id: Optional[str] = None):
        """
        Initialize LiveChat fetcher

        Args:
            username: LiveChat account username (Client ID)
            password: LiveChat account password (API key)
            license_id: Optional license ID
        """
        self.username = username
        self.password = password
        self.license_id = license_id
        self.base_url = "https://api.livechatinc.com/v3.5"
        self.session = requests.Session()
        # Use Basic Authentication
        self.session.auth = (username, password)
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

        # Rate limiting (180 requests per minute = 1 per 333ms)
        self.rate_limit_delay = 0.35  # 350ms between requests (conservative)
        self.last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def test_connection(self) -> bool:
        """
        Test API connection and authentication

        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.base_url}/agent/action/list_chats"
            payload = {'limit': 1}

            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info("✅ LiveChat API connection successful")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("❌ LiveChat authentication failed - check PAT token")
            elif e.response.status_code == 403:
                logger.error("❌ LiveChat access forbidden - check scopes/permissions")
            else:
                logger.error(f"❌ LiveChat API error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ LiveChat connection test failed: {e}")
            return False

    def list_agents(self) -> Dict[str, str]:
        """
        Fetch list of agents (human and bot)

        Returns:
            Dict mapping agent_id to agent name
        """
        try:
            self._rate_limit()
            
            # Fetch human agents
            url = f"{self.base_url}/configuration/action/list_agents"
            response = self.session.post(url, json={}, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Create agent mapping
            agent_map = {}
            for agent in data:
                agent_id = agent.get('id')
                name = agent.get('name', '')
                agent_type = agent.get('role', 'agent')

                if agent_id and name:
                    agent_map[agent_id] = {
                        'name': name,
                        'type': agent_type
                    }

            # Fetch bots separately
            self._rate_limit()
            url_bots = f"{self.base_url}/configuration/action/list_bots"
            try:
                response_bots = self.session.post(url_bots, json={}, timeout=10)
                response_bots.raise_for_status()
                bots_data = response_bots.json()
                
                for bot in bots_data:
                    bot_id = bot.get('id')
                    bot_name = bot.get('name', '')
                    
                    if bot_id and bot_name:
                        agent_map[bot_id] = {
                            'name': bot_name,
                            'type': 'bot'
                        }
                        
                logger.info(f"👥 Fetched {len(agent_map)} agents ({len(bots_data)} bots)")
            except Exception as bot_error:
                logger.warning(f"Could not fetch bots: {bot_error}")
                logger.info(f"👥 Fetched {len(agent_map)} agents (no bots)")

            return agent_map

        except Exception as e:
            logger.error(f"Failed to fetch agents: {e}")
            return {}

    def fetch_chats(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit_per_page: int = 100,
        max_chats: Optional[int] = None,
        include_archived: bool = True,
        include_details: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch chats from LiveChat with pagination

        Args:
            from_date: Start date for filtering (UTC)
            to_date: End date for filtering (UTC)
            limit_per_page: Results per page (max 100)
            max_chats: Maximum total chats to fetch (None = all)
            include_archived: Include archived (completed) chats

        Returns:
            List of chat dictionaries
        """
        all_chats = []
        page_id = None
        page = 0
        total_fetched = 0

        logger.info(f"🔄 Starting LiveChat fetch...")

        try:
            while True:
                page += 1
                self._rate_limit()

                # Build request payload
                url = f"{self.base_url}/agent/action/list_chats"
                payload = {}

                # First page vs pagination pages
                if not page_id:
                    # First page - can use filters, limit, sort_order
                    payload['limit'] = limit_per_page
                    payload['sort_order'] = 'desc'  # Most recent first

                    filters = {}

                    # Date range filter
                    if from_date or to_date:
                        created_at_filter = {}
                        if from_date:
                            created_at_filter['from'] = from_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                        if to_date:
                            created_at_filter['to'] = to_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                        filters['created_at'] = created_at_filter

                    # Include archived/active chats
                    if include_archived:
                        filters['include_active'] = True

                    if filters:
                        payload['filters'] = filters
                else:
                    # Pagination - ONLY use page_id (cannot combine with filters, limit, or sort_order)
                    payload['page_id'] = page_id

                # Make request
                logger.debug(f"Request payload (page {page}): {payload}")
                response = self.session.post(url, json=payload, timeout=30)

                if response.status_code != 200:
                    logger.error(f"API error on page {page}: {response.status_code} - {response.text[:500]}")

                response.raise_for_status()
                data = response.json()

                # Extract chats (API returns 'chats_summary')
                chats = data.get('chats_summary', [])
                if not chats:
                    logger.warning(f"Page {page} returned no chats")
                    break

                if include_details:
                    detailed_batch = []
                    for summary in chats:
                        chat_id = summary.get('id')
                        needs_detail = (
                            not summary.get('created_at') or
                            'thread' not in summary or
                            not summary.get('thread') or
                            ('threads' not in summary and 'thread' not in summary)
                        )

                        if include_details and chat_id and needs_detail:
                            detail = self.get_chat_details(chat_id)
                            if detail:
                                chat_payload = detail.get('chat') or detail
                                if chat_payload:
                                    chat_payload.setdefault('id', chat_id)
                                    detailed_batch.append(chat_payload)
                                    continue
                                else:
                                    logger.warning(f"Chat detail payload missing 'chat' key for {chat_id}")
                            else:
                                logger.warning(f"Falling back to summary for chat {chat_id}")

                        detailed_batch.append(summary)

                    chats = detailed_batch

                all_chats.extend(chats)
                total_fetched += len(chats)

                logger.info(f"📄 Page {page}: Fetched {len(chats)} chats (total: {total_fetched})")

                # Check for pagination
                page_id = data.get('next_page_id')

                # Check limits
                if not page_id or (max_chats and total_fetched >= max_chats):
                    break

            logger.info(f"✅ Successfully fetched {total_fetched} chats from LiveChat")
            return all_chats

        except Exception as e:
            logger.error(f"❌ Failed to fetch chats: {e}")
            raise

    def get_chat_details(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a specific chat

        Args:
            chat_id: Chat ID

        Returns:
            Chat details dictionary or None
        """
        try:
            self._rate_limit()
            url = f"{self.base_url}/agent/action/get_chat"
            payload = {'chat_id': chat_id}

            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to fetch chat {chat_id}: {e}")
            return None

    def parse_chats_to_dataframe(
        self,
        chats: List[Dict[str, Any]],
        agent_map: Optional[Dict[str, Dict]] = None
    ) -> pd.DataFrame:
        """
        Convert raw chat data to DataFrame format matching your CSV structure

        Args:
            chats: List of chat dictionaries from API
            agent_map: Optional agent mapping from list_agents()

        Returns:
            DataFrame with processed chat data
        """
        if not chats:
            logger.warning("⚠️  No chats to parse")
            return pd.DataFrame()

        if agent_map is None:
            agent_map = self.list_agents()

        # Known bot agent IDs (hardcoded fallback for legacy/unknown bots)
        known_bot_ids = {
            '5626186ef1d50006d82a02372509ec3e': 'Agent Scrape',
            'ce8545b838652bea3889eafd72a6d821': 'Wynn AI',
            '9b96f9b272d4666b95cc74bb8bbd4131': 'Agent Scrape'  # Additional bot instance
        }

        parsed_chats = []

        for chat in chats:
            try:
                # Handle wrapped payloads from get_chat_details
                if isinstance(chat, dict) and 'chat' in chat:
                    chat = chat['chat']

                # Extract basic info
                chat_id = chat.get('id')

                # Threads can appear as single thread or a list
                thread = chat.get('thread')
                if not thread and isinstance(chat.get('threads'), list) and chat['threads']:
                    # Prefer the most recent thread (first in list usually latest)
                    thread = chat['threads'][0]

                created_at = (
                    chat.get('created_at')
                    or chat.get('started_at')
                    or chat.get('last_event_created_at')
                )

                if not created_at and isinstance(thread, dict):
                    created_at = (
                        thread.get('started_at')
                        or thread.get('created_at')
                        or thread.get('last_event_created_at')
                    )

                users = chat.get('users', [])
                properties = chat.get('properties', {})
                if isinstance(properties, dict) and 'items' in properties:
                    # LiveChat API sometimes returns properties as list under 'items'
                    properties = {item.get('name'): item.get('value') for item in properties.get('items', [])}

                # Parse agents
                agents = [u for u in users if u.get('type') in ['agent', 'bot']]
                primary_agent_id = agents[0].get('id') if agents else None
                
                # Try agent_map first, then known_bot_ids fallback
                if primary_agent_id:
                    if primary_agent_id in agent_map:
                        primary_agent = agent_map[primary_agent_id].get('name', 'Unknown')
                    elif primary_agent_id in known_bot_ids:
                        primary_agent = known_bot_ids[primary_agent_id]
                        logger.debug(f"Using hardcoded bot name for ID {primary_agent_id}: {primary_agent}")
                    else:
                        primary_agent = 'Unknown'
                        logger.warning(f"Unknown agent ID: {primary_agent_id}")
                else:
                    primary_agent = None

                # Check for bot
                bot_agent = None
                human_agents = []
                for agent in agents:
                    agent_id = agent.get('id')
                    
                    # Get agent info from map or known bots
                    if agent_id in agent_map:
                        agent_info = agent_map[agent_id]
                        agent_name = agent_info.get('name', 'Unknown')
                        agent_is_bot = agent_info.get('type') == 'bot'
                    elif agent_id in known_bot_ids:
                        agent_name = known_bot_ids[agent_id]
                        agent_is_bot = True
                    else:
                        agent_name = 'Unknown'
                        agent_is_bot = False

                    # Classify as bot or human
                    if agent_is_bot or 'bot' in agent_name.lower() or agent_name in ['Wynn AI', 'Agent Scrape', 'Traject Data Customer Support']:
                        bot_agent = agent_name
                    else:
                        human_agents.append(agent_name)

                # Determine agent type
                agent_type = 'bot' if bot_agent and not human_agents else 'human'

                # Check for transfer (bot to human)
                bot_transfer = 1 if (bot_agent and human_agents) else 0

                # Parse rating
                rating = properties.get('rating', {})
                rating_score = rating.get('score') if isinstance(rating, dict) else None
                rating_comment = rating.get('comment', '') if isinstance(rating, dict) else ''
                
                # Convert numeric score to text format for rate_raw (to match CSV format)
                # LiveChat API returns 1-5 numeric scores, CSV has "rated good"/"rated bad"
                rate_raw = ''
                if rating_score is not None:
                    if rating_score >= 4:  # 4-5 = good
                        rate_raw = 'rated good'
                    elif rating_score <= 2:  # 1-2 = bad
                        rate_raw = 'rated bad'
                    else:  # 3 = neutral (treat as not rated for now)
                        rate_raw = 'not rated'
                else:
                    rate_raw = 'not rated'
                
                # Keep the numeric value too (will be recalculated by ChatDataProcessor)
                rating_value = rating_score
                has_rating = rating_score is not None

                # Parse other fields
                source = properties.get('source', {}).get('type', 'unknown')
                tags = chat.get('tags', [])
                if tags and isinstance(tags[0], dict):
                    tags = [tag.get('name', '') for tag in tags]

                # Calculate duration (thread start to end)
                thread_events = []
                if isinstance(thread, dict):
                    thread_events = thread.get('events', []) or []

                duration_minutes = 0
                if thread_events:
                    first_event_time = thread_events[0].get('created_at')
                    last_event_time = thread_events[-1].get('created_at')

                    if first_event_time and last_event_time:
                        first_dt = datetime.fromisoformat(first_event_time.replace('Z', '+00:00'))
                        last_dt = datetime.fromisoformat(last_event_time.replace('Z', '+00:00'))
                        duration_seconds = max((last_dt - first_dt).total_seconds(), 0)
                        duration_minutes = duration_seconds / 60.0

                if not duration_minutes and isinstance(thread, dict):
                    started_at = thread.get('started_at') or thread.get('created_at')
                    ended_at = thread.get('ended_at') or thread.get('last_event_created_at')
                    if started_at and ended_at:
                        start_dt = datetime.fromisoformat(str(started_at).replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(str(ended_at).replace('Z', '+00:00'))
                        duration_seconds = max((end_dt - start_dt).total_seconds(), 0)
                        duration_minutes = duration_seconds / 60.0

                # Calculate first response time (time to first agent message)
                first_response_time = None
                customer_first_message = None
                agent_first_message = None

                for event in thread_events:
                    if not isinstance(event, dict):
                        continue
                    if event.get('type') == 'message':
                        created_ts = event.get('created_at')
                        if not created_ts:
                            continue
                        created_dt = datetime.fromisoformat(str(created_ts).replace('Z', '+00:00'))
                        author_type = event.get('author_type', '')

                        if author_type == 'customer' and customer_first_message is None:
                            customer_first_message = created_dt
                        elif author_type in ['agent', 'bot'] and agent_first_message is None:
                            agent_first_message = created_dt

                        if customer_first_message and agent_first_message:
                            delta = agent_first_message - customer_first_message
                            first_response_time = max(delta.total_seconds(), 0)
                            break

                # Build row
                row = {
                    'chat_id': chat_id,
                    'chat_creation_date_utc': created_at,
                    'primary_agent': primary_agent,
                    'display_agent': bot_agent if agent_type == 'bot' else primary_agent,
                    'agent_type': agent_type,
                    'bot_transfer': bot_transfer,
                    'rate_raw': rate_raw,  # Add rate_raw for ChatDataProcessor
                    'rating_value': rating_value,
                    'rating_comment': rating_comment,
                    'has_rating': has_rating,
                    'source': source,
                    'tags': ','.join(tags),
                    'duration_minutes': duration_minutes,
                    'first_response_time': first_response_time,  # seconds
                    'human_agents': ','.join(human_agents),
                    'bot_agent': bot_agent or '',
                    'num_agents': len(agents)
                }

                parsed_chats.append(row)

            except Exception as e:
                logger.warning(f"Failed to parse chat {chat.get('id', 'unknown')}: {e}")
                continue

        df = pd.DataFrame(parsed_chats)
        logger.info(f"📊 Parsed {len(df)} chats to DataFrame with {len(df.columns)} columns")

        return df

    def fetch_and_parse(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        max_chats: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Convenience method: fetch chats and convert to DataFrame in one call

        Args:
            from_date: Start date (UTC)
            to_date: End date (UTC)
            max_chats: Maximum chats to fetch

        Returns:
            DataFrame with parsed chat data
        """
        # Fetch agent mapping first
        agent_map = self.list_agents()

        # Fetch chats
        chats = self.fetch_chats(
            from_date=from_date,
            to_date=to_date,
            max_chats=max_chats,
            include_details=True
        )

        # Parse to DataFrame
        return self.parse_chats_to_dataframe(chats, agent_map)

    def fetch_incremental(
        self,
        last_sync_time: datetime
    ) -> pd.DataFrame:
        """
        Fetch only chats created/modified since last sync (incremental update)

        Args:
            last_sync_time: Datetime of last successful sync (UTC)

        Returns:
            DataFrame with new chats
        """
        logger.info(f"🔄 Incremental sync: fetching chats since {last_sync_time}")
        return self.fetch_and_parse(from_date=last_sync_time)


def main():
    """Test the fetcher"""
    logging.basicConfig(level=logging.INFO)

    # Get credentials from environment
    username = os.environ.get('LIVECHAT_USERNAME')
    password = os.environ.get('LIVECHAT_PASSWORD')

    if not username or not password:
        logger.error("LIVECHAT_USERNAME and LIVECHAT_PASSWORD environment variables must be set")
        logger.info("Example: export LIVECHAT_USERNAME='your-client-id'")
        logger.info("Example: export LIVECHAT_PASSWORD='your-api-key'")
        return

    # Initialize fetcher
    fetcher = LiveChatFetcher(username, password)

    # Test connection
    if not fetcher.test_connection():
        return

    # Fetch agents
    logger.info("\n👥 Fetching agents...")
    agents = fetcher.list_agents()
    logger.info(f"Sample agents: {list(agents.items())[:5]}")

    # Fetch last 30 days of chats
    logger.info("\n📥 Fetching last 30 days of chats...")
    from_date = datetime.utcnow() - timedelta(days=30)
    df = fetcher.fetch_and_parse(from_date=from_date, max_chats=50)

    if not df.empty:
        logger.info(f"\n📊 Sample Data:")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"\nFirst few chats:")
        print(df[['chat_id', 'chat_creation_date_utc', 'agent_type', 'display_agent', 'has_rating']].head())


if __name__ == '__main__':
    main()
