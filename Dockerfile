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

# Copy prisma schema first
COPY prisma ./prisma

# Generate Prisma client
RUN bunx prisma generate

# Copy source code
COPY . .

# Build the Next.js app
RUN bun run build

# Create startup script that initializes DB before starting
RUN echo '#!/bin/sh' > /start.sh && \
    echo 'echo "Initializing database..."' >> /start.sh && \
    echo 'bunx prisma db push --skip-generate' >> /start.sh && \
    echo 'echo "Starting server..."' >> /start.sh && \
    echo 'bun start' >> /start.sh && \
    chmod +x /start.sh

# Expose port
EXPOSE 3000

# Set environment variables
ENV NODE_ENV=production
ENV STREAMLINK_PATH=/usr/local/bin/streamlink

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start the app
CMD ["/start.sh"]
