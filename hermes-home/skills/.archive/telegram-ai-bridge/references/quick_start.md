# Quick Start Guide - Telegram AI Chat Bridge

## 30-Second Setup

1. **Get token** from @BotFather on Telegram
2. **Set env var:** `export TELEGRAM_BOT_TOKEN="your-token"`
3. **Run:** `python telegram_skill/simplified_bot.py`
4. **Done!** Send `/start` to test.

## Full Features (Optional)

For conversation memory and Hermes AI integration:

```bash
export HERMES_API_URL="https://api.hermes.ai/v1/chat"
export HERMES_API_KEY="your-api-key"
python telegram_skill/extended_bot.py
```

## Commands

- `/start` - Welcome with buttons
- `/help` - Help text
- `/clear` - Clear history