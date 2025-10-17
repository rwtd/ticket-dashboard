#!/usr/bin/env python3
"""
LiveChat Ratings Fetcher
Fetches chat ratings from LiveChat Reports API v3.6
"""

import requests
import logging
from datetime import datetime
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)


class LiveChatRatingsFetcher:
    """Fetch chat ratings from LiveChat Reports API"""

    def __init__(self, username: str, password: str):
        """
        Initialize ratings fetcher
        
        Args:
            username: LiveChat account username (Client ID)
            password: LiveChat account password (API key)
        """
        self.username = username
        self.password = password
        self.base_url = "https://api.livechatinc.com/v3.6/reports"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        
        # Rate limiting
        self.rate_limit_delay = 0.35
        self.last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_ratings(
        self,
        from_date: datetime,
        to_date: Optional[datetime] = None,
        distribution: str = "day"
    ) -> Dict:
        """
        Fetch chat ratings from Reports API
        
        Args:
            from_date: Start date (UTC)
            to_date: End date (UTC), defaults to now
            distribution: Time distribution (day, hour, month, year)
            
        Returns:
            Dict with ratings data
        """
        try:
            self._rate_limit()
            
            if to_date is None:
                to_date = datetime.utcnow()
            
            url = f"{self.base_url}/chats/ratings"
            payload = {
                "distribution": distribution,
                "filters": {
                    "from": from_date.strftime('%Y-%m-%dT%H:%M:%S-00:00'),
                    "to": to_date.strftime('%Y-%m-%dT%H:%M:%S-00:00')
                }
            }
            
            logger.info(f"📊 Fetching ratings from {from_date.date()} to {to_date.date()}")
            
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Fetched ratings report: {data.get('total', 0)} total rated chats")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch ratings: {e}")
            return {}

    def test_connection(self) -> bool:
        """Test Reports API connection"""
        try:
            from datetime import timedelta
            from_date = datetime.utcnow() - timedelta(days=7)
            result = self.fetch_ratings(from_date)
            return 'name' in result
        except Exception as e:
            logger.error(f"❌ Reports API connection test failed: {e}")
            return False


def get_ratings_data(days: int = 30) -> Dict:
    """
    Convenience function to fetch ratings data for the last N days
    
    Args:
        days: Number of days to fetch (default: 30)
        
    Returns:
        Dict with ratings data from Reports API
    """
    import os
    
    # Get credentials
    pat = os.environ.get('LIVECHAT_PAT')
    if not pat:
        logger.warning("LIVECHAT_PAT not set, cannot fetch ratings")
        return {}
    
    if ':' in pat:
        username, password = pat.split(':', 1)
    else:
        username, password = pat, ''
    
    # Initialize fetcher
    fetcher = LiveChatRatingsFetcher(username, password)
    
    # Fetch ratings
    from datetime import timedelta
    from_date = datetime.utcnow() - timedelta(days=days)
    return fetcher.fetch_ratings(from_date)


def main():
    """Test the ratings fetcher"""
    import os
    logging.basicConfig(level=logging.INFO)
    
    # Get credentials
    pat = os.environ.get('LIVECHAT_PAT')
    if not pat:
        logger.error("LIVECHAT_PAT environment variable must be set")
        return
    
    if ':' in pat:
        username, password = pat.split(':', 1)
    else:
        username, password = pat, ''
    
    # Initialize fetcher
    fetcher = LiveChatRatingsFetcher(username, password)
    
    # Test connection
    if not fetcher.test_connection():
        return
    
    # Fetch last 30 days of ratings
    from datetime import timedelta
    from_date = datetime.utcnow() - timedelta(days=30)
    ratings = fetcher.fetch_ratings(from_date)
    
    print(f"\n📊 Ratings Report:")
    print(f"Total rated chats: {ratings.get('total', 0)}")
    print(f"\nSample records:")
    records = ratings.get('records', {})
    for date, data in list(records.items())[:5]:
        print(f"  {date}: {data}")


if __name__ == '__main__':
    main()