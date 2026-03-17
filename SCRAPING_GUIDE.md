# 🎓 Complete Guide to HTML Inspection & Web Scraping

## Introduction

This guide teaches you how to analyze website HTML structure and build effective scrapers. We'll use real examples from streaming sites.

---

## Part 1: Using Browser Developer Tools

### Opening DevTools

| Browser | Shortcut | Menu Path |
|---------|----------|-----------|
| Chrome | `F12` or `Ctrl+Shift+I` | Menu → More Tools → Developer Tools |
| Firefox | `F12` or `Ctrl+Shift+I` | Menu → Web Developer → Inspector |
| Safari | `Cmd+Option+I` | Develop → Show Web Inspector |
| Edge | `F12` | Menu → More Tools → Developer Tools |

### The Elements Panel

Once DevTools is open, you'll see the **Elements** panel showing the HTML structure:

```
┌─────────────────────────────────────────────────────────────┐
│ Elements  Console  Sources  Network  ...                    │
├─────────────────────────────────────────────────────────────┤
│ <html>                                                      │
│   <head> ... </head>                                        │
│   <body>                                                    │
│     <nav class="navbar is-danger">                         │
│       <div class="container">                              │
│         <a class="navbar-item" href="/en">  ← Right-click  │
│           DaddyLive                                        │
│         </a>                                                │
│       </div>                                                │
│     </nav>                                                  │
│     ...                                                     │
│   </body>                                                   │
│ </html>                                                     │
└─────────────────────────────────────────────────────────────┘
```

### Essential DevTools Features

1. **Inspect Element** - Right-click any element → "Inspect"
2. **Copy Selector** - Right-click element → Copy → Copy selector
3. **Copy XPath** - Right-click element → Copy → Copy XPath
4. **Search HTML** - `Ctrl+F` within Elements panel
5. **Network Tab** - See all HTTP requests (great for finding APIs!)

---

## Part 2: Analyzing the Target Site

### Example: DaddyLive Homepage Structure

Looking at the actual HTML from `daddylivehd.net`:

```html
<!-- Navigation Bar -->
<nav class="navbar is-danger has-shadow hidden-print">
    <div class="container">
        <div class="navbar-brand">
            <a class="navbar-item" href="/en">
                <span class="is-size-4">Daddy<b>Live</b></span>
            </a>
        </div>
        <div id="navMenuColordark-example" class="navbar-menu">
            <div class="navbar-end">
                <a class="navbar-item" href="https://daddylivehd.net/en/elephtv-apk">
                    ElephTV APK
                </a>
                <a class="navbar-item" href="https://daddylivehd.net/en/daddy-live-schedule">
                    Daddy Live Schedule
                </a>
            </div>
        </div>
    </div>
</nav>
```

### Key Observations:

| Element | Selector | Purpose |
|---------|----------|---------|
| Navigation | `.navbar` | Contains main menu |
| Menu items | `.navbar-item` | Individual links |
| Brand link | `.navbar-brand .navbar-item` | Logo/home link |

### Schedule Page Structure

From the schedule page HTML:

```html
<div class="content">
    <h3><b>Thursday 19th Jan 2025 - Schedule Time UK GMT</b></h3>
    
    <div><b>PPV Events</b></div>
    <div><b>19:45</b></div>
    <div><b>2025 Chilly Willy at Tucson Speedway</b></div>
    <div><b>22:30</b></div>
    <div><b>Lucas Oil Late Model Series 2025</b></div>
    
    <div><b>Soccer</b></div>
    <div><b>06:00</b></div>
    <div><b>Australia - A-League Women : Sydney FC vs Central Coast Mariners</b></div>
</div>
```

### Problem: Poor HTML Structure

The schedule data is in plain `<div><b>` tags without proper classes! This makes scraping harder but still possible.

---

## Part 3: Finding CSS Selectors

### Method 1: Using Browser's "Copy Selector"

1. Right-click the element you want
2. Select **Copy → Copy selector**
3. Result example: `#navMenuColordark-example > div > a:nth-child(2)`

