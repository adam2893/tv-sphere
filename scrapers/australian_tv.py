"""
Australian TV Scraper Module
Scrapes Australian free-to-air TV channels

Note: Most Australian streaming services (ABC iView, SBS, 9Now, 7plus, 10Play)
require geolocation in Australia. The scrapers here work with public APIs
where available, but actual streaming may require VPN/Australian IP.
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


class FreeviewScraper:
    """
    Scraper for Freeview Australia channel guide.
    Freeview aggregates all Australian free-to-air channels.
    
    URL: https://freeview.com.au
    """
    
    def __init__(self, base_url: str = "https://freeview.com.au"):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
        
        # Major Australian channels with their stream URLs where available
        self.channels = [
            {'id': 'aus_abc_main', 'name': 'ABC', 'network': 'ABC', 'category': 'Australian General', 'stream_url': None},
            {'id': 'aus_abc-news', 'name': 'ABC News', 'network': 'ABC', 'category': 'Australian News', 'stream_url': None},
            {'id': 'aus_abc-comedy', 'name': 'ABC Comedy', 'network': 'ABC', 'category': 'Australian Comedy', 'stream_url': None},
            {'id': 'aus_abc-kids', 'name': 'ABC Kids', 'network': 'ABC', 'category': 'Australian Kids', 'stream_url': None},
            {'id': 'aus_sbs', 'name': 'SBS', 'network': 'SBS', 'category': 'Australian General', 'stream_url': None},
            {'id': 'aus_sbs-viceland', 'name': 'SBS Viceland', 'network': 'SBS', 'category': 'Australian Entertainment', 'stream_url': None},
            {'id': 'aus_sbs-food', 'name': 'SBS Food', 'network': 'SBS', 'category': 'Australian Lifestyle', 'stream_url': None},
            {'id': 'aus_sbs-world-movies', 'name': 'SBS World Movies', 'network': 'SBS', 'category': 'Australian Movies', 'stream_url': None},
            {'id': 'aus_nitv', 'name': 'NITV', 'network': 'SBS', 'category': 'Australian Indigenous', 'stream_url': None},
            {'id': 'aus_seven', 'name': 'Channel 7', 'network': 'Seven', 'category': 'Australian General', 'stream_url': None},
            {'id': 'aus_7mate', 'name': '7mate', 'network': 'Seven', 'category': 'Australian Entertainment', 'stream_url': None},
            {'id': 'aus_7two', 'name': '7two', 'network': 'Seven', 'category': 'Australian Entertainment', 'stream_url': None},
            {'id': 'aus_7flix', 'name': '7flix', 'network': 'Seven', 'category': 'Australian Movies', 'stream_url': None},
            {'id': 'aus_nine', 'name': 'Channel 9', 'network': 'Nine', 'category': 'Australian General', 'stream_url': None},
            {'id': 'aus_9go', 'name': '9Go!', 'network': 'Nine', 'category': 'Australian Entertainment', 'stream_url': None},
            {'id': 'aus_9gem', 'name': '9Gem', 'network': 'Nine', 'category': 'Australian Entertainment', 'stream_url': None},
            {'id': 'aus_9life', 'name': '9Life', 'network': 'Nine', 'category': 'Australian Lifestyle', 'stream_url': None},
            {'id': 'aus_ten', 'name': 'Channel 10', 'network': 'Ten', 'category': 'Australian General', 'stream_url': None},
            {'id': 'aus_10-bold', 'name': '10 Bold', 'network': 'Ten', 'category': 'Australian Entertainment', 'stream_url': None},
            {'id': 'aus_10-peach', 'name': '10 Peach', 'network': 'Ten', 'category': 'Australian Entertainment', 'stream_url': None},
        ]
    
    async def initialize(self):
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
    
    async def close(self):
        if self.client:
            await self.client.aclose()
    
    async def get_channels(self) -> List[Dict]:
        """Get list of Australian channels."""
        channels = []
        
        for ch in self.channels:
            channels.append({
                'id': ch['id'],
                'name': ch['name'],
                'category': ch['category'],
                'source': 'freeview',
                'network': ch['network'],
                'stream_url': ch.get('stream_url'),
                'embed_url': None,  # No embed URL for these
            })
        
        return channels


class ABCiViewScraper:
    """
    Scraper for ABC iView (Australia's public broadcaster).
    
    URL: https://iview.abc.net.au
    
    Note: ABC iView is geo-restricted to Australia.
    Some content APIs may be publicly accessible.
    """
    
    API_BASE = "https://iview.abc.net.au/api"
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
        )
    
    async def close(self):
        if self.client:
            await self.client.aclose()
    
    async def get_live_channels(self) -> List[Dict]:
        """Get ABC live channels."""
        channels = []
        
        try:
            # ABC iView has a public API for channel list
            response = await self.client.get(f"{self.API_BASE}/channels")
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle both list and dict responses
                if isinstance(data, list):
                    channel_list = data
                elif isinstance(data, dict) and 'channels' in data:
                    channel_list = data['channels']
                else:
                    channel_list = []
                
                for channel in channel_list:
                    if isinstance(channel, dict):
                        channels.append({
                            'id': f"aus_abc_{channel.get('id', channel.get('slug', ''))}",
                            'name': f"ABC {channel.get('title', channel.get('name', 'Channel'))}",
                            'category': 'Australian General',
                            'source': 'abc-iview',
                            'stream_url': channel.get('liveStreamURL') or channel.get('stream_url'),
                            'embed_url': None,
                        })
            
            if not channels:
                # Fallback to known channels
                channels = [
                    {'id': 'aus_abc_main', 'name': 'ABC', 'category': 'Australian General', 'source': 'abc-iview', 'stream_url': None, 'embed_url': None},
                    {'id': 'aus_abc_news', 'name': 'ABC News', 'category': 'Australian News', 'source': 'abc-iview', 'stream_url': None, 'embed_url': None},
                    {'id': 'aus_abc_comedy', 'name': 'ABC Comedy', 'category': 'Australian Comedy', 'source': 'abc-iview', 'stream_url': None, 'embed_url': None},
                    {'id': 'aus_abc_kids', 'name': 'ABC Kids', 'category': 'Australian Kids', 'source': 'abc-iview', 'stream_url': None, 'embed_url': None},
                ]
                
        except Exception as e:
            logger.error(f"Error fetching ABC channels: {e}")
            # Return known channels as fallback
            channels = [
                {'id': 'aus_abc_main', 'name': 'ABC', 'category': 'Australian General', 'source': 'abc-iview', 'stream_url': None, 'embed_url': None},
                {'id': 'aus_abc_news', 'name': 'ABC News', 'category': 'Australian News', 'source': 'abc-iview', 'stream_url': None, 'embed_url': None},
            ]
        
        return channels


class SBSOnDemandScraper:
    """
    Scraper for SBS On Demand.
    
    URL: https://www.sbs.com.au/ondemand
    
    Note: SBS is geo-restricted to Australia.
    """
    
    API_BASE = "https://www.sbs.com.au/api"
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
        )
    
    async def close(self):
        if self.client:
            await self.client.aclose()
    
    async def get_live_channels(self) -> List[Dict]:
        """Get SBS live channels."""
        # Known SBS channels
        return [
            {'id': 'aus_sbs_main', 'name': 'SBS', 'category': 'Australian General', 'source': 'sbs', 'stream_url': None, 'embed_url': None},
            {'id': 'aus_sbs_viceland', 'name': 'SBS Viceland', 'category': 'Australian Entertainment', 'source': 'sbs', 'stream_url': None, 'embed_url': None},
            {'id': 'aus_sbs_food', 'name': 'SBS Food', 'category': 'Australian Lifestyle', 'source': 'sbs', 'stream_url': None, 'embed_url': None},
            {'id': 'aus_sbs_world', 'name': 'SBS World Movies', 'category': 'Australian Movies', 'source': 'sbs', 'stream_url': None, 'embed_url': None},
            {'id': 'aus_sbs_nitv', 'name': 'NITV', 'category': 'Australian Indigenous', 'source': 'sbs', 'stream_url': None, 'embed_url': None},
        ]


class TenPlayScraper:
    """
    Scraper for 10Play (Network Ten).
    
    URL: https://10play.com.au
    """
    
    def __init__(self, base_url: str = "https://10play.com.au"):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )
    
    async def close(self):
        if self.client:
            await self.client.aclose()
    
    async def get_live_channels(self) -> List[Dict]:
        """Get Network Ten channels."""
        return [
            {'id': 'aus_ten_main', 'name': 'Channel 10', 'category': 'Australian General', 'source': '10play', 'stream_url': None, 'embed_url': None},
            {'id': 'aus_ten_bold', 'name': '10 Bold', 'category': 'Australian Entertainment', 'source': '10play', 'stream_url': None, 'embed_url': None},
            {'id': 'aus_ten_peach', 'name': '10 Peach', 'category': 'Australian Entertainment', 'source': '10play', 'stream_url': None, 'embed_url': None},
        ]


# Convenience function
async def scrape_australian_channels() -> List[Dict]:
    """Scrape all Australian TV channels."""
    all_channels = []
    
    # Freeview (comprehensive list)
    freeview = FreeviewScraper()
    await freeview.initialize()
    try:
        channels = await freeview.get_channels()
        all_channels.extend(channels)
    finally:
        await freeview.close()
    
    # ABC iView
    abc = ABCiViewScraper()
    await abc.initialize()
    try:
        channels = await abc.get_live_channels()
        all_channels.extend(channels)
    finally:
        await abc.close()
    
    # SBS
    sbs = SBSOnDemandScraper()
    await sbs.initialize()
    try:
        channels = await sbs.get_live_channels()
        all_channels.extend(channels)
    finally:
        await sbs.close()
    
    return all_channels


# Test
if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("Australian TV Scraper Test")
        print("=" * 60)
        
        channels = await scrape_australian_channels()
        
        print(f"\n✅ Found {len(channels)} Australian channels:\n")
        
        # Group by source
        by_source = {}
        for ch in channels:
            src = ch['source']
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(ch)
        
        for source, chs in by_source.items():
            print(f"\n📺 {source.upper()} ({len(chs)} channels):")
            for ch in chs:
                stream = "✓" if ch.get('stream_url') else "✗"
                print(f"   [{stream}] {ch['name']} - {ch['category']}")
    
    asyncio.run(test())
