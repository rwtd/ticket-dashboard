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
            url = f"{self.base_url}/configuration/action/list_agents"

            response = self.session.post(url, json={}, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Create agent mapping
            agent_map = {}
            for agent in data:
                agent_id = agent.get('id')
                name = agent.get('name', '')
                agent_type = agent.get('role', 'agent')  # 'agent' or 'bot'

                if agent_id and name:
                    agent_map[agent_id] = {
                        'name': name,
                        'type': agent_type
                    }

            logger.info(f"👥 Fetched {len(agent_map)} agents")
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
        include_archived: bool = True
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

        parsed_chats = []

        for chat in chats:
            try:
                # Extract basic info
                chat_id = chat.get('id')
                created_at = chat.get('created_at')  # UTC timestamp
                thread = chat.get('thread', {})
                users = chat.get('users', [])
                properties = chat.get('properties', {})

                # Parse agents
                agents = [u for u in users if u.get('type') in ['agent', 'bot']]
                primary_agent_id = agents[0].get('id') if agents else None
                primary_agent = agent_map.get(primary_agent_id, {}).get('name', 'Unknown') if primary_agent_id else None

                # Check for bot
                bot_agent = None
                human_agents = []
                for agent in agents:
                    agent_id = agent.get('id')
                    agent_info = agent_map.get(agent_id, {})
                    agent_name = agent_info.get('name', 'Unknown')

                    if agent_info.get('type') == 'bot' or 'bot' in agent_name.lower() or agent_name in ['Wynn AI', 'Agent Scrape', 'Traject Data Customer Support']:
                        bot_agent = agent_name
                    else:
                        human_agents.append(agent_name)

                # Determine agent type
                agent_type = 'bot' if bot_agent and not human_agents else 'human'

                # Check for transfer (bot to human)
                bot_transfer = 1 if (bot_agent and human_agents) else 0

                # Parse rating
                rating = properties.get('rating', {})
                rating_value = rating.get('score') if isinstance(rating, dict) else None
                rating_comment = rating.get('comment', '') if isinstance(rating, dict) else ''
                has_rating = rating_value is not None

                # Parse other fields
                source = properties.get('source', {}).get('type', 'unknown')
                tags = chat.get('tags', [])

                # Calculate duration (thread start to end)
                thread_events = thread.get('events', [])
                if thread_events:
                    first_event_time = thread_events[0].get('created_at')
                    last_event_time = thread_events[-1].get('created_at')

                    if first_event_time and last_event_time:
                        first_dt = datetime.fromisoformat(first_event_time.replace('Z', '+00:00'))
                        last_dt = datetime.fromisoformat(last_event_time.replace('Z', '+00:00'))
                        duration_seconds = (last_dt - first_dt).total_seconds()
                        duration_minutes = duration_seconds / 60.0
                    else:
                        duration_minutes = 0
                else:
                    duration_minutes = 0

                # Calculate first response time (time to first agent message)
                first_response_time = None
                customer_first_message = None
                agent_first_message = None

                for event in thread_events:
                    if event.get('type') == 'message':
                        author_id = event.get('author_id')
                        author_type = event.get('author_type', '')

                        if author_type == 'customer' and customer_first_message is None:
                            customer_first_message = datetime.fromisoformat(event.get('created_at').replace('Z', '+00:00'))
                        elif author_type in ['agent', 'bot'] and agent_first_message is None:
                            agent_first_message = datetime.fromisoformat(event.get('created_at').replace('Z', '+00:00'))

                        if customer_first_message and agent_first_message:
                            first_response_time = (agent_first_message - customer_first_message).total_seconds()
                            break

                # Build row
                row = {
                    'chat_id': chat_id,
                    'chat_creation_date_utc': created_at,
                    'primary_agent': primary_agent,
                    'display_agent': bot_agent if agent_type == 'bot' else primary_agent,
                    'agent_type': agent_type,
                    'bot_transfer': bot_transfer,
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
            max_chats=max_chats
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