### Method 2: Building Custom Selectors

```css
/* By ID */
#navMenuColordark-example

/* By Class */
.navbar-item

/* By Tag */
nav

/* By Attribute */
a[href*="schedule"]

/* Combinations */
nav.navbar.is-danger

/* Descendants */
.navbar .navbar-item

/* Direct children */
.navbar > .container > .navbar-brand
```

### Method 3: Using DevTools Console

Open Console and test selectors:

```javascript
// Test if selector finds elements
document.querySelectorAll('.navbar-item')
// Returns NodeList(5) [a.navbar-item, a.navbar-item, ...]

// Count matches
document.querySelectorAll('.navbar-item').length
// 5

// Get text content
document.querySelector('.navbar-brand').textContent
// " DaddyLive"
```

---

## Part 4: Building a Scraper

### Basic BeautifulSoup Scraper

```python
import asyncio
import httpx
from bs4 import BeautifulSoup

async def scrape_daddylive_schedule():
    """Scrape the schedule page for events."""
    url = "https://daddylivehd.net/en/daddy-live-schedule"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the content div
    content = soup.find('div', class_='content')
    
    if not content:
        return []
    
    events = []
    current_category = None
    current_time = None
    
    # Iterate through all divs
    for div in content.find_all('div'):
        text = div.get_text(strip=True)
        
        # Check if this is a time (matches HH:MM pattern)
        if text and ':' in text and len(text) <= 5:
            current_time = text
        # Check if this could be a category or event
        elif text:
            # Known categories
            categories = ['PPV Events', 'TV Shows', 'Soccer', 'Football', 
                         'Basketball', 'Tennis', 'Cricket', 'Rugby']
            
            if any(cat.lower() in text.lower() for cat in categories):
                current_category = text
            elif current_time and current_category:
                # This is an event!
                events.append({
                    'category': current_category,
                    'time': current_time,
                    'title': text,
                })
    
    return events
```

### Better Approach: Parse by Pattern

```python
import re

async def scrape_schedule_improved():
    """Improved schedule scraper using regex patterns."""
    url = "https://daddylivehd.net/en/daddy-live-schedule"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find('div', class_='content')
    
    # Get all text content
    text = content.get_text('\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    events = []
    current_category = None
    time_pattern = re.compile(r'^\d{1,2}:\d{2}$')
    
    for i, line in enumerate(lines):
        # Check for time
        if time_pattern.match(line):
            time = line
            # Next line should be the event title
            if i + 1 < len(lines):
                title = lines[i + 1]
                events.append({
                    'time': time,
                    'title': title,
                    'category': current_category,
                })
        # Check for category headers
        elif line in ['PPV Events', 'TV Shows', 'Soccer', 'Football']:
            current_category = line
    
    return events
```

---

## Part 5: Finding Hidden APIs

Many sites load data via AJAX/API calls. The Network tab reveals these!

### Steps:

1. Open DevTools → **Network** tab
2. Refresh the page
3. Filter by **XHR** or **Fetch**
4. Look for JSON responses

### Example Network Request

```
Name                    Status  Type    Size
─────────────────────────────────────────────
matches/all-today       200     xhr     45KB  ← This is an API!
stream/source/123       200     xhr     2KB
manifest.json           200     document 1KB
```

### Click on Request → Preview Tab

```json
[
  {
    "id": "abc123",
    "title": "Lakers vs Warriors",
    "category": "Basketball",
    "date": 1737360000000,
    "sources": [
      {"source": "golf", "id": "xyz789"}
    ]
  }
]
```

### Using the API Instead of Scraping HTML

```python
async def fetch_from_api():
    """Fetch data directly from the API."""
    api_url = "https://streamed.pk/api/matches/all-today"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(api_url)
        return response.json()  # Already parsed JSON!
```

This is **much easier** and **more reliable** than HTML scraping!

---

## Part 6: Handling Challenges

### Challenge 1: Dynamic Content (JavaScript)

**Problem:** Page content loads via JavaScript after page load.

