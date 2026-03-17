# 📺 TV Sphere - Stremio Addon for Live TV

A self-hosted Stremio addon that aggregates live TV channels from multiple streaming sources and delivers them directly within Stremio.

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📡 **Multi-Source Aggregation** | Collects channels from DaddyLive, Streamed, and more |
| 🎬 **Auto-Categorization** | Channels automatically sorted into News, Sports, Movies, Kids, etc. |
| 🚀 **Smart Caching** | 5-minute catalog cache, 30-minute stream cache |
| 🔧 **Built-in Proxy** | Bypasses CORS and referrer restrictions |
| 🔐 **HMAC URL Signing** | Protects your proxy from unauthorized use |
| 🐳 **Docker Ready** | One-command deployment |

## 🏗️ Architecture

```
┌─────────────┐       ┌─────────────────────────┐       ┌────────────────┐
│   Stremio    │◄─────►│    TV Sphere Server      │◄─────►│  DaddyLive     │
│   Client     │       │   (Quart + Playwright)   │       │  Streamed.pk   │
└─────────────┘       └───────────┬───────────────┘       │  More...       │
                                  │                       └────────────────┘
                          ┌───────▼───────┐
                          │  Proxy Engine │
                          │  (curl-cffi)  │
                          └───────────────┘
```

## 📋 Prerequisites

### For Docker Setup
- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/)

### For Python Setup
- Python 3.10+
- pip
- Git

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/tv-sphere.git
cd tv-sphere

# Create environment file
cp .env.example .env
# Edit .env and set your PROXY_SECRET_KEY

# Build and run
docker-compose up -d --build

# Verify it's running
curl http://localhost:8000/manifest.json
```

### Option 2: Python Direct

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/tv-sphere.git
cd tv-sphere

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .\.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set environment
export PROXY_SECRET_KEY="your-secret-key-here"

# Run
python main.py
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_SECRET_KEY` | *required* | HMAC signing key for proxy URLs |
| `PORT` | 8000 | Server port |
| `CACHE_TIMEOUT` | 300 | Channel list cache duration (seconds) |
| `STREAM_CACHE_DURATION` | 1800 | Resolved stream cache duration |
| `MAX_CONCURRENT_RESOLVERS` | 2 | Max parallel stream resolutions |

### Adding New Sources

Edit `TV_SOURCES` in `main.py`:

```python
TV_SOURCES = {
    "daddylive": {
        "name": "DaddyLive",
        "base_url": "https://daddylive.mp",
        "channels_path": "/24-7-channels.php",
        "enabled": True,
    },
    "your_source": {
        "name": "Your Source",
        "base_url": "https://example.com",
        "channels_path": "/channels",
        "enabled": True,
    },
}
```

Then implement a scraper function:

```python
async def scrape_your_source_channels() -> List[Dict]:
    """Scrape channels from your source."""
    channels = []
    # Your scraping logic here
    return channels
```

Add it to `get_all_channels()`:

```python
tasks = [
    scrape_daddylive_channels(),
    scrape_streamed_channels(),
    scrape_your_source_channels(),  # Add here
]
```

## 📺 Installing in Stremio

1. Start your TV Sphere server
2. Open Stremio
3. Go to **Settings → Addons**
4. Paste your manifest URL: `http://YOUR_IP:8000/manifest.json`
5. Click **Install**
6. Browse channels in the "Live TV" catalog

### For Remote Access

Use a reverse proxy with HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name tv-sphere.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🔧 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Landing page |
| `GET /manifest.json` | Stremio addon manifest |
| `GET /catalog/tv/tv_channels.json` | Channel list |
| `GET /stream/tv/{channel_id}.json` | Stream URLs |
| `GET /proxy` | Stream proxy |
| `GET /api/channels` | Debug: All channels |
| `GET /health` | Health check |

## 🛠️ Troubleshooting

### No streams appearing
- Check logs: `docker logs -f tv-sphere`
- Source might have changed - update scraper selectors
- Try increasing `PER_EMBED_TIMEOUT`

### Playwright errors
```bash
# Reinstall browsers
playwright install chromium
playwright install-deps chromium
```

### High memory usage
- Reduce `MAX_CONCURRENT_RESOLVERS`
- Playwright uses ~500MB per browser instance
- Minimum recommended RAM: 2GB

### 403 Forbidden on streams
- Verify `PROXY_SECRET_KEY` is set consistently
- Clear caches by restarting the server

## 📁 Project Structure

```
tv-sphere/
├── main.py              # Main application
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose config
├── .env.example         # Environment template
├── templates/
│   └── home.html        # Landing page template
├── cache/               # Cache directory (created at runtime)
└── README.md            # This file
```

## ⚠️ Legal Disclaimer

This addon is for **personal, educational use only**. The developers:
- Do NOT host, store, or distribute any media content
- Are NOT responsible for how this software is used
- Make NO guarantees about stream availability or quality

All streams are sourced from publicly available third-party websites. Users are responsible for complying with their local laws and the terms of service of streaming websites.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Open a Pull Request

## 📝 License

Provided as-is for personal and educational use. No warranty provided.

---

<p align="center">
  Made with ❤️ for the Stremio community
</p>
