# TV Sphere 3.0 - Dockerfile
# Multi-stage build for smaller image

# Stage 1: Build
FROM node:20-alpine AS builder

# Install bun
RUN npm install -g bun

WORKDIR /app

# Copy package files
COPY package.json bun.lock ./

# Install dependencies
RUN bun install --frozen-lockfile

# Copy source
COPY . .

# Build
RUN bun run build

# Stage 2: Runtime
FROM python:3.11-slim

# Install Node.js and required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    ffmpeg \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install bun and streamlink
RUN npm install -g bun && \
    pip install --no-cache-dir streamlink beautifulsoup4 httpx lxml

WORKDIR /app

# Copy built app from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
COPY --from=builder /app/bun.lock ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/prisma ./prisma

# Copy db
COPY --from=builder /app/db ./db

# Expose port
EXPOSE 3000

# Set environment variables
ENV NODE_ENV=production
ENV STREAMLINK_PATH=/usr/local/bin/streamlink
ENV DATABASE_URL=file:/app/db/tvsphere.db

# Create startup script
RUN echo '#!/bin/sh\nbun run db:push\nbun start' > /start.sh && chmod +x /start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Start the app
CMD ["/start.sh"]
