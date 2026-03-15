"""
TV Sphere - Stremio Addon for Live TV Channels
A multi-source live TV streaming aggregator for Stremio
"""
import asyncio
import logging
import time
import base64
import json
import hmac
import hashlib
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urljoin, urlparse
from datetime import datetime

import httpx
from quart import (
    Quart,
    jsonify,
    send_from_directory,
    url_for,
    request,
    Response,
    render_template,
)
from quart_cors import cors
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Quart(__name__)
app = cors(app, allow_origin="*")

# --- TV Sources Configuration ---
TV_SOURCES = {
    "daddylive": {
        "name": "DaddyLive",
        "base_url": "https://daddylive.mp",
        "channels_path": "/24-7-channels.php",
        "enabled": True,
    },
    "streamed": {
        "name": "Streamed",
        "base_url": "https://streamed.pk",
        "api_base": "https://streamed.pk/api",
        "enabled": True,
    },
    # Add more sources as needed
}

# --- Environment Variables ---
CACHE_TIMEOUT = int(os.environ.get("CACHE_TIMEOUT", "300"))  # 5 minutes
STREAM_CACHE_DURATION = int(os.environ.get("STREAM_CACHE_DURATION", "1800"))  # 30 minutes
SECRET_KEY = os.environ.get("PROXY_SECRET_KEY", "change-me-to-a-real-secret")
MAX_CONCURRENT_RESOLVERS = int(os.environ.get("MAX_CONCURRENT_RESOLVERS", "2"))
MAX_GLOBAL_CONCURRENT_RESOLVERS = int(
    os.environ.get("MAX_GLOBAL_CONCURRENT_RESOLVERS", str(MAX_CONCURRENT_RESOLVERS))
)
STREAM_RESOLUTION_TIMEOUT = float(os.environ.get("STREAM_RESOLUTION_TIMEOUT", "60"))
PER_EMBED_TIMEOUT = float(os.environ.get("PER_EMBED_TIMEOUT", "30"))
PLAYWRIGHT_LOCALE = os.environ.get("PLAYWRIGHT_LOCALE", "en-US")
PLAYWRIGHT_TIMEZONE = os.environ.get("PLAYWRIGHT_TIMEZONE", "America/Chicago")

# --- Global Caches ---
catalog_cache: Dict = {}
stream_cache: Dict = {}
catalog_cache_lock = asyncio.Lock()
stream_cache_lock = asyncio.Lock()
upstream_client_lock = asyncio.Lock()
in_flight_streams_lock = asyncio.Lock()
in_flight_stream_requests: Dict = {}
global_resolver_semaphore = asyncio.Semaphore(MAX_GLOBAL_CONCURRENT_RESOLVERS)
upstream_client: Optional[httpx.AsyncClient] = None

# --- TV Channel Categories ---
CATEGORIES = {
    "news": {"name": "News", "icon": "📰"},
    "sports": {"name": "Sports", "icon": "⚽"},
    "entertainment": {"name": "Entertainment", "icon": "🎬"},
    "movies": {"name": "Movies", "icon": "🎥"},
    "kids": {"name": "Kids", "icon": "🧸"},
    "documentary": {"name": "Documentary", "icon": "📚"},
    "music": {"name": "Music", "icon": "🎵"},
    "lifestyle": {"name": "Lifestyle", "icon": "🏠"},
    "international": {"name": "International", "icon": "🌍"},
    "other": {"name": "Other", "icon": "📺"},
}

# --- Helper Functions ---


def sign_url(url: str) -> str:
    """Generate an HMAC-SHA256 signature for a proxy URL."""
    return hmac.new(SECRET_KEY.encode(), url.encode(), hashlib.sha256).hexdigest()


async def get_upstream_client() -> httpx.AsyncClient:
    global upstream_client

    if upstream_client is not None:
        return upstream_client

    async with upstream_client_lock:
        if upstream_client is None:
            upstream_client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )

    return upstream_client


@app.after_serving
async def close_upstream_client() -> None:
    global upstream_client

    if upstream_client is None:
        return

    await upstream_client.aclose()
    upstream_client = None


