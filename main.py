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
from typing import Dict, List, Optional
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

# Import scrapers
from scrapers.daddylive import DaddyLiveScraper

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Quart(__name__)
app = cors(app, allow_origin="*")

# --- Environment Variables ---
CACHE_TIMEOUT = int(os.environ.get("CACHE_TIMEOUT", "300"))
STREAM_CACHE_DURATION = int(os.environ.get("STREAM_CACHE_DURATION", "1800"))
SECRET_KEY = os.environ.get("PROXY_SECRET_KEY", "change-me-to-a-real-secret")
MAX_RESOLVERS = int(os.environ.get("MAX_RESOLVERS", "2"))

# --- External API ---
STREAMED_API = "https://streamed.pk/api"

# --- Global Caches ---
catalog_cache: Dict = {}
stream_cache: Dict = {}
catalog_cache_lock = asyncio.Lock()
stream_cache_lock = asyncio.Lock()

# --- TV Channel Categories ---
CATEGORIES = {
    "PPV": {"name": "PPV Events", "icon": "🎟️"},
    "TV Shows": {"name": "TV Shows", "icon": "📺"},
    "Soccer": {"name": "Soccer", "icon": "⚽"},
    "Football": {"name": "Football", "icon": "🏈"},
    "Basketball": {"name": "Basketball", "icon": "🏀"},
    "Tennis": {"name": "Tennis", "icon": "🎾"},
    "Cricket": {"name": "Cricket", "icon": "🏏"},
    "Rugby": {"name": "Rugby", "icon": "🏉"},
    "Hockey": {"name": "Hockey", "icon": "🏒"},
    "Baseball": {"name": "Baseball", "icon": "⚾"},
    "Golf": {"name": "Golf", "icon": "⛳"},
    "Boxing": {"name": "Boxing", "icon": "🥊"},
    "MMA": {"name": "MMA", "icon": "🥋"},
    "Motor Sports": {"name": "Motor Sports", "icon": "🏎️"},
    "Other": {"name": "Other", "icon": "📺"},
}

# --- HTTP Client ---
upstream_client: Optional[httpx.AsyncClient] = None


async def get_client() -> httpx.AsyncClient:
    global upstream_client
    if upstream_client is None:
        upstream_client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
    return upstream_client


@app.after_serving
async def close_client():
    global upstream_client
    if upstream_client:
        await upstream_client.aclose()
        upstream_client = None


# --- Helper Functions ---

def sign_url(url: str) -> str:
    """Generate HMAC-SHA256 signature for proxy URL."""
    return hmac.new(SECRET_KEY.encode(), url.encode(), hashlib.sha256).hexdigest()


# --- Streamed.pk API Integration ---

