"""
TV Sphere - Stremio Addon for Live TV Channels
A multi-source live TV streaming aggregator for Stremio

Sources:
- DaddyLive (sports events schedule)
- Streamed.pk (sports streams)
- Thai TV (Channel 3, 5, 7, etc.)
- Australian TV (ABC, SBS, Nine, Seven, Ten)
"""
import asyncio
import logging
import time
import base64
import json
import hmac
import hashlib
import os
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
from scrapers.thai_tv import ThaiTVScraper, scrape_thai_channels
from scrapers.australian_tv import scrape_australian_channels

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

# --- External API ---
STREAMED_API = "https://streamed.pk/api"

# --- Global Caches ---
catalog_cache: Dict = {}
stream_cache: Dict = {}
catalog_cache_lock = asyncio.Lock()
stream_cache_lock = asyncio.Lock()

# --- Categories ---
CATEGORIES = {
    # Sports
    "PPV": {"name": "PPV Events", "icon": "🎟️"},
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
    
    # TV Shows
    "TV Shows": {"name": "TV Shows", "icon": "📺"},
    
    # Thai Categories
    "Thai Entertainment": {"name": "Thai Entertainment", "icon": "🇹🇭"},
    "Thai News": {"name": "Thai News", "icon": "📰"},
    "Thai Comedy": {"name": "Thai Comedy", "icon": "😂"},
    "Thai Kids": {"name": "Thai Kids", "icon": "👶"},
    "Thai Lifestyle": {"name": "Thai Lifestyle", "icon": "🏠"},
    "Thai Movies": {"name": "Thai Movies", "icon": "🎬"},
    "Thai Indigenous": {"name": "Thai Indigenous", "icon": "🌏"},
    
    # Australian Categories
    "Australian General": {"name": "Australian General", "icon": "🇦🇺"},
    "Australian News": {"name": "Australian News", "icon": "📰"},
    "Australian Entertainment": {"name": "Australian Entertainment", "icon": "🎬"},
    "Australian Kids": {"name": "Australian Kids", "icon": "👶"},
    "Australian Lifestyle": {"name": "Australian Lifestyle", "icon": "🏠"},
    "Australian Movies": {"name": "Australian Movies", "icon": "🎥"},
    "Australian Comedy": {"name": "Australian Comedy", "icon": "😂"},
    "Australian Indigenous": {"name": "Australian Indigenous", "icon": "🦘"},
    
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/html, */*",
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


# --- Source Scrapers ---

async def fetch_streamed_events() -> List[Dict]:
    """Fetch live events from Streamed.pk API."""
    try:
        client = await get_client()
        resp = await client.get(f"{STREAMED_API}/matches/all-today", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        
        events = []
        for event in data:
            cat = event.get("category", "Other")
            if cat not in CATEGORIES:
                cat = "Other"
            
            events.append({
                'id': f"st_{event['id']}",
                'name': event.get("title", "Unknown"),
                'category': cat,
                'source': 'streamed',
                'event_id': event['id'],
                'sources': event.get("sources", []),
            })
        
        logging.info(f"Fetched {len(events)} events from Streamed.pk")
        return events
    except Exception as e:
        logging.error(f"Error fetching Streamed.pk: {e}")
        return []


async def fetch_daddylive_events() -> List[Dict]:
    """Fetch events from DaddyLive schedule."""
    try:
        scraper = DaddyLiveScraper()
        await scraper.initialize()
        events = await scraper.get_events()
        channels = scraper.get_channels_from_events(events)
        await scraper.close()
        logging.info(f"Fetched {len(channels)} events from DaddyLive")
        return channels
    except Exception as e:
        logging.error(f"Error fetching DaddyLive: {e}")
        return []


async def fetch_thai_channels() -> List[Dict]:
    """Fetch Thai TV channels."""
    try:
        channels = await scrape_thai_channels()
        logging.info(f"Fetched {len(channels)} Thai channels")
        return channels
    except Exception as e:
        logging.error(f"Error fetching Thai channels: {e}")
        return []


async def fetch_australian_channels() -> List[Dict]:
    """Fetch Australian TV channels."""
    try:
        channels = await scrape_australian_channels()
        logging.info(f"Fetched {len(channels)} Australian channels")
        return channels
    except Exception as e:
        logging.error(f"Error fetching Australian channels: {e}")
        return []


# --- Channel Aggregation ---

async def get_all_channels() -> List[Dict]:
    """Aggregate channels from all sources."""
    global catalog_cache

    async with catalog_cache_lock:
        current_time = time.time()

        if catalog_cache and (current_time - catalog_cache.get("last_updated", 0) < CACHE_TIMEOUT):
            return catalog_cache["data"]

        all_channels = []

        # Run all scrapers concurrently
        results = await asyncio.gather(
            fetch_daddylive_events(),
            fetch_streamed_events(),
            fetch_thai_channels(),
            fetch_australian_channels(),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, list):
                all_channels.extend(result)
            elif isinstance(result, Exception):
                logging.error(f"Scraper error: {result}")

        # Sort by category
        all_channels.sort(key=lambda x: (x.get("category", "Other"), x.get("name", "")))

        catalog_cache = {"last_updated": current_time, "data": all_channels}
        logging.info(f"Total channels: {len(all_channels)}")
        return all_channels


# --- Stream Resolution ---

async def get_stream_embeds(event_id: str) -> List[Dict]:
    """Get embed URLs for a Streamed event."""
    try:
        client = await get_client()
        resp = await client.get(f"{STREAMED_API}/matches/all-today", timeout=10.0)
        events = resp.json()
        
        event = next((e for e in events if str(e['id']) == event_id), None)
        if not event or not event.get('sources'):
            return []
        
        embeds = []
        for src in event['sources']:
            try:
                api_url = f"{STREAMED_API}/stream/{src['source']}/{src['id']}"
                resp = await client.get(api_url, timeout=5.0)
                
                if resp.status_code == 200:
                    for stream in resp.json():
                        if stream.get('embedUrl'):
                            embeds.append({
                                'embed_url': stream['embedUrl'],
                                'source': src['source'],
                                'quality': "HD" if stream.get('hd') else "SD",
                                'stream_no': stream.get('streamNo', 1),
                            })
            except:
                continue
        
        return embeds
    except Exception as e:
        logging.error(f"Error getting embeds: {e}")
        return []


async def resolve_m3u8(embed_url: str) -> Optional[Dict]:
    """Resolve embed to M3U8 using Playwright."""
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    stream_info = {}
    
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True, channel="chrome", args=["--no-sandbox"])
            except:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            
            context = await browser.new_context(user_agent=user_agent, ignore_https_errors=True)
            page = await context.new_page()
            
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
                            "Referer": headers.get("referer", embed_url),
                        }
                    except:
                        pass
            
            page.on("request", handle_request)
            
            try:
                await page.goto(embed_url, wait_until="domcontentloaded", timeout=25000)
                
                for _ in range(5):
                    if "url" in stream_info:
                        break
                    for sel in ["button.vjs-big-play-button", ".play-button", "#player"]:
                        try:
                            await page.locator(sel).first.click(timeout=1000, force=True)
                        except:
                            pass
                    await asyncio.sleep(0.5)
            finally:
                await context.close()
                await browser.close()
                
    except Exception as e:
        logging.error(f"Playwright error: {e}")
    
    return stream_info if "url" in stream_info else None


async def get_stream_for_channel(channel_id: str) -> List[Dict]:
    """Get streams for a channel."""
    
    # Check cache
    async with stream_cache_lock:
        cached = stream_cache.get(channel_id)
        if cached and time.time() < cached['expires']:
            return cached['streams']
    
    streams = []
    
    # Streamed.pk events
    if channel_id.startswith("st_"):
        event_id = channel_id[3:]
        embeds = await get_stream_embeds(event_id)
        
        for embed in embeds[:3]:
            try:
                result = await resolve_m3u8(embed['embed_url'])
                if result and 'url' in result:
                    streams.append({
                        "title": f"{embed['source'].title()} - Stream {embed['stream_no']} ({embed['quality']})",
                        "url": result['url'],
                        "behaviorHints": {"notWebReady": True, "proxyHeaders": {"request": result['headers']}},
                    })
                    break
            except:
                continue
    
    # Thai channels
    elif channel_id.startswith("thai_"):
        # Return the stream page URL (needs resolution at play time)
        channels = await scrape_thai_channels()
        channel = next((c for c in channels if c['id'] == channel_id), None)
        if channel:
            streams.append({
                "title": f"{channel['name']} (Thai)",
                "url": channel.get('stream_url', ''),
                "description": "Thai TV - may require geolocation",
            })
    
    # Australian channels  
    elif channel_id.startswith("aus_"):
        channels = await scrape_australian_channels()
        channel = next((c for c in channels if c['id'] == channel_id), None)
        if channel:
            streams.append({
                "title": f"{channel['name']} (Australia)",
                "url": channel.get('stream_url', '#'),
                "description": "Australian TV - requires Australian IP",
            })
    
    # Cache
    if streams:
        async with stream_cache_lock:
            stream_cache[channel_id] = {'streams': streams, 'expires': time.time() + STREAM_CACHE_DURATION}
    
    return streams


# --- Proxy Engine ---

@app.route("/proxy")
async def proxy_stream():
    """Proxy M3U8 streams."""
    target_url = request.args.get("url")
    headers_b64 = request.args.get("headers")
    sig = request.args.get("sig")

    if not target_url:
        return "Missing URL", 400
    if not sig or not hmac.compare_digest(sig, sign_url(target_url)):
        return "Forbidden", 403

    try:
        headers = json.loads(base64.b64decode(headers_b64).decode()) if headers_b64 else {}
    except:
        headers = {}

    for key in ["Host", "Content-Length", "Transfer-Encoding", "Connection"]:
        headers.pop(key, None)

    async with cffi_requests.AsyncSession(impersonate="chrome120") as session:
        try:
            resp = await session.get(target_url, headers=headers)
            
            if "mpegurl" in resp.headers.get("Content-Type", "") or target_url.endswith(".m3u8"):
                text = resp.content.decode("utf-8")
                new_lines = []
                
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        new_lines.append(line)
                    else:
                        abs_url = urljoin(target_url, line)
                        h_b64 = base64.b64encode(json.dumps(headers).encode()).decode()
                        proxy_url = f"{url_for('proxy_stream', _external=True)}?url={quote(abs_url)}&headers={h_b64}&sig={sign_url(abs_url)}"
                        new_lines.append(proxy_url)
                
                return Response("\n".join(new_lines), mimetype="application/vnd.apple.mpegurl")
            
            return Response(resp.content, status=resp.status_code, mimetype=resp.headers.get("Content-Type", ""))
            
        except Exception as e:
            return str(e), 500


# --- Routes ---

@app.route("/")
async def home():
    manifest_url = url_for("manifest", _external=True).replace("http://", "https://")
    return await render_template("home.html", manifest_url=manifest_url)


@app.route("/logo.png")
async def serve_logo():
    return await send_from_directory(".", "logo.png")


@app.route("/manifest.json")
async def manifest():
    channels = await get_all_channels()
    categories = sorted(set(c.get("category", "Other") for c in channels))
    
    return jsonify({
        "id": "org.stremio.tvsphere",
        "version": "1.1.0",
        "name": "TV Sphere",
        "description": "Live TV from Sports, Thai & Australian channels",
        "logo": url_for("serve_logo", _external=True),
        "resources": ["catalog", "stream"],
        "types": ["tv"],
        "idPrefixes": ["tv_", "dl_", "st_", "thai_", "aus_"],
        "catalogs": [{
            "type": "tv",
            "id": "tv_channels",
            "name": "Live TV",
            "extra": [
                {"name": "genre", "options": [CATEGORIES.get(c, {"name": c})["name"] for c in categories]},
                {"name": "search", "isRequired": False}
            ],
        }],
    })


@app.route("/catalog/<type>/<id>.json")
@app.route("/catalog/<type>/<id>/genre=<genre>.json")
async def catalog(type: str, id: str, genre: str = None):
    if id != "tv_channels":
        return jsonify({"metas": []})

    channels = await get_all_channels()
    metas = []

    for ch in channels:
        if genre:
            cat_info = CATEGORIES.get(ch.get("category", "Other"), {"name": "Other"})
            if cat_info["name"].lower() != genre.lower():
                continue

        cat = ch.get("category", "Other")
        cat_info = CATEGORIES.get(cat, {"name": cat, "icon": "📺"})

        metas.append({
            "id": ch["id"],
            "type": "tv",
            "name": ch["name"],
            "description": f"{cat_info['icon']} {cat_info['name']}",
            "genres": [cat_info["name"]],
        })

    return jsonify({"metas": metas})


@app.route("/stream/<type>/<id>.json")
async def stream(type: str, id: str):
    streams = await get_stream_for_channel(id)
    return jsonify({"streams": streams})


# --- Debug API ---

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
    return jsonify({"status": "healthy", "channels_cached": len(catalog_cache.get("data", []))})


if __name__ == "__main__":
    logging.info("Starting TV Sphere addon server...")
    app.run(host="0.0.0.0", port=8000)