def categorize_channel(channel_name: str) -> str:
    """Auto-categorize channel based on name keywords."""
    name_lower = channel_name.lower()

    # Sports channels
    if any(kw in name_lower for kw in ["espn", "sports", "sport", "fox sports", "bein", "sky sports", "nba", "nfl", "mlb", "nhl", "golf", "tennis", "f1", "fight"]):
        return "sports"

    # News channels
    if any(kw in name_lower for kw in ["news", "cnn", "bbc", "cnbc", "fox news", "msnbc", "abc news", "nbc news", "cbs news", "sky news", "al jazeera", "dw", "france 24"]):
        return "news"

    # Kids channels
    if any(kw in name_lower for kw in ["disney", "nickelodeon", "nick", "cartoon", "kids", "boomerang", "pbs kids", "baby"]):
        return "kids"

    # Movies channels
    if any(kw in name_lower for kw in ["movie", "cinema", "film", "hbo", "showtime", "starz", "encore", "tcm", "amc", "fx movie"]):
        return "movies"

    # Documentary channels
    if any(kw in name_lower for kw in ["discovery", "national geographic", "nat geo", "history", "animal planet", "science", "documentary", "smithsonian"]):
        return "documentary"

    # Music channels
    if any(kw in name_lower for kw in ["mtv", "music", "vh1", "bet", "country music", "cmt"]):
        return "music"

    # Entertainment channels
    if any(kw in name_lower for kw in ["comedy", "entertainment", "e!", "bravo", "tnt", "tbs", "usa", "fx", "syfy", "abc", "nbc", "cbs", "fox", "cw"]):
        return "entertainment"

    # Lifestyle channels
    if any(kw in name_lower for kw in ["food", "travel", "home", "garden", "hgtv", "cooking", "lifestyle", "tlc", "lifetime", "oxygen"]):
        return "lifestyle"

    # International channels
    if any(kw in name_lower for kw in ["telemundo", "univision", "globo", "azteca", "internacional", "arabic", "hindi", "bollywood", "zdf", "rtl", "canal"]):
        return "international"

    return "other"


def generate_channel_id(channel_name: str, source: str) -> str:
    """Generate a unique channel ID."""
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', channel_name.lower())
    return f"tv_{source}_{clean_name}"


# --- Channel Scrapers ---

