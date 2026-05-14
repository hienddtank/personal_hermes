---
name: Telegram AI Chat Bridge Skill
description: A complete Telegram bot implementation that acts as a bridge between users and Hermes AI. Messages sent to the bot are automatically forwarded to the AI assistant, and responses are sent back to users via Telegram.
version: "1.0.0"
author: Hermes Agent
category: messaging
platforms: [telegram]
---

# Telegram AI Chat Bridge Skill

A complete Telegram bot implementation that acts as a bridge between users and Hermes AI. Messages sent to the bot are automatically forwarded to the AI assistant, and responses are sent back to users via Telegram.

## Features

- **Message Forwarding**: Automatically forwards user messages to Hermes AI
- **Conversation Memory**: Maintains conversation history for context-aware responses
- **Inline Keyboards**: Interactive buttons (Clear History, Help)
- **User Access Control**: Restrict bot to specific users via environment variable
- **Async Processing**: Efficient concurrent message handling
- **Docker Support**: Ready-to-deploy container image

## Files Structure

```
telegram_skill/
├── extended_bot.py      # Full-featured implementation
├── simplified_bot.py    # Minimal version for quick deployment
├── __init__.py         # Package initialization with session management
├── Dockerfile          # Container configuration
├── requirements.txt     # Python dependencies
├── skill.json          # Skill metadata
├── README.md           # Usage guide
└── DEPLOYMENT.md       # Comprehensive deployment instructions
```

## Quick Start

### 1. Get a Bot Token

Open Telegram → Search `@BotFather` → Send `/newbot` → Follow prompts → Copy token.

### 2. Set Environment Variable

```bash
export TELEGRAM_BOT_TOKEN="your-token-from-botfather"
```

### 3. Run the Bot

**Simplified version (quick start):**
```bash
python telegram_skill/simplified_bot.py
```

**Extended version (full features):**
```bash
python telegram_skill/extended_bot.py
```

### 4. Test It

Send `/start` to your bot on Telegram → You'll see a welcome message with buttons!

## Configuration Options

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | Token from @BotFather |
| `HERMES_API_URL` | ❌ No | Hermes AI API endpoint (for full integration) |
| `HERMES_API_KEY` | ❌ No | Hermes API authentication key |
| `HERMES_MODEL` | ❌ No | Model name (default: copaw-9b) |
| `TELEGRAM_ALLOWED_USERS` | ❌ No | Comma-separated user IDs to allow |

## Deployment Options

### Docker (Recommended)
```bash
docker build -t hermes-telegram-bridge /root/telegram_skill
docker run -e TELEGRAM_BOT_TOKEN="your-token" hermes-telegram-bridge
```

### Heroku
```bash
git push heroku main
# Set config vars in dashboard: TELEGRAM_BOT_TOKEN, HERMES_API_KEY
```

### Railway.app
Create `railway.json` → Push to GitHub → Connect Railway → Deploy

### VPS (Ubuntu)
See `DEPLOYMENT.md` for systemd service setup instructions.

## Commands Available

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with quick action buttons |
| `/help` | Show help text |
| `/clear` | Clear conversation history |

## Hermes API Integration

To enable full AI functionality, configure the environment variables:

```bash
export HERMES_API_URL="https://api.hermes.ai/v1/chat"
export HERMES_API_KEY="your-api-key-here"
export HERMES_MODEL="copaw-9b"  # Optional, default is copaw-9b
```

The bot will automatically forward messages to the Hermes API and return AI responses to users.

## Troubleshooting

### Bot doesn't respond
1. Check if `TELEGRAM_BOT_TOKEN` is set correctly
2. Verify the bot was created with @BotFather successfully
3. Check logs for error messages

### Messages not forwarding to AI
1. Verify `HERMES_API_URL` and `HERMES_API_KEY` are correct
2. Test your API endpoint directly with curl
3. Check network/firewall settings

### Access denied errors
1. If `TELEGRAM_ALLOWED_USERS` is set, verify the user ID
2. Get your own user ID by creating a test bot and checking logs while you talk to it

## Security Considerations

- Never commit tokens to version control
- Use `.gitignore` for sensitive files (`.env`, `*.log`)
- For production, use environment variables or a secrets manager
- Restrict `TELEGRAM_ALLOWED_USERS` in production

## License

This skill is provided as-is for educational and development purposes.