"""
DaddyLive Scraper Module
Updated for dlstreams.top - extracts live sports events
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
    Scraper for DaddyLive (dlhd.link / dlhd.dad)
    
    Official domains that redirect to current working site.
    Tested and working - extracts 300+ events from live schedule.
    
    Note: DaddyLive changes domains frequently to avoid blocks.
    Current working domain redirects from dlhd.link -> dlstreams.top
    """
    
    # Category mapping for normalization
    CATEGORY_MAP = {
        'ppv': 'PPV',
        'soccer': 'Soccer',
        'football': 'Football',
        'basketball': 'Basketball',
        'nba': 'Basketball',
        'tennis': 'Tennis',
        'cricket': 'Cricket',
        'rugby': 'Rugby',
        'motor': 'Motor Sports',
        'motorsport': 'Motor Sports',
        'hockey': 'Hockey',
        'ice hockey': 'Hockey',
        'nhl': 'Hockey',
        'baseball': 'Baseball',
        'golf': 'Golf',
        'boxing': 'Boxing',
        'mma': 'MMA',
        'ufc': 'MMA',
        'wrestling': 'MMA',
        'horse': 'Horse Racing',
        'darts': 'Darts',
        'snooker': 'Snooker',
        'cycling': 'Cycling',
        'ski': 'Winter Sports',
        'winter': 'Winter Sports',
        'biathlon': 'Winter Sports',
        'upcoming': 'PPV',
    }
    
    # Official DaddyLive domains with fallbacks
    OFFICIAL_DOMAINS = [
        "https://dlstreams.top",  # Direct to current working domain
        "https://dlhd.link",
        "https://dlhd.dad",
    ]
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        self.resolved_base_url = None
    
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
        Returns list of events with title, category, link
        """
        if not self.client:
            await self.initialize()
        
        # Try each domain in order
        for domain in self.OFFICIAL_DOMAINS:
            try:
                logger.info(f"Trying domain: {domain}")
                html = await self._fetch_schedule_page(domain)
                events = self._parse_schedule_html(html)
                if events:
                    logger.info(f"Successfully fetched {len(events)} events from {domain}")
                    return events
            except Exception as e:
                logger.warning(f"Failed to fetch from {domain}: {e}")
                continue
        
        logger.error("All DaddyLive domains failed")
        return []
    
    async def _fetch_schedule_page(self, url: str) -> str:
        """Fetch the schedule page HTML."""
        logger.info(f"Fetching schedule from: {url}")
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        # Store the resolved URL after redirect
        self.resolved_base_url = str(response.url).rstrip('/')
        if self.resolved_base_url != url:
            logger.info(f"Redirected to: {self.resolved_base_url}")
        
        return response.text
    
    def _normalize_category(self, cat_name: str) -> str:
        """Normalize category name to standard format."""
        cat_lower = cat_name.lower()
        
        for key, value in self.CATEGORY_MAP.items():
            if key in cat_lower:
                return value
        
        return "Other"
    
    def _parse_schedule_html(self, html: str) -> List[Dict]:
        """
        Parse the schedule HTML to extract events.
        
        New structure:
        - div.schedule contains all events
        - div.schedule__category contains each category
        - div.schedule__catHeader has category name
        - div.schedule__channels has links to streams
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the schedule container
        schedule = soup.find('div', class_='schedule')
        if not schedule:
            logger.warning("Could not find schedule div")
            return []
        
        events = []
        event_id = 0
        
        # Find all categories
        categories = schedule.find_all('div', class_='schedule__category')
        logger.info(f"Found {len(categories)} categories")
        
        for cat in categories:
            # Get category name from header
            header = cat.find('div', class_='schedule__catHeader')
            cat_name = header.get_text(strip=True) if header else 'Other'
            normalized_cat = self._normalize_category(cat_name)
            
            # Find all channel links
            channels_div = cat.find('div', class_='schedule__channels')
            if channels_div:
                links = channels_div.find_all('a', href=True)
                
                for link in links:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # Extract watch ID from href like /watch.php?id=123
                    watch_id = ''
                    if 'id=' in href:
                        watch_id = href.split('id=')[-1].split('&')[0]
                    
                    # Parse time from title if present (format: "12:30 Event Name")
                    time_str = ''
                    clean_title = title
                    
                    time_match = re.match(r'^(\d{1,2}:\d{2})\s+', title)
                    if time_match:
                        time_str = time_match.group(1)
                        clean_title = title[time_match.end():]
                    
                    if title and watch_id:
                        # Use resolved URL for embed (the actual working domain)
                        base = self.resolved_base_url or self.base_url or "https://dlstreams.top"
                        events.append({
                            'id': f"dl_{watch_id}",
                            'watch_id': watch_id,
                            'title': clean_title or title,
                            'category': normalized_cat,
                            'original_category': cat_name,
                            'time': time_str,
                            'link': href,
                            'embed_url': f"{base}/watch.php?id={watch_id}",
                        })
                        event_id += 1
        
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
                'original_category': event.get('original_category', ''),
                'embed_url': event.get('embed_url', ''),
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
        print("DaddyLive Scraper Test (dlstreams.top)")
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
                    time_str = f"[{e['time']}] " if e['time'] else ""
                    print(f"   {time_str}{e['title'][:50]} (id={e['watch_id']})")
                if len(cat_events) > 3:
                    print(f"   ... and {len(cat_events) - 3} more")
                    
        finally:
            await scraper.close()
    
    asyncio.run(test())