async def scrape_daddylive_channels() -> List[Dict]:
    """Scrape TV channels from DaddyLive 24/7 section."""
    channels = []

    source_config = TV_SOURCES.get("daddylive")
    if not source_config or not source_config.get("enabled"):
        return channels

    try:
        client = await get_upstream_client()
        url = f"{source_config['base_url']}{source_config['channels_path']}"
        logging.info(f"Scraping DaddyLive channels from: {url}")

        resp = await client.get(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find channel containers - adjust selectors based on actual site structure
        # This is a generic pattern - will need adjustment for real site
        channel_elements = soup.find_all('div', class_=lambda x: x and 'channel' in x.lower()) or \
                          soup.find_all('a', href=lambda x: x and 'stream' in x.lower()) or \
                          soup.find_all('tr', class_='channel-row')

        for elem in channel_elements:
            try:
                # Extract channel name
                name_elem = elem.find('span', class_='channel-name') or \
                           elem.find('td', class_='name') or \
                           elem.find('a')

                if not name_elem:
                    continue

                channel_name = name_elem.get_text(strip=True)
                if not channel_name:
                    continue

                # Extract stream URL
                link_elem = elem.find('a', href=True)
                if not link_elem:
                    continue

                stream_url = link_elem['href']
                if not stream_url.startswith('http'):
                    stream_url = urljoin(source_config['base_url'], stream_url)

                # Determine category
                category = categorize_channel(channel_name)
                channel_id = generate_channel_id(channel_name, "daddylive")

                channels.append({
                    "id": channel_id,
                    "name": channel_name,
                    "category": category,
                    "source": "daddylive",
                    "stream_url": stream_url,
                    "poster": f"https://logo.clearbit.com/{channel_name.lower().replace(' ', '')}.com",
                })

            except Exception as e:
                logging.debug(f"Error parsing channel element: {e}")
                continue

        logging.info(f"Scraped {len(channels)} channels from DaddyLive")

    except Exception as e:
        logging.error(f"Failed to scrape DaddyLive: {e}")

    return channels


async def scrape_streamed_channels() -> List[Dict]:
    """Fetch TV channels from Streamed.pk API (reusing SportsSphere approach)."""
    channels = []

    source_config = TV_SOURCES.get("streamed")
    if not source_config or not source_config.get("enabled"):
        return channels

    try:
        client = await get_upstream_client()
        api_base = source_config["api_base"]

        # Try to get 24/7 channels or live events
        # This endpoint might need adjustment based on actual API
        logging.info(f"Fetching channels from Streamed API: {api_base}")

        # Get today's events that could be treated as channels
        resp = await client.get(f"{api_base}/matches/all-today", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        for event in data:
            try:
                event_name = event.get("title", "")
                if not event_name:
                    continue

                # Treat live events as temporary channels
                category = event.get("category", "other").lower()
                channel_id = f"tv_streamed_{event['id']}"

                channels.append({
                    "id": channel_id,
                    "name": event_name,
                    "category": categorize_channel(event_name) if category == "other" else category,
                    "source": "streamed",
                    "event_id": event["id"],
                    "sources": event.get("sources", []),
                    "poster": event.get("poster"),
                })

            except Exception as e:
                logging.debug(f"Error parsing event: {e}")
                continue

        logging.info(f"Fetched {len(channels)} channels from Streamed")

    except Exception as e:
        logging.error(f"Failed to fetch from Streamed: {e}")

    return channels


async def get_all_channels() -> List[Dict]:
    """Aggregate channels from all enabled sources."""
    global catalog_cache

    async with catalog_cache_lock:
        current_time = time.time()

        if catalog_cache and (
            current_time - catalog_cache.get("last_updated", 0) < CACHE_TIMEOUT
        ):
            return catalog_cache["data"]

        all_channels = []

        # Run all scrapers concurrently
        tasks = [
            scrape_daddylive_channels(),
            scrape_streamed_channels(),
            # Add more scrapers here as needed
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_channels.extend(result)
            elif isinstance(result, Exception):
                logging.error(f"Scraper error: {result}")

        # Sort by category and name
        all_channels.sort(key=lambda x: (x.get("category", "other"), x.get("name", "")))

        catalog_cache = {"last_updated": current_time, "data": all_channels}
        return all_channels


# --- Stream Resolution ---

async def resolve_stream_url(channel: Dict, browser) -> Optional[Dict]:
    """Resolve the actual streaming URL for a channel."""
    source = channel.get("source", "")
    stream_url = channel.get("stream_url", "")
    channel_name = channel.get("name", "Unknown")

    logging.info(f"Resolving stream for: {channel_name} (source: {source})")

    stream_info = {}

    # Handle different sources differently
    if source == "streamed":
        # Use existing SportsSphere logic for streamed sources
        return await resolve_streamed_stream(channel, browser)

    if not stream_url:
        logging.warning(f"No stream URL for channel: {channel_name}")
        return None

    # Generic Playwright resolution for other sources
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    parsed_uri = urlparse(stream_url)
    clean_root = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
    clean_origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

    context = await browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1366, "height": 768},
        ignore_https_errors=True,
        locale=PLAYWRIGHT_LOCALE,
        timezone_id=PLAYWRIGHT_TIMEZONE,
    )

    await context.set_extra_http_headers({
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    })

    # Anti-detection script
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = window.chrome || { runtime: {} };
    """)

    page = await context.new_page()

    # Block unnecessary resources
    BLOCKED_RESOURCE_TYPES = {"image", "stylesheet", "font", "media"}

    async def block_resources(route):
        try:
            if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()
        except:
            pass

    await page.route("**/*", block_resources)

    # Capture M3U8 URLs
    async def handle_request(request):
        if "url" in stream_info:
            return

        url = request.url
        if ".m3u" in url and "http" in url:
            logging.info(f"Found M3U8: {url}")
            try:
                headers = await request.all_headers()
                stream_info["headers"] = {
                    "User-Agent": user_agent,
                    "Cookie": headers.get("cookie", ""),
                    "Referer": headers.get("referer", stream_url),
                    "Origin": clean_origin,
                }
                stream_info["url"] = url
                stream_info["clean_root"] = clean_root
            except Exception as e:
                logging.warning(f"Could not capture headers: {e}")

    page.on("request", handle_request)

    try:
        await page.goto(stream_url, wait_until="domcontentloaded", timeout=25000)

        # Wait a bit and try to trigger playback
        await asyncio.sleep(2)

        # Try common play button selectors
        for selector in ["button.vjs-big-play-button", ".play-button", "#player", "video", "button"]:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1000, force=True)
                    break
            except:
                pass

        # Wait for stream detection
        for _ in range(10):
            if "url" in stream_info:
                break
            await asyncio.sleep(0.5)

    except Exception as e:
        logging.error(f"Playwright error resolving {channel_name}: {e}")
    finally:
        await context.close()

    return stream_info if "url" in stream_info else None


async def resolve_streamed_stream(channel: Dict, browser) -> Optional[Dict]:
    """Resolve streams from Streamed source (adapted from SportsSphere)."""
    event_id = channel.get("event_id")
    sources = channel.get("sources", [])

    if not sources:
        return None

    # Get embed URLs from the API
    embed_urls = []
    client = await get_upstream_client()

    for src in sources:
        source_name = src.get("source")
        source_id = src.get("id")

        try:
            api_url = f"{TV_SOURCES['streamed']['api_base']}/stream/{source_name}/{source_id}"
            resp = await client.get(api_url, timeout=5.0)

            if resp.status_code == 200:
                streams_data = resp.json()
                for stream_obj in streams_data:
                    embed_url = stream_obj.get("embedUrl")
                    if embed_url:
                        embed_urls.append({
                            "url": embed_url,
                            "source": source_name,
                            "quality": "HD" if stream_obj.get("hd") else "SD",
                        })
        except Exception:
            continue

    if not embed_urls:
        return None

    # Try to resolve the first working embed
    for embed in embed_urls[:3]:  # Limit attempts
        result = await resolve_embed_url(embed["url"], browser)
        if result and "url" in result:
            result["source"] = embed["source"]
            result["quality"] = embed["quality"]
            return result

    return None


async def resolve_embed_url(embed_url: str, browser) -> Optional[Dict]:
    """Resolve an embed URL to get the actual stream URL."""
    stream_info = {}

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    parsed_uri = urlparse(embed_url)
    clean_root = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"

    context = await browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1366, "height": 768},
        ignore_https_errors=True,
    )

    page = await context.new_page()

    async def handle_request(request):
        if "url" in stream_info:
            return

        url = request.url
        if ".m3u" in url and "http" in url and "narakathegame" not in url:
            try:
                headers = await request.all_headers()
                stream_info["headers"] = {
                    "User-Agent": user_agent,
                    "Cookie": headers.get("cookie", ""),
                    "Referer": headers.get("referer", embed_url),
                }
                stream_info["url"] = url
                stream_info["clean_root"] = clean_root
            except:
                pass

    page.on("request", handle_request)

    try:
        await page.goto(embed_url, wait_until="domcontentloaded", timeout=25000)

        for _ in range(7):
            if "url" in stream_info:
                break

            # Try clicking play buttons
            try:
                await page.mouse.click(683, 384)
            except:
                pass

            await asyncio.sleep(1)

            for selector in ["button.vjs-big-play-button", ".play-button", "video", "#player"]:
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        await locator.first.click(timeout=1000, force=True)
                except:
                    pass

    except Exception as e:
        logging.debug(f"Embed resolution error: {e}")
    finally:
        await context.close()

    return stream_info if "url" in stream_info else None


async def get_cached_stream(channel_id: str) -> Optional[Dict]:
    """Get cached stream for a channel."""
    current_time = time.time()

    async with stream_cache_lock:
        cached = stream_cache.get(channel_id)
        if not cached:
            return None

        if current_time < cached["expires_at"]:
            return cached["stream"]

        del stream_cache[channel_id]

    return None


async def set_cached_stream(channel_id: str, stream: Dict) -> None:
    """Cache a resolved stream."""
    async with stream_cache_lock:
        stream_cache[channel_id] = {
            "stream": stream,
            "expires_at": time.time() + STREAM_CACHE_DURATION,
        }


async def resolve_channel_stream(channel_id: str) -> List[Dict]:
    """Resolve all available streams for a channel."""
    # Check cache first
    cached = await get_cached_stream(channel_id)
    if cached:
        logging.info(f"Cache hit for channel: {channel_id}")
        return [cached]

    # Get channel info
    channels = await get_all_channels()
    channel = next((c for c in channels if c["id"] == channel_id), None)

    if not channel:
        return []

    # Resolve stream using Playwright
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-gpu",
                    "--mute-audio",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
        except:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

        try:
            result = await asyncio.wait_for(
                resolve_stream_url(channel, browser),
                timeout=PER_EMBED_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logging.warning(f"Timeout resolving {channel_id}")
            result = None
        finally:
            await browser.close()

    if not result or "url" not in result:
        return []

    stream_url = result["url"]
    headers = result.get("headers", {})
    clean_root = result.get("clean_root", "")

    # Build stream response
    stream_response = {
        "title": f"{channel['name']} (Live)",
        "url": stream_url,
        "behaviorHints": {
            "notWebReady": True,
            "proxyHeaders": {"request": headers},
        },
    }

    # Check if proxy is needed
    needs_proxy = any(domain in stream_url for domain in ["strmd.top", "delta", "m3u8"])

    if needs_proxy:
        headers_json = json.dumps(headers)
        headers_b64 = base64.b64encode(headers_json.encode()).decode()
        proxy_url = f"{url_for('proxy_stream', _external=True)}?url={quote(stream_url)}&headers={headers_b64}&sig={sign_url(stream_url)}"
        stream_response = {
            "title": f"{channel['name']} (Proxy)",
            "url": proxy_url,
        }

    # Cache the result
    await set_cached_stream(channel_id, stream_response)

    return [stream_response]


# --- Proxy Engine ---

@app.route("/proxy")
async def proxy_stream():
    """Proxy M3U8 streams with proper headers."""
    target_url = request.args.get("url")
    headers_b64 = request.args.get("headers")
    sig = request.args.get("sig")

    if not target_url or not headers_b64:
        return "Missing params", 400

    # HMAC Signature Verification
    if not sig or not hmac.compare_digest(sig, sign_url(target_url)):
        logging.warning(f"Invalid signature for: {target_url}")
        return "Forbidden", 403

    try:
        headers = json.loads(base64.b64decode(headers_b64).decode("utf-8"))
    except:
        return "Invalid headers", 400

    # Clean headers
    for key in ["Host", "Content-Length", "Transfer-Encoding", "Connection", "Accept-Encoding"]:
        headers.pop(key, None)

    async with cffi_requests.AsyncSession(impersonate="chrome120") as session:
        try:
            resp = await session.get(target_url, headers=headers)

            if resp.status_code != 200:
                return f"Proxy Error {resp.status_code}", resp.status_code

            content_type = resp.headers.get("Content-Type", "")

            if "mpegurl" in content_type or target_url.endswith(".m3u8"):
                # Rewrite M3U8 URLs to use proxy
                text = resp.content.decode("utf-8")
                new_lines = []

                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        new_lines.append(line)
                    else:
                        absolute_link = urljoin(target_url, line)
                        encoded_headers = base64.b64encode(
                            json.dumps(headers).encode()
                        ).decode()
                        proxy_link = f"{url_for('proxy_stream', _external=True)}?url={quote(absolute_link)}&headers={encoded_headers}&sig={sign_url(absolute_link)}"
                        new_lines.append(proxy_link)

                response = Response(
                    "\n".join(new_lines),
                    mimetype="application/vnd.apple.mpegurl"
                )
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                return response
            else:
                return Response(resp.content, status=resp.status_code, mimetype=content_type)

        except Exception as e:
            logging.error(f"Proxy exception: {e}")
            return str(e), 500


# --- Standard Routes ---

@app.route("/")
@app.route("/home")
async def home():
    manifest_url = url_for("manifest", _external=True).replace("http://", "https://")
    return await render_template("home.html", manifest_url=manifest_url)


@app.route("/logo.png")
async def serve_logo():
    """Serve addon logo."""
    # Return a default or custom logo
    return await send_from_directory(".", "logo.png")


@app.route("/manifest.json")
async def manifest():
    """Stremio addon manifest."""
    channels = await get_all_channels()
    available_categories = sorted(list(set(c.get("category", "other") for c in channels)))

    # Map categories to display names
    category_options = [
        CATEGORIES.get(cat, {"name": cat.title()})["name"]
        for cat in available_categories
    ]

    return jsonify({
        "id": "org.stremio.tvsphere",
        "version": "1.0.0",
        "name": "TV Sphere",
        "description": "Live TV Channels from Multiple Sources",
        "logo": url_for("serve_logo", _external=True),
        "resources": ["catalog", "stream"],
        "types": ["tv"],
        "idPrefixes": ["tv_"],
        "catalogs": [
            {
                "type": "tv",
                "id": "tv_channels",
                "name": "Live TV",
                "extra": [
                    {"name": "genre", "options": category_options},
                    {"name": "search", "isRequired": False}
                ],
            }
        ],
        "behaviorHints": {
            "configurable": True,
            "configurationRequired": False,
        }
    })


@app.route("/catalog/<type>/<id>.json")
@app.route("/catalog/<type>/<id>/genre=<genre>.json")
async def catalog(type: str, id: str, genre: str = None):
    """Return TV channel catalog."""
    if id != "tv_channels":
        return jsonify({"metas": []})

    channels = await get_all_channels()
    metas = []

    for channel in channels:
        if genre:
            cat_name = CATEGORIES.get(channel.get("category", "other"), {"name": "Other"})["name"]
            if cat_name.lower() != genre.lower():
                continue

        category = channel.get("category", "other")
        cat_info = CATEGORIES.get(category, {"name": category.title(), "icon": "📺"})

        metas.append({
            "id": channel["id"],
            "type": "tv",
            "name": channel["name"],
            "poster": channel.get("poster"),
            "description": f"{cat_info['icon']} {cat_info['name']} Channel",
            "genres": [cat_info["name"]],
        })

    return jsonify({"metas": metas})


@app.route("/stream/<type>/<id>.json")
async def stream(type: str, id: str):
    """Return stream URLs for a channel."""
    if not id.startswith("tv_"):
        return jsonify({"streams": []})

    channel_id = id

    try:
        streams = await resolve_channel_stream(channel_id)
    except Exception as e:
        logging.error(f"Stream resolution failed for {channel_id}: {e}")
        return jsonify({"streams": []})

    return jsonify({"streams": streams})


# --- API Routes for Debugging ---

@app.route("/api/channels")
async def api_channels():
    """API endpoint to list all channels (for debugging)."""
    channels = await get_all_channels()
    return jsonify({
        "total": len(channels),
        "channels": channels,
        "last_updated": catalog_cache.get("last_updated", 0),
    })


@app.route("/api/sources")
async def api_sources():
    """API endpoint to list configured sources."""
    return jsonify(TV_SOURCES)


@app.route("/health")
async def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "channels_cached": len(catalog_cache.get("data", [])),
        "streams_cached": len(stream_cache),
    })


if __name__ == "__main__":
    logging.info("Starting TV Sphere addon server...")
    app.run(host="0.0.0.0", port=8000)
