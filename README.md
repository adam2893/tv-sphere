# TV Sphere 3.0

A web-based Streamlink GUI for extracting and managing IPTV streams. Perfect for deployment on home servers like Unraid.

## Features

- **Stream Extraction**: Enter any URL and automatically detect the appropriate Streamlink plugin
- **Plugin Browser**: Browse all 300+ supported streaming plugins
- **Credential Management**: Store login credentials for authenticated services (10play, etc.)
- **Playlist Management**: Create and manage IPTV playlists
- **M3U Export**: Export playlists as M3U files for any IPTV player
- **Dark Mode UI**: Modern, responsive interface

## Supported Sites

Streamlink supports 300+ streaming sites including:
- Twitch
- YouTube
- Vimeo
- Dailymotion
- Facebook
- 10Play Australia (with credentials)
- BBC iPlayer
- And many more...

## Quick Start

### Docker (Recommended)

```bash
docker run -d \
  --name tv-sphere \
  -p 7401:3000 \
  -v tvsphere_data:/app/db \
  adam28693/tv-sphere:latest
```

### Docker Compose

```yaml
version: "3.8"
services:
  tv-sphere:
    image: adam28693/tv-sphere:latest
    ports:
      - "7401:3000"
    volumes:
      - tvsphere_data:/app/db
```

### Unraid

1. Go to Apps tab in Unraid
2. Search for "tv-sphere" or add custom repository
3. Configure port (default: 7401) and paths
4. Start container

## Usage

1. **Extract Stream**:
   - Enter a streaming URL
   - Click "Detect" to identify the plugin
   - If auth is required, enter credentials
   - Click "Resolve Stream" to get stream URLs
   - Copy or open stream URL in your player

2. **Manage Credentials**:
   - Store login info for services that require authentication
   - Credentials are encrypted in the database

3. **Create Playlists**:
   - Add channels to playlists
   - Export as M3U for use in VLC, TiviMate, etc.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `file:/app/db/tvsphere.db` |
| `STREAMLINK_PATH` | Path to streamlink binary | `/usr/local/bin/streamlink` |

## API Endpoints

- `GET /api/plugins` - List all available plugins
- `POST /api/detect` - Detect plugin for a URL
- `POST /api/resolve` - Resolve stream URLs
- `GET/POST/DELETE /api/credentials` - Manage stored credentials
- `GET/POST/PUT/DELETE /api/playlists` - Manage playlists
- `GET /api/m3u` - Generate M3U playlist

## Development

```bash
# Install dependencies
bun install

# Run development server
bun dev

# Build for production
bun build
```

## Tech Stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS, shadcn/ui
- **Backend**: Next.js API Routes, Prisma ORM
- **Stream Extraction**: Streamlink (Python)
- **Database**: SQLite

## License

MIT License - For educational purposes only.

## Disclaimer

This tool is for educational purposes. Users are responsible for complying with the terms of service of streaming platforms. The authors are not responsible for any misuse of this software.
