# TV Sphere 3.0 - Dockerfile
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install bun
RUN npm install -g bun

# Install streamlink via pip
RUN pip3 install --no-cache-dir --break-system-packages streamlink beautifulsoup4 httpx lxml

WORKDIR /app

# Copy package files
COPY package.json bun.lock ./

# Install dependencies
RUN bun install --frozen-lockfile

# Copy prisma schema first (for generate)
COPY prisma ./prisma

# Generate Prisma client BEFORE building
RUN bunx prisma generate

# Copy source code
COPY . .

# Build the Next.js app
RUN bun run build

# Expose port
EXPOSE 3000

# Set environment variables
ENV NODE_ENV=production
ENV STREAMLINK_PATH=/usr/local/bin/streamlink

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start the app
CMD ["bun", "start"]
