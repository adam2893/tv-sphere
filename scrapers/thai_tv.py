"""
Thai TV Scraper Module
Scrapes Thai TV channels from adintrend.tv and other Thai sources
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ThaiTVScraper:
    """
    Scraper for Thai TV channels from adintrend.tv
    
    Channels available:
    - ช่อง 3 (Channel 3)
    - ช่อง 5 (Channel 5)  
    - ช่อง 7 (Channel 7)
    - ช่อง 8 (Channel 8)
    - ช่อง 9 (Channel 9)
    - NBT
    - Nation TV
    - PPTV HD
    - GMM 25
    - อมรินทร์ทีวี (Amarin TV)
    - Thai PBS
    - ไทยรัฐทีวี (Thairath TV)
    - MONO29
    """
    
    CHANNELS = {
        'ch3': {'name': 'Channel 3', 'thai_name': 'ช่อง 3', 'category': 'Entertainment'},
        'ch5': {'name': 'Channel 5', 'thai_name': 'ช่อง 5', 'category': 'Entertainment'},
        'ch7': {'name': 'Channel 7', 'thai_name': 'ช่อง 7', 'category': 'Entertainment'},
        'ch9': {'name': 'Channel 9', 'thai_name': 'ช่อง 9', 'category': 'Entertainment'},
        'ch11': {'name': 'NBT', 'thai_name': 'NBT', 'category': 'News'},
        'ch37': {'name': 'Nation TV', 'thai_name': 'Nation', 'category': 'News'},
        'ch33': {'name': 'Channel 8', 'thai_name': 'ช่อง 8', 'category': 'Entertainment'},
        'ch25': {'name': 'PPTV HD', 'thai_name': 'PPTV HD', 'category': 'News'},
        'ch0': {'name': 'GMM 25', 'thai_name': 'GMM 25', 'category': 'Entertainment'},
        'ch26': {'name': 'Amarin TV', 'thai_name': 'อมรินทร์ทีวี', 'category': 'Entertainment'},
        'ch1': {'name': 'Thai PBS', 'thai_name': 'Thai PBS', 'category': 'News'},
        'ch39': {'name': 'Thairath TV', 'thai_name': 'ไทยรัฐทีวี', 'category': 'News'},
        'ch38': {'name': 'MONO29', 'thai_name': 'MONO29', 'category': 'Entertainment'},
    }
    
    def __init__(self, base_url: str = "https://www.adintrend.tv"):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        """Initialize HTTP client."""
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
            }
        )
    
    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def get_channel_list(self) -> List[Dict]:
        """Get list of available Thai TV channels."""
        channels = []
        
        for channel_id, info in self.CHANNELS.items():
            channels.append({
                'id': f"thai_{channel_id}",
                'name': f"{info['name']} ({info['thai_name']})",
                'category': f"Thai {info['category']}",
                'source': 'adintrend',
                # These are embed pages that need Playwright resolution
                'embed_url': f"{self.base_url}/hd/{channel_id}?t=live",
                'stream_url': None,  # No direct stream URL available
                'logo': f"{self.base_url}/images02/ch{channel_id}.png",
            })
        
        return channels
    
    async def get_stream_url(self, channel_id: str) -> Optional[str]:
        """
        Get the actual stream URL for a Thai channel.
        Requires Playwright to resolve the embed.
        """
        if not self.client:
            await self.initialize()
        
        try:
            # Navigate to channel page
            url = f"{self.base_url}/hd/{channel_id}?t=live"
            response = await self.client.get(url)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the iframe source
            iframe = soup.find('iframe', id='TV')
            if iframe and iframe.get('src'):
                iframe_url = iframe['src']
                logger.info(f"Found iframe for {channel_id}: {iframe_url}")
                return iframe_url
            
            # Alternative: look for script with src
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'iframe' in str(script.string).lower():
                    # Try to extract URL
                    match = re.search(r'src=["\']([^"\']+)["\']', str(script.string))
                    if match:
                        return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting stream for {channel_id}: {e}")
            return None


class Ch7Scraper:
    """
    Scraper for Channel 7 HD Thailand (ch7.com)
    Official site with live streaming
    """
    
    def __init__(self, base_url: str = "https://www.ch7.com"):
        self.base_url = base_url
        self.client: Optional[httpx.AsyncClient] = None
    
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
    
    async def get_live_url(self) -> Optional[str]:
        """Get Channel 7 live stream URL."""
        try:
            response = await self.client.get(f"{self.base_url}/live")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for video source or iframe
            video = soup.find('video')
            if video and video.get('src'):
                return video['src']
            
            source = soup.find('source')
            if source and source.get('src'):
                return source['src']
            
            # Look for m3u8 in scripts
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and '.m3u8' in str(script.string):
                    match = re.search(r'(https?://[^\s"\']+\.)m3u8', str(script.string))
                    if match:
                        return match.group(0)
            
            return None
        except Exception as e:
            logger.error(f"Error fetching CH7 live: {e}")
            return None
    
    def get_channel_info(self) -> Dict:
        """Get Channel 7 info."""
        return {
            'id': 'thai_ch7',
            'name': 'Channel 7 HD',
            'thai_name': 'ช่อง 7HD',
            'category': 'Thai Entertainment',
            'source': 'ch7',
            'stream_url': f"{self.base_url}/live",
        }


# Convenience functions
async def scrape_thai_channels() -> List[Dict]:
    """Quick function to get all Thai channels."""
    scraper = ThaiTVScraper()
    await scraper.initialize()
    try:
        return await scraper.get_channel_list()
    finally:
        await scraper.close()


# Test
if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("Thai TV Scraper Test")
        print("=" * 60)
        
        scraper = ThaiTVScraper()
        await scraper.initialize()
        
        try:
            channels = await scraper.get_channel_list()
            print(f"\n✅ Found {len(channels)} Thai channels:\n")
            
            for ch in channels:
                print(f"  {ch['name']}: {ch['stream_url']}")
            
            # Test getting a stream URL
            print("\n" + "-" * 40)
            print("Testing stream URL for Channel 3...")
            stream_url = await scraper.get_stream_url('ch3')
            if stream_url:
                print(f"Found: {stream_url[:80]}...")
            else:
                print("Could not resolve stream URL (may need Playwright)")
                
        finally:
            await scraper.close()
    
    asyncio.run(test())
