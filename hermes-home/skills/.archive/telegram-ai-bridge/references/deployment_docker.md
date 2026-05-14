# Docker Deployment Guide

## Build and Run

```bash
# Build the image
docker build -t hermes-telegram-bridge /root/telegram_skill

# Run with environment variables
docker run -d \
  --name telegram-ai-bridge \
  -e TELEGRAM_BOT_TOKEN="your-token" \
  -e HERMES_API_URL="https://api.hermes.ai/v1/chat" \
  -e HERMES_API_KEY="your-api-key" \
  hermes-telegram-bridge

# View logs
docker logs -f telegram-ai-bridge

# Stop
docker stop telegram-ai-bridge
```

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | `1234567890:ABCdef...` |
| `HERMES_API_URL` | ❌ No | `https://api.hermes.ai/v1/chat` |
| `HERMES_API_KEY` | ❌ No | `your-api-key-here` |

## Docker Compose (Optional)

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  telegram-ai-bridge:
    build: /root/telegram_skill
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - HERMES_API_URL=${HERMES_API_URL:-}
      - HERMES_API_KEY=${HERMES_API_KEY:-}
    restart: unless-stopped
```

Run: `docker-compose up -d`