**Solution:** Use Playwright/Selenium to render JavaScript:

```python
from playwright.async_api import async_playwright

async def scrape_dynamic_content(url):
    """Scrape JavaScript-rendered content."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url)
        await page.wait_for_load_state('networkidle')  # Wait for JS
        
        # Get the fully rendered HTML
        html = await page.content()
        
        await browser.close()
        
    return BeautifulSoup(html, 'html.parser')
```

### Challenge 2: Anti-Bot Protection

**Common Protections:**
- Cloudflare
- CAPTCHA
- Rate limiting
- User-agent detection

**Solutions:**

```python
# Rotate User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/123.0",
]

# Use realistic headers
headers = {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Add delays between requests
await asyncio.sleep(random.uniform(1, 3))
```

### Challenge 3: Cloudflare Challenge Pages

```python
# Use curl_cffi which can bypass some Cloudflare checks
from curl_cffi import requests as cffi_requests

async def bypass_cloudflare(url):
    """Attempt to bypass Cloudflare with TLS fingerprint."""
    async with cffi_requests.AsyncSession(impersonate="chrome120") as session:
        response = await session.get(url)
        return response.text
```

### Challenge 4: Finding Stream URLs

Stream URLs are often hidden in embeds. Here's how to find them:

```python
async def find_stream_url(embed_url):
    """Find M3U8 URL inside an embed page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Capture network requests
        m3u8_urls = []
        
        def handle_request(request):
            if '.m3u8' in request.url:
                m3u8_urls.append(request.url)
        
        page.on('request', handle_request)
        
        # Navigate and interact
        await page.goto(embed_url)
        
        # Try to trigger video playback
        try:
            await page.click('.play-button', timeout=5000)
        except:
            pass
        
        await page.wait_for_timeout(5000)  # Wait for video to start
        await browser.close()
        
    return m3u8_urls[0] if m3u8_urls else None
```

---

## Part 7: Complete Working Example

Here's a complete scraper for daddylive:

```python
import asyncio
import re
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

class DaddyLiveScraper:
    def __init__(self):
        self.base_url = "https://daddylivehd.net"
        self.client = None
    
    async def initialize(self):
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
    
    async def close(self):
        if self.client:
            await self.client.aclose()
    
    async def get_schedule(self) -> List[Dict]:
        """Get today's schedule."""
        url = f"{self.base_url}/en/daddy-live-schedule"
        response = await self.client.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the content div
        content = soup.find('div', class_='content')
        if not content:
            return []
        
        events = []
        current_category = None
        time_pattern = re.compile(r'^\d{1,2}:\d{2}$')
        
        # Get all bold text elements
        for b in content.find_all('b'):
            text = b.get_text(strip=True)
            
            if time_pattern.match(text):
                # This is a time - next sibling is the event
                time = text
                parent = b.parent
                if parent and parent.next_sibling:
                    next_div = parent.next_sibling
                    if hasattr(next_div, 'find'):
                        title_b = next_div.find('b')
                        if title_b:
                            events.append({
                                'time': time,
                                'title': title_b.get_text(strip=True),
                                'category': current_category,
                            })
            elif text in ['PPV Events', 'TV Shows', 'Soccer', 'Football', 
                         'Basketball', 'Tennis', 'Cricket', 'Rugby', 'Motor']:
                current_category = text
        
        return events
    
    async def get_channels(self) -> List[Dict]:
        """Get 24/7 channel list."""
        # Note: You'd need to find the actual channels page URL
        # This is a template based on the site structure
        url = f"{self.base_url}/en/channels"  # Hypothetical URL
        
        try:
            response = await self.client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            channels = []
            # Look for channel links/elements
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'channel' in href.lower() or 'stream' in href.lower():
                    name = link.get_text(strip=True)
                    if name:
                        channels.append({
                            'name': name,
                            'url': href if href.startswith('http') else f"{self.base_url}{href}",
                        })
            
            return channels
        except Exception as e:
            print(f"Error fetching channels: {e}")
            return []
    
    async def resolve_stream(self, channel_url: str) -> str:
        """Resolve the actual stream URL from a channel page."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"
            )
            page = await context.new_page()
            
            m3u8_url = None
            
            def capture_request(request):
                nonlocal m3u8_url
                if '.m3u8' in request.url and not m3u8_url:
                    m3u8_url = request.url
            
            page.on('request', capture_request)
            
            try:
                await page.goto(channel_url, timeout=30000)
                await page.wait_for_timeout(5000)
                
                # Try clicking play if no stream found
                if not m3u8_url:
                    for selector in ['.play-button', 'video', '#player']:
                        try:
                            await page.click(selector, timeout=2000)
                            await page.wait_for_timeout(3000)
                            if m3u8_url:
                                break
                        except:
                            pass
            finally:
                await browser.close()
            
            return m3u8_url


# Usage Example
async def main():
    scraper = DaddyLiveScraper()
    await scraper.initialize()
    
    try:
        # Get schedule
        schedule = await scraper.get_schedule()
        print(f"Found {len(schedule)} events:")
        for event in schedule[:5]:
            print(f"  [{event['time']}] {event['title']}")
        
        # Get channels
        channels = await scraper.get_channels()
        print(f"\nFound {len(channels)} channels")
        
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Part 8: Testing Your Scrapers

### Quick Test in Python REPL

```python
# Start Python
python

