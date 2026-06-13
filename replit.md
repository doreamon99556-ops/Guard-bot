# Telegram Group Moderation Bot

A Python Telegram bot that monitors group messages for profanity, issues warnings, and mutes repeat offenders.

## Run & Operate

- `python3 telegram-bot/main.py` — run the bot (managed via "Telegram Bot" workflow)
- `python3 -m pip install -r telegram-bot/requirements.txt` — install/update Python dependencies
- Required secret: `TELEGRAM_BOT_TOKEN` — get from @BotFather on Telegram

## Stack

- Python 3.11
- `python-telegram-bot` v21 (async, polling)
- `better-profanity` — profanity detection
- JSON file for warning persistence (`telegram-bot/warnings.json`)

## Where things live

- `telegram-bot/main.py` — all bot logic (handlers, commands)
- `telegram-bot/requirements.txt` — Python dependencies
- `telegram-bot/warnings.json` — auto-created; persists per-user warning counts keyed by `chat_id:user_id`

## Bot Commands

| Command | Who can use | Description |
|---|---|---|
| `/warnings` | Anyone | Show your own warning count (or reply to see another user's) |
| `/resetwarnings` | Admins only | Reply to a user's message to clear their warnings |
| `/unmute` | Admins only | Reply to a user's message to unmute them and clear warnings |

## How It Works

1. Every group message is checked for profanity using `better-profanity`
2. If profanity is detected, the message is deleted and a warning is sent
3. After 3 warnings, the user is muted (`can_send_messages=False`)
4. The bot must be added as an **admin** with Delete Messages + Restrict Members permissions

## Architecture decisions

- Warnings are stored in a flat JSON file (`chat_id:user_id` keys) — simple and portable, no DB needed
- Bot uses async polling (no webhook) — easier to run without a public HTTPS endpoint
- Admin-only commands check Telegram's `get_chat_administrators` list at call time

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- The bot **must be an admin** in the group with "Delete messages" and "Restrict members" permissions — without admin rights it cannot delete messages or mute users
- `better-profanity` uses a built-in English word list; custom words can be added via `profanity.add_censor_words([...])`
- `warnings.json` resets if the file is deleted; for production use consider a database instead
