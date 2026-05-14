# Hermes API Integration Guide

## How It Works

The bot forwards user messages to the Hermes AI API and returns responses automatically.

### Message Flow

```
User → Telegram Bot → Conversation History → Hermes API → AI Response → User via Telegram
```

### API Endpoint

Default: `https://api.hermes.ai/v1/chat`

### Request Format

```json
{
  "messages": [
    {"role": "user", "content": "Hello!", "chat_id": "123", "user_id": 456},
    {"role": "assistant", "content": "Hi there!", ...}
  ],
  "model": "copaw-9b",
  "chat_id": "123"
}
```

### Response Format

```json
{
  "response": "This is the AI's response to the user."
}
```

## Configuration

Set these environment variables:

```bash
export HERMES_API_URL="https://api.hermes.ai/v1/chat"
export HERMES_API_KEY="your-api-key-here"
export HERMES_MODEL="copaw-9b"  # Optional, default is copaw-9b
```

## Testing the API

Test directly with curl:

```bash
curl -X POST "https://api.hermes.ai/v1/chat" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "model": "copaw-9b"
  }'
```

## Demo Mode

If `HERMES_API_KEY` is not set, the bot runs in demo mode with placeholder responses. This is useful for testing the Telegram integration without needing an API key.

To enable full AI functionality:

1. Get your Hermes API key from the Hermes dashboard
2. Set the environment variable before running the bot
3. Restart the bot