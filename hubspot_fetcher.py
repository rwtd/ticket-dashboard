#!/usr/bin/env python3
"""
HubSpot Tickets API Fetcher
Fetches ticket data from HubSpot CRM API with pagination and incremental sync support
"""

import os
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import time
import pytz

logger = logging.getLogger(__name__)


class HubSpotTicketFetcher:
    """Fetch ticket data from HubSpot CRM API"""

    # Default properties to fetch (matching your CSV columns)
    DEFAULT_PROPERTIES = [
        'subject',
        'hs_pipeline',
        'hs_pipeline_stage',
        'createdate',
        'hs_lastmodifieddate',
        'closed_date',
        'hubspot_owner_id',
        'hs_ticket_priority',
        'hs_ticket_category',
        'source_type',
        'content',
        # Response time metrics (key for your analytics)
        'first_agent_reply_date',  # First agent email response date - used for response time calculation
        'hs_first_agent_message_sent_at',  # First agent response from conversations
        'time_to_close',
        # Additional context
        'hs_object_id',  # Ticket ID
        'hs_created_by_user_id',
        'hs_all_owner_ids',
    ]

    def __init__(self, api_key: str, portal_id: Optional[str] = None):
        """
        Initialize HubSpot fetcher

        Args:
            api_key: HubSpot Private App token
            portal_id: Optional portal ID (usually not needed)
        """
        self.api_key = api_key
        self.portal_id = portal_id
        self.base_url = "https://api.hubapi.com"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

        # Rate limiting (100 requests per 10 seconds for Private Apps)
        self.rate_limit_delay = 0.11  # 110ms between requests (conservative)
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
            url = f"{self.base_url}/crm/v3/objects/tickets"
            params = {'limit': 1}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            logger.info("✅ HubSpot API connection successful")
            return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("❌ HubSpot authentication failed - check API key")
            elif e.response.status_code == 403:
                logger.error("❌ HubSpot access forbidden - check scopes/permissions")
            else:
                logger.error(f"❌ HubSpot API error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ HubSpot connection test failed: {e}")
            return False

    def get_properties_schema(self) -> List[Dict[str, Any]]:
        """
        Fetch available ticket properties schema

        Returns:
            List of property definitions
        """
        try:
            self._rate_limit()
            url = f"{self.base_url}/crm/v3/properties/tickets"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            properties = response.json().get('results', [])
            logger.info(f"📋 Fetched {len(properties)} ticket property definitions")
            return properties

        except Exception as e:
            logger.error(f"Failed to fetch properties schema: {e}")
            return []

    def fetch_tickets(
        self,
        properties: Optional[List[str]] = None,
        since_date: Optional[datetime] = None,
        limit_per_page: int = 100,
        max_tickets: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch tickets from HubSpot with pagination

        Args:
            properties: List of properties to fetch (defaults to DEFAULT_PROPERTIES)
            since_date: Only fetch tickets modified since this date (for incremental sync)
            limit_per_page: Results per page (max 100)
            max_tickets: Maximum total tickets to fetch (None = all)

        Returns:
            DataFrame with ticket data
        """
        if properties is None:
            properties = self.DEFAULT_PROPERTIES

        all_tickets = []
        after = None
        page = 0
        total_fetched = 0

        logger.info(f"🔄 Starting HubSpot ticket fetch...")

        try:
            while True:
                page += 1
                self._rate_limit()

                # Build request
                url = f"{self.base_url}/crm/v3/objects/tickets"
                params = {
                    'limit': limit_per_page,
                    'properties': ','.join(properties),
                    'archived': False  # Only active tickets
                }

                if after:
                    params['after'] = after

                # Make request
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Extract tickets
                tickets = data.get('results', [])

                # Filter by date if requested
                if since_date:
                    filtered_tickets = []
                    for ticket in tickets:
                        modified_str = ticket.get('properties', {}).get('hs_lastmodifieddate')
                        if modified_str:
                            modified_dt = datetime.fromisoformat(modified_str.replace('Z', '+00:00'))
                            if modified_dt >= since_date:
                                filtered_tickets.append(ticket)
                    tickets = filtered_tickets

                all_tickets.extend(tickets)
                total_fetched += len(tickets)

                logger.info(f"📄 Page {page}: Fetched {len(tickets)} tickets (total: {total_fetched})")

                # Check for pagination
                paging = data.get('paging', {})
                after = paging.get('next', {}).get('after')

                # Check limits
                if not after or (max_tickets and total_fetched >= max_tickets):
                    break

            logger.info(f"✅ Successfully fetched {total_fetched} tickets from HubSpot")

            # Convert to DataFrame
            if not all_tickets:
                logger.warning("⚠️  No tickets found")
                return pd.DataFrame()

            # Flatten ticket data
            flattened = []
            for ticket in all_tickets:
                props = ticket.get('properties', {})
                props['ticket_id'] = ticket.get('id')
                props['created_at'] = ticket.get('createdAt')
                props['updated_at'] = ticket.get('updatedAt')
                flattened.append(props)

            df = pd.DataFrame(flattened)

            logger.info(f"📊 Created DataFrame with {len(df)} tickets and {len(df.columns)} columns")
            return df

        except Exception as e:
            logger.error(f"❌ Failed to fetch tickets: {e}")
            raise

    def fetch_owners(self) -> Dict[str, str]:
        """
        Fetch ticket owners (agents) mapping

        Returns:
            Dict mapping owner_id to owner name
        """
        try:
            self._rate_limit()
            url = f"{self.base_url}/crm/v3/owners"
            params = {'limit': 100}

            all_owners = []
            after = None

            while True:
                if after:
                    params['after'] = after

                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                owners = data.get('results', [])
                all_owners.extend(owners)

                after = data.get('paging', {}).get('next', {}).get('after')
                if not after:
                    break

            # Create mapping
            owner_map = {}
            for owner in all_owners:
                owner_id = str(owner.get('id'))
                # Try different name fields
                name = (
                    owner.get('firstName', '') + ' ' + owner.get('lastName', '')
                ).strip() or owner.get('email', '') or owner.get('userId', '')

                if name:
                    owner_map[owner_id] = name

            logger.info(f"👥 Fetched {len(owner_map)} ticket owners")
            return owner_map

        except Exception as e:
            logger.error(f"Failed to fetch owners: {e}")
            return {}

    def fetch_pipelines(self) -> Dict[str, str]:
        """
        Fetch ticket pipelines and return ID to label mapping

        Returns:
            Dict mapping pipeline ID to pipeline label
        """
        try:
            url = f"{self.base_url}/crm/v3/pipelines/tickets"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Create mapping of pipeline ID to label
            pipeline_map = {}
            for pipeline in data.get('results', []):
                pipeline_id = str(pipeline.get('id'))
                pipeline_label = pipeline.get('label', '')
                if pipeline_id and pipeline_label:
                    pipeline_map[pipeline_id] = pipeline_label

            logger.info(f"📊 Fetched {len(pipeline_map)} ticket pipelines")
            return pipeline_map

        except Exception as e:
            logger.error(f"Failed to fetch pipelines: {e}")
            return {}

    def fetch_incremental(
        self,
        last_sync_time: datetime,
        properties: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Fetch only tickets modified since last sync (incremental update)

        Args:
            last_sync_time: Datetime of last successful sync
            properties: Properties to fetch

        Returns:
            DataFrame with new/modified tickets
        """
        logger.info(f"🔄 Incremental sync: fetching tickets modified since {last_sync_time}")
        return self.fetch_tickets(
            properties=properties,
            since_date=last_sync_time
        )


def main():
    """Test the fetcher"""
    logging.basicConfig(level=logging.INFO)

    # Get API key from environment
    api_key = os.environ.get('HUBSPOT_API_KEY')
    if not api_key:
        logger.error("HUBSPOT_API_KEY environment variable not set")
        return

    # Initialize fetcher
    fetcher = HubSpotTicketFetcher(api_key)

    # Test connection
    if not fetcher.test_connection():
        return

    # Fetch sample tickets
    logger.info("\n📥 Fetching last 50 tickets...")
    df = fetcher.fetch_tickets(max_tickets=50)

    if not df.empty:
        logger.info(f"\n📊 Sample Data:")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"\nFirst few tickets:")
        print(df[['ticket_id', 'subject', 'createdate', 'hs_pipeline']].head())

    # Fetch owners
    logger.info("\n👥 Fetching owners...")
    owners = fetcher.fetch_owners()
    logger.info(f"Sample owners: {list(owners.items())[:5]}")


if __name__ == '__main__':
    main()