async def fetch_streamed_events() -> List[Dict]:
    """Fetch live events from Streamed.pk API (like SportsSphere)."""
    try:
        client = await get_client()
        resp = await client.get(f"{STREAMED_API}/matches/all-today", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        
        events = []
        for event in data:
            # Categorize
            cat = event.get("category", "Other")
            if cat not in CATEGORIES:
                cat = "Other"
            
            events.append({
                'id': f"st_{event['id']}",
                'name': event.get("title", "Unknown Event"),
                'category': cat,
                'source': 'streamed',
                'event_id': event['id'],
                'sources': event.get("sources", []),
                'poster': event.get("poster"),
                'date': event.get("date"),
            })
        
        logging.info(f"Fetched {len(events)} events from Streamed.pk")
        return events
    except Exception as e:
        logging.error(f"Error fetching from Streamed.pk: {e}")
        return []


async def get_stream_embeds(event_id: str) -> List[Dict]:
    """Get embed URLs for a Streamed event."""
    try:
        client = await get_client()
        
        # First get event details
        resp = await client.get(f"{STREAMED_API}/matches/all-today", timeout=10.0)
        events = resp.json()
        
        event = next((e for e in events if str(e['id']) == event_id), None)
        if not event or not event.get('sources'):
            return []
        
        embeds = []
        for src in event['sources']:
            source_name = src.get('source')
            source_id = src.get('id')
            
            try:
                api_url = f"{STREAMED_API}/stream/{source_name}/{source_id}"
                resp = await client.get(api_url, timeout=5.0)
                
                if resp.status_code == 200:
                    streams_data = resp.json()
                    for stream_obj in streams_data:
                        embed_url = stream_obj.get('embedUrl')
                        if embed_url:
                            quality = "HD" if stream_obj.get('hd') else "SD"
                            stream_no = stream_obj.get('streamNo', 1)
                            
                            embeds.append({
                                'embed_url': embed_url,
                                'source': source_name,
                                'quality': quality,
                                'stream_no': stream_no,
                                'label': f"{source_name.title()} - Stream {stream_no} ({quality})",
                            })
            except Exception:
                continue
        
        return embeds
    except Exception as e:
        logging.error(f"Error getting embeds: {e}")
        return []


# --- Stream Resolution with Playwright ---

async def resolve_embed_to_m3u8(embed_url: str) -> Optional[Dict]:
    """Use Playwright to resolve embed URL to M3U8."""
    
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    parsed = urlparse(embed_url)
    clean_root = f"{parsed.scheme}://{parsed.netloc}/"
    
    stream_info = {}
    
    try:
        async with async_playwright() as p:
            # Try Chrome first, fallback to Chromium
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    channel="chrome",
                    args=["--no-sandbox", "--disable-gpu", "--mute-audio"],
                )
            except:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-gpu"],
                )
            
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768},
                ignore_https_errors=True,
            )
            
            # Anti-detection
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = window.chrome || {};
            """)
            
            page = await context.new_page()
            
            # Capture M3U8 URLs
            async def handle_request(request):
                if "url" in stream_info:
                    return
                
                url = request.url
                if ".m3u" in url and "http" in url and "narakathegame" not in url:
                    try:
                        headers = await request.all_headers()
                        stream_info['url'] = url
                        stream_info['headers'] = {
                            "User-Agent": user_agent,
                            "Cookie": headers.get("cookie", ""),
                            "Referer": headers.get("referer", embed_url),
                            "Origin": f"{parsed.scheme}://{parsed.netloc}",
                        }
                        stream_info['clean_root'] = clean_root
                    except:
                        pass
            
            page.on("request", handle_request)
            
            try:
                await page.goto(embed_url, wait_until="domcontentloaded", timeout=25000)
                
                # Try to trigger playback
                for _ in range(5):
                    if "url" in stream_info:
                        break
                    
                    # Click play buttons
                    for selector in ["button.vjs-big-play-button", ".play-button", "#player", "video"]:
                        try:
                            await page.locator(selector).first.click(timeout=1000, force=True)
                        except:
                            pass
                    
                    await asyncio.sleep(0.5)
                    
            finally:
                await context.close()
                await browser.close()
                
    except Exception as e:
        logging.error(f"Playwright resolution error: {e}")
    
    return stream_info if "url" in stream_info else None


# --- Channel Aggregation ---

async def get_all_channels() -> List[Dict]:
    """Aggregate channels from all sources."""
    global catalog_cache

    async with catalog_cache_lock:
        current_time = time.time()

        if catalog_cache and (current_time - catalog_cache.get("last_updated", 0) < CACHE_TIMEOUT):
            return catalog_cache["data"]

        all_channels = []

        # Scrape DaddyLive schedule
        try:
            scraper = DaddyLiveScraper()
            await scraper.initialize()
            events = await scraper.get_events()
            channels = scraper.get_channels_from_events(events)
            await scraper.close()
            all_channels.extend(channels)
            logging.info(f"Loaded {len(channels)} events from DaddyLive")
        except Exception as e:
            logging.error(f"Error scraping DaddyLive: {e}")

        # Fetch from Streamed.pk
        try:
            streamed = await fetch_streamed_events()
            all_channels.extend(streamed)
            logging.info(f"Loaded {len(streamed)} events from Streamed.pk")
        except Exception as e:
            logging.error(f"Error fetching Streamed.pk: {e}")

        # Sort by category
        all_channels.sort(key=lambda x: (x.get("category", "Other"), x.get("name", "")))

        catalog_cache = {"last_updated": current_time, "data": all_channels}
        return all_channels


# --- Stream Retrieval ---

async def get_stream_for_event(channel_id: str) -> List[Dict]:
    """Get streams for an event."""
    
    # Check cache
    async with stream_cache_lock:
        cached = stream_cache.get(channel_id)
        if cached and time.time() < cached['expires']:
            return cached['streams']
    
    streams = []
    
    # Handle Streamed.pk events
    if channel_id.startswith("st_"):
        event_id = channel_id[3:]
        embeds = await get_stream_embeds(event_id)
        
        for embed in embeds[:3]:  # Limit attempts
            try:
                result = await resolve_embed_to_m3u8(embed['embed_url'])
                
                if result and 'url' in result:
                    m3u8_url = result['url']
                    headers = result['headers']
                    
                    # Check if proxy is needed
                    needs_proxy = any(d in m3u8_url for d in ['strmd.top', 'delta'])
                    
                    if needs_proxy:
                        headers_b64 = base64.b64encode(json.dumps(headers).encode()).decode()
                        proxy_url = f"{url_for('proxy_stream', _external=True)}?url={quote(m3u8_url)}&headers={headers_b64}&sig={sign_url(m3u8_url)}"
                        
                        streams.append({
                            "title": f"{embed['label']} (Proxy)",
                            "url": proxy_url,
                        })
                    else:
                        streams.append({
                            "title": f"{embed['label']} (Direct)",
                            "url": m3u8_url,
                            "behaviorHints": {
                                "notWebReady": True,
                                "proxyHeaders": {"request": headers},
                            },
                        })
                    
                    if streams:  # Stop after first success
                        break
                        
            except Exception as e:
                logging.error(f"Resolution error: {e}")
                continue
    
    # Cache result
    if streams:
        async with stream_cache_lock:
            stream_cache[channel_id] = {
                'streams': streams,
                'expires': time.time() + STREAM_CACHE_DURATION,
            }
    
    return streams


# --- Proxy Engine ---

@app.route("/proxy")
async def proxy_stream():
    """Proxy M3U8 streams with proper headers."""
    target_url = request.args.get("url")
    headers_b64 = request.args.get("headers")
    sig = request.args.get("sig")

    if not target_url or not headers_b64:
        return "Missing params", 400

    if not sig or not hmac.compare_digest(sig, sign_url(target_url)):
        return "Forbidden", 403

    try:
        headers = json.loads(base64.b64decode(headers_b64).decode("utf-8"))
    except:
        return "Invalid headers", 400

    for key in ["Host", "Content-Length", "Transfer-Encoding", "Connection", "Accept-Encoding"]:
        headers.pop(key, None)

    async with cffi_requests.AsyncSession(impersonate="chrome120") as session:
        try:
            resp = await session.get(target_url, headers=headers)

            if resp.status_code != 200:
                return f"Proxy Error {resp.status_code}", resp.status_code

            content_type = resp.headers.get("Content-Type", "")

            if "mpegurl" in content_type or target_url.endswith(".m3u8"):
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
                        encoded_headers = base64.b64encode(json.dumps(headers).encode()).decode()
                        proxy_link = f"{url_for('proxy_stream', _external=True)}?url={quote(absolute_link)}&headers={encoded_headers}&sig={sign_url(absolute_link)}"
                        new_lines.append(proxy_link)

                response = Response("\n".join(new_lines), mimetype="application/vnd.apple.mpegurl")
                response.headers["Cache-Control"] = "no-cache"
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
    return await send_from_directory(".", "logo.png")


@app.route("/manifest.json")
async def manifest():
    """Stremio addon manifest."""
    channels = await get_all_channels()
    categories = sorted(set(c.get("category", "Other") for c in channels))
    
    return jsonify({
        "id": "org.stremio.tvsphere",
        "version": "1.0.0",
        "name": "TV Sphere",
        "description": "Live TV Events from Multiple Sources",
        "logo": url_for("serve_logo", _external=True),
        "resources": ["catalog", "stream"],
        "types": ["tv"],
        "idPrefixes": ["tv_", "dl_", "st_"],
        "catalogs": [{
            "type": "tv",
            "id": "tv_channels",
            "name": "Live Events",
            "extra": [
                {"name": "genre", "options": [CATEGORIES.get(c, {"name": c})["name"] for c in categories]},
                {"name": "search", "isRequired": False}
            ],
        }],
    })


@app.route("/catalog/<type>/<id>.json")
@app.route("/catalog/<type>/<id>/genre=<genre>.json")
async def catalog(type: str, id: str, genre: str = None):
    """Return event catalog."""
    if id != "tv_channels":
        return jsonify({"metas": []})

    channels = await get_all_channels()
    metas = []

    for channel in channels:
        if genre:
            cat_info = CATEGORIES.get(channel.get("category", "Other"), {"name": "Other"})
            if cat_info["name"].lower() != genre.lower():
                continue

        cat = channel.get("category", "Other")
        cat_info = CATEGORIES.get(cat, {"name": cat, "icon": "📺"})

        metas.append({
            "id": channel["id"],
            "type": "tv",
            "name": channel["name"],
            "poster": channel.get("poster"),
            "description": f"{cat_info['icon']} {channel.get('time', '')} {cat_info['name']}",
            "genres": [cat_info["name"]],
        })

    return jsonify({"metas": metas})


@app.route("/stream/<type>/<id>.json")
async def stream(type: str, id: str):
    """Return stream URLs for an event."""
    streams = await get_stream_for_event(id)
    return jsonify({"streams": streams})


# --- Debug Endpoints ---

@app.route("/api/channels")
async def api_channels():
    channels = await get_all_channels()
    return jsonify({"total": len(channels), "channels": channels})


@app.route("/api/categories")
async def api_categories():
    channels = await get_all_channels()
    cats = {}
    for ch in channels:
        cat = ch.get("category", "Other")
        cats[cat] = cats.get(cat, 0) + 1
    return jsonify(cats)


@app.route("/health")
async def health():
    return jsonify({
        "status": "healthy",
        "channels_cached": len(catalog_cache.get("data", [])),
    })


if __name__ == "__main__":
    logging.info("Starting TV Sphere addon server...")
    app.run(host="0.0.0.0", port=8000)
