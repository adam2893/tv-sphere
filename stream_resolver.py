"""
Stream Resolver Module
Resolves M3U8 stream URLs from embed pages using Playwright
"""
import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class StreamResolver:
    """
    Resolves embed URLs to actual M3U8 stream URLs using headless browser.
    
    Flow:
    1. Navigate to embed URL with Playwright
    2. Capture network requests
    3. Extract M3U8 URLs from network traffic
    4. Return stream URL + required headers
    """
    
    def __init__(
        self,
        timeout: int = 30,
        headless: bool = True,
        locale: str = "en-US",
        timezone: str = "America/Chicago",
    ):
        self.timeout = timeout
        self.headless = headless
        self.locale = locale
        self.timezone = timezone
        
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Patterns to ignore in M3U8 detection
        self.ignore_patterns = [
            'narakathegame',
            'doubleclick',
            'googleads',
        ]
    
    async def resolve_embed(self, embed_url: str) -> Optional[Dict]:
        """
        Resolve an embed URL to get the actual stream URL.
        
        Returns:
            {
                'url': 'https://example.com/stream.m3u8',
                'headers': {'Referer': '...', 'User-Agent': '...', ...},
                'clean_root': 'https://example.com/'
            }
            or None if resolution failed
        """
        logger.info(f"Resolving embed: {embed_url}")
        
        async with async_playwright() as p:
            # Launch browser
            try:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    channel="chrome",
                    args=[
                        "--no-sandbox",
                        "--disable-gpu",
                        "--mute-audio",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )
            except Exception:
                # Fallback to bundled Chromium
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
            
            try:
                result = await self._resolve_with_browser(embed_url, browser)
                return result
            finally:
                await browser.close()
    
    async def _resolve_with_browser(self, embed_url: str, browser: Browser) -> Optional[Dict]:
        """Internal method to resolve with a browser instance."""
        
        parsed_uri = urlparse(embed_url)
        clean_root = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
        clean_origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
        
        stream_info: Dict = {}
        
        # Create browser context
        context = await browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1366, "height": 768},
            ignore_https_errors=True,
            locale=self.locale,
            timezone_id=self.timezone,
        )
        
        # Set extra headers
        await context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Upgrade-Insecure-Requests": "1",
        })
        
        # Inject anti-detection script
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            window.chrome = window.chrome || { runtime: {} };
        """)
        
        page = await context.new_page()
        
        # Block unnecessary resources to speed up
        BLOCKED_TYPES = {"image", "stylesheet", "font", "media"}
        
        async def block_resources(route):
            try:
                if route.request.resource_type in BLOCKED_TYPES:
                    await route.abort()
                else:
                    await route.continue_()
            except:
                pass
        
        await page.route("**/*", block_resources)
        
        # Handle popup windows
        async def handle_popup(popup):
            if popup != page:
                try:
                    await popup.close()
                except:
                    pass
        
        context.on("page", handle_popup)
        
        # Capture M3U8 URLs from network requests
        async def handle_request(request):
            if "url" in stream_info:
                return
            
            url = request.url
            
            # Check for M3U8
            if ".m3u" in url and "http" in url:
                # Skip ignore patterns
                for pattern in self.ignore_patterns:
                    if pattern in url.lower():
                        return
                
                logger.info(f"Found M3U8: {url}")
                
                try:
                    headers = await request.all_headers()
                    
                    stream_info["headers"] = {
                        "User-Agent": self.user_agent,
                        "Cookie": headers.get("cookie", ""),
                        "Referer": headers.get("referer", embed_url),
                        "Origin": clean_origin,
                    }
                    stream_info["url"] = url
                    stream_info["clean_root"] = clean_root
                    
                except Exception as e:
                    logger.warning(f"Could not capture headers: {e}")
        
        page.on("request", handle_request)
        
        try:
            # Navigate to embed page
            await page.goto(embed_url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            
            # Wait for network to settle
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            # Try to trigger video playback
            if "url" not in stream_info:
                await self._try_trigger_playback(page)
            
            # Wait a bit more for stream detection
            for _ in range(5):
                if "url" in stream_info:
                    break
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error(f"Playwright error: {e}")
        finally:
            await context.close()
        
        if "url" in stream_info:
            logger.info(f"Successfully resolved: {stream_info['url'][:80]}...")
            return stream_info
        else:
            logger.warning(f"Failed to resolve stream from: {embed_url}")
            return None
    
    async def _try_trigger_playback(self, page: Page):
        """Try various methods to trigger video playback."""
        
        # Common play button selectors
        play_selectors = [
            "button.vjs-big-play-button",
            ".play-button",
            "div.play",
            "svg",
            "video",
            "#player",
            ".jw-icon-playback",
            ".jwplayer",
            ".plyr__control--overlaid",
            "button[aria-label='Play']",
            "button",
        ]
        
        # Try clicking play buttons
        for selector in play_selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1000, force=True)
                    await asyncio.sleep(0.5)
            except:
                pass
        
        # Try mouse click in center
        try:
            await page.mouse.click(683, 384)
        except:
            pass
        
        # Try JavaScript-based triggering
        try:
            await page.evaluate("""
                () => {
                    const candidates = document.querySelectorAll(
                        'video, button, .play-button, .jw-icon-playback, #player, .jwplayer'
                    );
                    for (const element of candidates) {
                        try {
                            element.dispatchEvent(new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window,
                            }));
                        } catch (e) {}
                    }
                    
                    // Try to play videos directly
                    for (const video of document.querySelectorAll('video')) {
                        try {
                            video.muted = true;
                            video.play().catch(() => {});
                        } catch (e) {}
                    }
                }
            """)
        except:
            pass


# Convenience function
async def resolve_stream(embed_url: str, timeout: int = 30) -> Optional[Dict]:
    """Quick function to resolve a stream URL."""
    resolver = StreamResolver(timeout=timeout)
    return await resolver.resolve_embed(embed_url)


# Test
if __name__ == "__main__":
    import sys
    
    async def test():
        if len(sys.argv) < 2:
            print("Usage: python stream_resolver.py <embed_url>")
            print("\nExample:")
            print("  python stream_resolver.py 'https://example.com/embed/123'")
            return
        
        embed_url = sys.argv[1]
        print(f"Resolving: {embed_url}")
        print("-" * 60)
        
        result = await resolve_stream(embed_url)
        
        if result:
            print(f"\n✅ SUCCESS!")
            print(f"URL: {result['url']}")
            print(f"Headers: {result['headers']}")
        else:
            print("\n❌ FAILED - No stream found")
    
    asyncio.run(test())