# Import and test
>>> import httpx
>>> from bs4 import BeautifulSoup
>>> 
>>> url = "https://daddylivehd.net/en/daddy-live-schedule"
>>> response = httpx.get(url)
>>> soup = BeautifulSoup(response.text, 'html.parser')
>>> 
>>> # Test your selectors
>>> soup.find('div', class_='content')
<div class="content">...</div>
>>> 
>>> soup.find_all('b')[:5]
[<b>Thursday 19th Jan 2025...</b>, ...]
```

### Using curl to Test Endpoints

```bash
# Test if URL is accessible
curl -I https://daddylivehd.net

# Get page content
curl https://daddylivehd.net/en/daddy-live-schedule

# Test with custom headers
curl -H "User-Agent: Mozilla/5.0" https://daddylivehd.net

# Test API endpoints
curl https://streamed.pk/api/matches/all-today | jq
```

---

## Part 9: Best Practices

### 1. Respect robots.txt

```python
import urllib.robotparser

def check_robots_txt(base_url, user_agent="*"):
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{base_url}/robots.txt")
    rp.read()
    return rp.can_fetch(user_agent, base_url)
```

### 2. Add Rate Limiting

```python
import asyncio
from functools import wraps

def rate_limit(delay: float):
    """Decorator to add delay between calls."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await asyncio.sleep(delay)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(1.0)  # 1 second delay
async def fetch_page(url):
    ...
```

### 3. Handle Errors Gracefully

```python
async def safe_fetch(client, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response
        except httpx.HTTPError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### 4. Cache Results

```python
import json
from pathlib import Path

class CacheManager:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def get(self, key):
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None
    
    def set(self, key, value):
        path = self.cache_dir / f"{key}.json"
        path.write_text(json.dumps(value))
```

---

## Part 10: Common Mistakes to Avoid

| Mistake | Problem | Solution |
|---------|---------|----------|
| No headers | Blocked as bot | Add realistic User-Agent |
| No delays | Rate limited | Add `asyncio.sleep()` |
| No error handling | Crashes on failure | Use try/except |
| Parsing with regex | Brittle code | Use BeautifulSoup |
| Ignoring encoding | Unicode errors | Specify `response.encoding` |
| No timeout | Infinite hangs | Always set timeouts |
| Not closing connections | Memory leaks | Use context managers |

---

## Summary

1. **Use DevTools** to inspect HTML and find selectors
2. **Check Network tab** for hidden APIs
3. **Use BeautifulSoup** for static HTML
4. **Use Playwright** for dynamic content
5. **Handle errors** gracefully
6. **Respect rate limits** to avoid being blocked
7. **Test incrementally** - build piece by piece

Happy scraping! 🕷️
