"""
DaddyLive Scraper Module
Properly structured scraper based on actual HTML analysis
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
    
    Based on HTML analysis:
    - Schedule page: /en/daddy-live-schedule
    - Events are in <div class="content"> with <b> tags for time/title
    - Categories: PPV Events, TV Shows, Soccer, Football, etc.
    """
    
    def __init__(self, base_url: str = "https://daddylivehd.net"):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        
        # Known category keywords from the actual HTML
        self.category_keywords = [
            'ppv events', 'tv shows', 'soccer', 'football', 'basketball',
            'tennis', 'cricket', 'rugby', 'motor', 'hockey', 'baseball',
            'golf', 'boxing', 'mma', 'wrestling', 'horse racing'
        ]
        
        # Time pattern: HH:MM format
        self.time_pattern = re.compile(r'^(\d{1,2}):(\d{2})$')
        
        # Date pattern from schedule
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
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
    
    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def get_schedule_page(self) -> str:
        """Fetch the schedule page HTML."""
        url = f"{self.base_url}/en/daddy-live-schedule"
        logger.info(f"Fetching schedule from: {url}")
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch schedule: {e}")
            raise
    
    def parse_schedule_html(self, html: str) -> List[Dict]:
        """
        Parse the schedule HTML to extract events.
        
        HTML Structure (from actual site):
        <div class="content">
            <h3><b>Thursday 19th Jan 2025 - Schedule Time UK GMT</b></h3>
            <div><b>PPV Events</b></div>
            <div><b>19:45</b></div>
            <div><b>2025 Chilly Willy at Tucson Speedway</b></div>
            <div><b>22:30</b></div>
            <div><b>Lucas Oil Late Model Series 2025</b></div>
            ...
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the main content div
        content = soup.find('div', class_='content')
        if not content:
            logger.warning("Could not find content div")
            return []
        
        events = []
        current_category = None
        current_date = None
        schedule_timezone = "UK GMT"
        
        # Get all bold elements
        bold_elements = content.find_all('b')
        
        for i, b_elem in enumerate(bold_elements):
            text = b_elem.get_text(strip=True)
            
            if not text:
                continue
            
            # Check for date header
            date_match = self.date_pattern.search(text)
            if date_match:
                current_date = text
                # Extract timezone if present
                if 'GMT' in text:
                    schedule_timezone = "UK GMT"
                continue
            
            # Check if this is a time (HH:MM)
            if self.time_pattern.match(text):
                time_str = text
                # The next <b> element should be the event title
                if i + 1 < len(bold_elements):
                    next_text = bold_elements[i + 1].get_text(strip=True)
                    
                    # Make sure next_text is not a time or category
                    if (not self.time_pattern.match(next_text) and 
                        next_text.lower() not in self.category_keywords and
                        not self.date_pattern.search(next_text)):
                        
                        events.append({
                            'time': time_str,
                            'title': next_text,
                            'category': current_category or 'Other',
                            'date': current_date,
                            'timezone': schedule_timezone,
                        })
                continue
            
            # Check if this is a category
            if text.lower() in self.category_keywords:
                current_category = text
                continue
        
        logger.info(f"Parsed {len(events)} events from schedule")
        return events
    
    def categorize_event(self, title: str) -> str:
        """Auto-categorize event based on title keywords."""
        title_lower = title.lower()
        
        # Sports mapping
        sport_keywords = {
            'football': [' vs ', ' v ', 'fc ', 'united', 'city', 'arsenal', 'liverpool', 'chelsea', 'premier league', 'la liga', 'serie a', 'bundesliga'],
            'basketball': ['nba', 'lakers', 'warriors', 'celtics', 'bulls', 'basketball'],
            'soccer': ['soccer', 'a-league', 'premier league'],
            'tennis': ['tennis', 'atp', 'wta', 'open'],
            'cricket': ['cricket', 'ipl', 'test match', 't20'],
            'mma': ['ufc', 'mma', 'bellator', 'fight night'],
            'boxing': ['boxing', 'box', 'fight'],
            'wrestling': ['wwe', 'wrestling', 'raw', 'smackdown', 'aew'],
            'golf': ['golf', 'pga', 'masters'],
            'racing': ['f1', 'formula', 'nascar', 'racing', 'gp'],
            'hockey': ['nhl', 'hockey', 'ice hockey'],
        }
        
        for category, keywords in sport_keywords.items():
            if any(kw in title_lower for kw in keywords):
                return category.title()
        
        return 'Other'
    
    async def get_events(self) -> List[Dict]:
        """Main method to get all scheduled events."""
        if not self.client:
            await self.initialize()
        
        try:
            html = await self.get_schedule_page()
            events = self.parse_schedule_html(html)
            
            # Post-process: auto-categorize if category is missing
            for event in events:
                if event['category'] == 'Other':
                    event['category'] = self.categorize_event(event['title'])
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []
    
    async def get_channels_from_homepage(self) -> List[Dict]:
        """
        Scrape any channel links from the homepage.
        
        From HTML analysis, the homepage has:
        - Navigation links to various pages
        - Download buttons for APKs
        - Links in the footer
        """
        if not self.client:
            await self.initialize()
        
        try:
            response = await self.client.get(self.base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            channels = []
            
            # Look for navigation items that might be channels
            nav = soup.find('nav', class_='navbar')
            if nav:
                for link in nav.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)
                    
                    if text and href and 'schedule' not in href.lower():
                        channels.append({
                            'name': text,
                            'url': urljoin(self.base_url, href),
                            'source': 'daddylive',
                        })
            
            logger.info(f"Found {len(channels)} links from homepage")
            return channels
            
        except Exception as e:
            logger.error(f"Error fetching homepage: {e}")
            return []
    
    async def find_embed_url(self, event_title: str) -> Optional[str]:
        """
        Try to find an embed URL for an event.
        
        Note: This would require additional investigation of how
        DaddyLive links events to their streams.
        """
        # This is a placeholder - actual implementation would need
        # to analyze how events link to stream pages
        logger.warning("find_embed_url not yet implemented")
        return None


# Convenience function for direct use
async def scrape_daddylive_events() -> List[Dict]:
    """Quick function to scrape DaddyLive events."""
    scraper = DaddyLiveScraper()
    await scraper.initialize()
    try:
        return await scraper.get_events()
    finally:
        await scraper.close()


# Test script
if __name__ == "__main__":
    import asyncio
    import json
    
    async def test():
        print("=" * 60)
        print("DaddyLive Scraper Test")
        print("=" * 60)
        
        scraper = DaddyLiveScraper()
        await scraper.initialize()
        
        try:
            # Test schedule parsing
            print("\n📅 Fetching schedule...")
            events = await scraper.get_events()
            
            print(f"\n✅ Found {len(events)} events\n")
            
            # Group by category
            by_category = {}
            for event in events:
                cat = event['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(event)
            
            # Print summary
            for category, cat_events in sorted(by_category.items()):
                print(f"\n🏆 {category} ({len(cat_events)} events):")
                for event in cat_events[:3]:  # Show first 3
                    print(f"   [{event['time']}] {event['title']}")
                if len(cat_events) > 3:
                    print(f"   ... and {len(cat_events) - 3} more")
            
            # Test homepage
            print("\n" + "=" * 60)
            print("🏠 Checking homepage...")
            channels = await scraper.get_channels_from_homepage()
            print(f"\n✅ Found {len(channels)} links:")
            for ch in channels[:5]:
                print(f"   - {ch['name']}: {ch['url']}")
            
        finally:
            await scraper.close()
        
        print("\n" + "=" * 60)
        print("Test complete!")
    
    asyncio.run(test())
