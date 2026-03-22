"""
TV Sphere - Stremio Addon for Live TV Channels
Using Streamlink for stream extraction - simple and reliable
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
from urllib.parse import quote, urljoin
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
import streamlink

# Import scrapers
from scrapers.daddylive import DaddyLiveScraper
from scrapers.thai_tv import scrape_thai_channels
from scrapers.australian_tv import scrape_australian_channels

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = Quart(__name__)
app = cors(app, allow_origin="*")

# --- Environment Variables ---
CACHE_TIMEOUT = int(os.environ.get("CACHE_TIMEOUT", "300"))
SECRET_KEY = os.environ.get("PROXY_SECRET_KEY", "change-me-to-a-real-secret")

# --- External API ---
STREAMED_API = "https://streamed.pk/api"

# --- Global Caches ---
catalog_cache: Dict = {}
catalog_cache_lock = asyncio.Lock()

# --- Categories ---
CATEGORIES = {
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
    "Winter Sports": {"name": "Winter Sports", "icon": "⛷️"},
    "Darts": {"name": "Darts", "icon": "🎯"},
    "Snooker": {"name": "Snooker", "icon": "🎱"},
    "Cycling": {"name": "Cycling", "icon": "🚴"},
    "Horse Racing": {"name": "Horse Racing", "icon": "🐴"},
    "TV Shows": {"name": "TV Shows", "icon": "📺"},
    "Thai Entertainment": {"name": "Thai Entertainment", "icon": "🇹🇭"},
    "Thai News": {"name": "Thai News", "icon": "📰"},
    "Australian General": {"name": "Australian General", "icon": "🇦🇺"},
    "Australian News": {"name": "Australian News", "icon": "📰"},
    "Australian Entertainment": {"name": "Australian Entertainment", "icon": "🇦🇺"},
    "Australian Movies": {"name": "Australian Movies", "icon": "🎬"},
    "Australian Comedy": {"name": "Australian Comedy", "icon": "😂"},
    "Australian Kids": {"name": "Australian Kids", "icon": "👶"},
    "Australian Lifestyle": {"name": "Australian Lifestyle", "icon": "🏠"},
    "Australian Indigenous": {"name": "Australian Indigenous", "icon": "🇦🇺"},
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

        all_channels.sort(key=lambda x: (x.get("category", "Other"), x.get("name", "")))

        catalog_cache = {"last_updated": current_time, "data": all_channels}
        logging.info(f"Total channels: {len(all_channels)}")
        return all_channels


# --- Stream Resolution using Streamlink ---

def resolve_stream_streamlink(url: str) -> Optional[str]:
    """
    Use Streamlink to extract the stream URL.
    Much simpler and more reliable than Playwright.
    """
    try:
        logging.info(f"Streamlink resolving: {url}")
        
        # Create streamlink session
        session = streamlink.Streamlink()
        
        # Set options for better compatibility
        session.set_option("http-headers", {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": url,
        })
        
        # Get available streams
        streams = session.streams(url)
        
        if not streams:
            logging.warning(f"No streams found for {url}")
            return None
        
        # Get best quality stream
        if "best" in streams:
            stream_url = streams["best"].url
        elif "720p" in streams:
            stream_url = streams["720p"].url
        elif "480p" in streams:
            stream_url = streams["480p"].url
        else:
            # Get first available
            stream_url = list(streams.values())[0].url
        
        logging.info(f"Streamlink found: {stream_url[:80]}...")
        return stream_url
        
    except Exception as e:
        logging.error(f"Streamlink error: {e}")
        return None


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
                            })
            except:
                continue
        
        return embeds
    except Exception as e:
        logging.error(f"Error getting embeds: {e}")
        return []


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
        "version": "2.0.0",
        "name": "TV Sphere",
        "description": "Live TV from Sports, Thai & Australian channels",
        "logo": url_for("serve_logo", _external=True),
        "resources": ["catalog", "stream", "meta"],
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


@app.route("/meta/<type>/<id>.json")
async def meta(type: str, id: str):
    """Return metadata for a specific channel/event."""
    logging.info(f"Meta request for: {id}")
    channels = await get_all_channels()
    channel = next((c for c in channels if c["id"] == id), None)
    
    if not channel:
        logging.warning(f"Channel not found: {id}")
        return jsonify({"meta": {}})
    
    cat = channel.get("category", "Other")
    cat_info = CATEGORIES.get(cat, {"name": cat, "icon": "📺"})
    
    meta_data = {
        "id": channel["id"],
        "type": "tv",
        "name": channel["name"],
        "description": f"{cat_info['icon']} {cat_info['name']}",
        "genres": [cat_info["name"]],
        "logo": channel.get("logo", ""),
        "runtime": "Live",
        "releaseInfo": "Live Stream",
    }
    
    logging.info(f"Returning meta for: {channel['name']}")
    return jsonify({"meta": meta_data})


@app.route("/stream/<type>/<id>.json")
async def stream(type: str, id: str):
    """Return stream URL using Streamlink."""
    logging.info(f"Stream request for: {id}")
    
    embed_url = None
    
    if id.startswith("st_"):
        event_id = id[3:]
        embeds = await get_stream_embeds(event_id)
        if embeds:
            embed_url = embeds[0]['embed_url']
            logging.info(f"Got embed URL from Streamed.pk: {embed_url}")
            
    elif id.startswith("dl_"):
        channels = await get_all_channels()
        channel = next((c for c in channels if c['id'] == id), None)
        if channel:
            embed_url = channel.get('embed_url')
            logging.info(f"Got embed URL from DaddyLive: {embed_url}")
    
    elif id.startswith("thai_"):
        channels = await get_all_channels()
        channel = next((c for c in channels if c['id'] == id), None)
        if channel:
            embed_url = channel.get('embed_url')
            logging.info(f"Got embed URL for Thai channel: {embed_url}")
    
    elif id.startswith("aus_"):
        channels = await get_all_channels()
        channel = next((c for c in channels if c['id'] == id), None)
        if channel:
            # Australian channels might have direct stream URLs
            stream_url = channel.get('stream_url')
            if stream_url and stream_url.startswith("http"):
                logging.info(f"Direct stream URL for Australian channel: {stream_url}")
                return jsonify({"streams": [{"title": "Live Stream", "url": stream_url}]})
            embed_url = channel.get('embed_url')
    
    if not embed_url:
        logging.warning(f"No embed URL for {id}")
        return jsonify({"streams": []})
    
    # Use Streamlink to resolve (run in thread pool since it's sync)
    loop = asyncio.get_event_loop()
    stream_url = await loop.run_in_executor(None, resolve_stream_streamlink, embed_url)
    
    if not stream_url:
        logging.warning(f"Could not resolve stream for {id}")
        return jsonify({"streams": []})
    
    logging.info(f"Returning stream for {id}: {stream_url[:80]}...")
    
    # Check if it's an M3U8 that needs proxying
    if ".m3u8" in stream_url or "m3u8" in stream_url.lower():
        # Return via proxy to handle CORS and segments
        proxy_url = f"{url_for('proxy_m3u8', _external=True)}?url={quote(stream_url)}&sig={sign_url(stream_url)}"
        return jsonify({"streams": [{"title": "Live Stream", "url": proxy_url}]})
    
    return jsonify({"streams": [{"title": "Live Stream", "url": stream_url}]})


@app.route("/proxy_m3u8")
async def proxy_m3u8():
    """Proxy M3U8 playlists and rewrite segment URLs."""
    target_url = request.args.get("url")
    sig = request.args.get("sig")
    
    if not target_url or not sig:
        return "Missing parameters", 400
    
    if not hmac.compare_digest(sig, sign_url(target_url)):
        return "Forbidden", 403
    
    logging.info(f"Proxying M3U8: {target_url[:80]}...")
    
    try:
        client = await get_client()
        resp = await client.get(target_url)
        
        if resp.status_code != 200:
            logging.error(f"M3U8 fetch failed: {resp.status_code}")
            return f"Upstream error: {resp.status_code}", 502
        
        content = resp.text
        
        # Rewrite segment URLs through proxy
        new_lines = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                # Rewrite URI in EXT-X-KEY
                if "URI=" in line:
                    line = re.sub(
                        r'URI="([^"]+)"',
                        lambda m: f'URI="{url_for("proxy_segment", _external=True)}?url={quote(urljoin(target_url, m.group(1)))}&sig={sign_url(urljoin(target_url, m.group(1)))}"',
                        line
                    )
                new_lines.append(line)
            else:
                # Rewrite segment URL
                abs_url = urljoin(target_url, line)
                proxy_seg_url = f"{url_for('proxy_segment', _external=True)}?url={quote(abs_url)}&sig={sign_url(abs_url)}"
                new_lines.append(proxy_seg_url)
        
        logging.info(f"Returning rewritten M3U8 with {len(new_lines)} lines")
        return Response("\n".join(new_lines), mimetype="application/vnd.apple.mpegurl")
        
    except Exception as e:
        logging.error(f"Proxy error: {e}")
        return str(e), 500


@app.route("/proxy_segment")
async def proxy_segment():
    """Proxy individual segments."""
    target_url = request.args.get("url")
    sig = request.args.get("sig")
    
    if not target_url or not sig:
        return "Missing parameters", 400
    
    if not hmac.compare_digest(sig, sign_url(target_url)):
        return "Forbidden", 403
    
    try:
        client = await get_client()
        resp = await client.get(target_url)
        return Response(resp.content, status=resp.status_code, mimetype=resp.headers.get("Content-Type", "video/MP2T"))
    except Exception as e:
        return str(e), 500


# --- Debug API ---

@app.route("/health")
async def health():
    return jsonify({"status": "healthy", "channels_cached": len(catalog_cache.get("data", []))})


if __name__ == "__main__":
    logging.info("Starting TV Sphere addon server...")
    app.run(host="0.0.0.0", port=8000)
