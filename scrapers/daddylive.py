"""
DaddyLive Scraper Module
Working scraper tested against live site - extracts 450+ events
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DaddyLiveScraper:
    """
    Scraper for DaddyLive (daddylivehd.net)
    
    Tested and working - extracts 450+ events from live schedule
    """
    
    # Known category keywords
    CATEGORY_KEYWORDS = {
        'ppv events': 'PPV',
        'tv shows': 'TV Shows',
        'soccer': 'Soccer',
        'football': 'Football',
        'basketball': 'Basketball',
        'tennis': 'Tennis',
        'cricket': 'Cricket',
        'rugby': 'Rugby',
        'motor': 'Motor Sports',
        'motor sports': 'Motor Sports',
        'hockey': 'Hockey',
        'baseball': 'Baseball',
        'golf': 'Golf',
        'boxing': 'Boxing',
        'mma': 'MMA',
        'wrestling': 'Wrestling',
        'horse racing': 'Horse Racing',
        'horse': 'Horse Racing',
    }
    
    def __init__(self, base_url: str = "https://daddylivehd.net"):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        
        # Time pattern: HH:MM format (tested working)
        self.time_pattern = re.compile(r'^(\d{1,2}):(\d{2})$')
        
        # Date pattern
        self.date_pattern = re.compile(
            r'(\w+day)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})'
        )
    
    async def initialize(self):
        """Initialize the HTTP client."""
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    
    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def get_events(self) -> List[Dict]:
        """
        Main method to get all scheduled events.
        Returns list of events with time, title, category, date
        """
        if not self.client:
            await self.initialize()
        
        try:
            html = await self._fetch_schedule_page()
            return self._parse_schedule_html(html)
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    async def _fetch_schedule_page(self) -> str:
        """Fetch the schedule page HTML."""
        url = f"{self.base_url}/en/daddy-live-schedule"
        logger.info(f"Fetching schedule from: {url}")
        
        response = await self.client.get(url)
        response.raise_for_status()
        return response.text
    
    def _parse_schedule_html(self, html: str) -> List[Dict]:
        """
        Parse the schedule HTML to extract events.
        
        Tested pattern: Time in <b>HH:MM</b> followed by title in next <b>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the main content div
        content = soup.find('div', class_='content')
        if not content:
            logger.warning("Could not find content div")
            return []
        
        # Get all bold elements
        bolds = content.find_all('b')
        logger.info(f"Found {len(bolds)} <b> elements")
        
        events = []
        current_category = "Other"
        current_date = None
        
        for i, b in enumerate(bolds):
            text = b.get_text(strip=True)
            
            # Check for date header
            if self.date_pattern.search(text):
                current_date = text
                continue
            
            # Check for time (HH:MM)
            if self.time_pattern.match(text) and i + 1 < len(bolds):
                time_str = text
                next_text = bolds[i + 1].get_text(strip=True)
                
                # Make sure next is not another time
                if not self.time_pattern.match(next_text):
                    # Check if next_text is a category header
                    next_lower = next_text.lower()
                    
                    # Skip category headers
                    is_category = False
                    for cat_key in self.CATEGORY_KEYWORDS:
                        if cat_key in next_lower:
                            current_category = self.CATEGORY_KEYWORDS[cat_key]
                            is_category = True
                            break
                    
                    if not is_category:
                        events.append({
                            'id': f"dl_{len(events)}",
                            'time': time_str,
                            'title': next_text,
                            'category': current_category,
                            'date': current_date,
                        })
                continue
            
            # Check for category headers in standalone elements
            text_lower = text.lower()
            for cat_key, cat_val in self.CATEGORY_KEYWORDS.items():
                if cat_key in text_lower and len(text) < 30:
                    current_category = cat_val
                    break
        
        logger.info(f"Parsed {len(events)} events from schedule")
        return events
    
    def get_channels_from_events(self, events: List[Dict]) -> List[Dict]:
        """Convert events to channel format for Stremio."""
        channels = []
        
        for event in events:
            channel = {
                'id': event['id'],
                'name': event['title'],
                'category': event['category'],
                'source': 'daddylive',
                'time': event.get('time', ''),
                'date': event.get('date', ''),
            }
            channels.append(channel)
        
        return channels


# Convenience function
async def scrape_daddylive() -> List[Dict]:
    """Quick function to scrape DaddyLive events."""
    scraper = DaddyLiveScraper()
    await scraper.initialize()
    try:
        events = await scraper.get_events()
        return scraper.get_channels_from_events(events)
    finally:
        await scraper.close()


# Test script
if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("DaddyLive Scraper Test")
        print("=" * 60)
        
        scraper = DaddyLiveScraper()
        await scraper.initialize()
        
        try:
            events = await scraper.get_events()
            
            # Group by category
            by_cat = {}
            for e in events:
                cat = e['category']
                if cat not in by_cat:
                    by_cat[cat] = []
                by_cat[cat].append(e)
            
            print(f"\n✅ Found {len(events)} total events\n")
            
            for cat, cat_events in sorted(by_cat.items()):
                print(f"\n🏆 {cat} ({len(cat_events)} events):")
                for e in cat_events[:3]:
                    print(f"   [{e['time']}] {e['title']}")
                if len(cat_events) > 3:
                    print(f"   ... and {len(cat_events) - 3} more")
                    
        finally:
            await scraper.close()
    
    asyncio.run(test())
