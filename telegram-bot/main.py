import os
import re
import json
import logging
import urllib.request
import asyncio
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WARNINGS_FILE = "telegram-bot/warnings.json"
MAX_WARNINGS = 3

BAD_WORD_URLS = [
    "https://raw.githubusercontent.com/coffee-and-fun/google-profanity-words/main/data/list.txt",
    "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en"
]

bad_words = set()

def load_bad_words() -> set[str]:
    words = set()
    for url in BAD_WORD_URLS:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                text = response.read().decode("utf-8")
                fetched = {line.strip().lower() for line in text.splitlines() if line.strip()}
                words.update(fetched)
                logger.info(f"Loaded {len(fetched)} words from {url}")
        except Exception as e:
            logger.warning(f"Could not fetch word list from {url}: {e}")
    logger.info(f"Total bad words loaded: {len(words)}")
    return words

def contains_bad_word(text: str) -> bool:
    tokens = re.split(r"[^\w]+", text.lower())
    for token in tokens:
        token = token.strip()
        if token and token in bad_words:
            return True
    return False

def load_warnings() -> dict:
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_warnings(data: dict) -> None:
    with open(WARNINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

warnings_data = load_warnings()

def get_warning_key(chat_id: int, user_id: int) -> str:
    return f"{chat_id}:{user_id}"

async def start_command(update: Update, context):
    await update.message.reply_text("Hello! I am Guard Bot. I will keep this group safe from profanity.")

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()

async def handle_message(update: Update, context):
    if not update.message or not update.message.text:
        return
    text = update.message.text
    if contains_bad_word(text):
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        username = update.message.from_user.username or update.message.from_user.first_name
        key = get_warning_key(chat_id, user_id)
        
        warnings = warnings_data.get(key, 0) + 1
        warnings_data[key] = warnings
        save_warnings(warnings_data)
        
        if warnings >= MAX_WARNINGS:
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False)
                )
                await update.message.reply_text(f"🚫 {username} has been muted for reaching the maximum warning limit.")
            except Exception as e:
                logger.warning(f"Could not mute {username}: {e}")
        else:
            await update.message.reply_text(f"⚠️ {username}, please avoid bad words. Warning: {warnings}/{MAX_WARNINGS}")

async def warn_count_command(update: Update, context):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    key = get_warning_key(chat_id, user_id)
    warnings = warnings_data.get(key, 0)
    await update.message.reply_text(f"You have {warnings} warnings.")

async def reset_warnings_command(update: Update, context):
    if update.message.reply_to_message:
        chat_id = update.message.chat_id
        target_user = update.message.reply_to_message.from_user
        key = get_warning_key(chat_id, target_user.id)
        if key in warnings_data:
            del warnings_data[key]
            save_warnings(warnings_data)
        await update.message.reply_text(f"Warnings reset for {target_user.username or target_user.first_name}.")

async def unmute_command(update: Update, context):
    if update.message.reply_to_message:
        chat_id = update.message.chat_id
        target_user = update.message.reply_to_message.from_user
        username = target_user.username or target_user.first_name
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            key = get_warning_key(chat_id, target_user.id)
            if key in warnings_data:
                del warnings_data[key]
                save_warnings(warnings_data)
            await update.message.reply_text(f"✅ {username} has been unmuted.")
        except Exception as e:
            logger.warning(f"Could not unmute {username}: {e}")
            await update.message.reply_text(f"Failed to unmute {username}.")

async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")
    
    global bad_words
    bad_words = load_bad_words()
    if not bad_words:
        logger.warning("No bad words loaded – word lists may be unreachable. Bot will not filter.")
        
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("warnings", warn_count_command))
    app.add_handler(CommandHandler("resetwarnings", reset_warnings_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
    
