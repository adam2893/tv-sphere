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
CACHE_TIMEOUT = int(os.environ.get("CACHE_TIMEOUT", "300"))  # 5 minutes
STREAM_CACHE_DURATION = int(os.environ.get("STREAM_CACHE_DURATION", "1800"))  # 30 minutes
SECRET_KEY = os.environ.get("PROXY_SECRET_KEY", "change-me-to-a-real-secret")
MAX_CONCURRENT_RESOLVERS = int(os.environ.get("MAX_CONCURRENT_RESOLVERS", "2"))

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

# --- Helper Functions ---

def sign_url(url: str) -> str:
    """Generate an HMAC-SHA256 signature for a proxy URL."""
    return hmac.new(SECRET_KEY.encode(), url.encode(), hashlib.sha256).hexdigest()


# --- Channel Aggregation ---

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

        # Scrape DaddyLive
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

        # Sort by category and time
        all_channels.sort(key=lambda x: (x.get("category", "Other"), x.get("time", "")))

        catalog_cache = {"last_updated": current_time, "data": all_channels}
        return all_channels


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
    return await send_from_directory(".", "logo.png")


@app.route("/manifest.json")
async def manifest():
    """Stremio addon manifest."""
    channels = await get_all_channels()
    available_categories = sorted(list(set(c.get("category", "Other") for c in channels)))

    category_options = [
        CATEGORIES.get(cat, {"name": cat})["name"]
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
        "idPrefixes": ["tv_", "dl_"],
        "catalogs": [
            {
                "type": "tv",
                "id": "tv_channels",
                "name": "Live Events",
                "extra": [
                    {"name": "genre", "options": category_options},
                    {"name": "search", "isRequired": False}
                ],
            }
        ],
        "behaviorHints": {
            "configurable": False,
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
            cat_info = CATEGORIES.get(channel.get("category", "Other"), {"name": "Other"})
            if cat_info["name"].lower() != genre.lower():
                continue

        category = channel.get("category", "Other")
        cat_info = CATEGORIES.get(category, {"name": category, "icon": "📺"})

        metas.append({
            "id": channel["id"],
            "type": "tv",
            "name": channel["name"],
            "poster": None,
            "description": f"{cat_info['icon']} {channel.get('time', '')} {cat_info['name']}",
            "genres": [cat_info["name"]],
        })

    return jsonify({"metas": metas})


@app.route("/stream/<type>/<id>.json")
async def stream(type: str, id: str):
    """Return stream URLs for a channel."""
    # For now, return a placeholder
    # Real implementation would need embed URL resolution
    return jsonify({
        "streams": [
            {
                "title": "Stream (Click to Load)",
                "url": "#",
                "description": "Stream resolution requires Playwright browser"
            }
        ]
    })


# --- API Routes for Debugging ---

@app.route("/api/channels")
async def api_channels():
    """API endpoint to list all channels."""
    channels = await get_all_channels()
    return jsonify({
        "total": len(channels),
        "channels": channels,
        "last_updated": catalog_cache.get("last_updated", 0),
    })


@app.route("/api/categories")
async def api_categories():
    """API endpoint to list categories."""
    channels = await get_all_channels()
    cats = {}
    for ch in channels:
        cat = ch.get("category", "Other")
        cats[cat] = cats.get(cat, 0) + 1
    
    return jsonify(cats)


@app.route("/health")
async def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "channels_cached": len(catalog_cache.get("data", [])),
    })


if __name__ == "__main__":
    logging.info("Starting TV Sphere addon server...")
    app.run(host="0.0.0.0", port=8000)
