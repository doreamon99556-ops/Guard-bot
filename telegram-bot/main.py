import os
import re
import json
import logging
import urllib.request

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WARNINGS_FILE = "telegram-bot/warnings.json"
MAX_WARNINGS = 3

BAD_WORD_URLS = [
    "https://raw.githubusercontent.com/coffee-and-fun/google-profanity-words/main/data/en.txt",
    "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/hi",
]

bad_words: set[str] = set()


def load_bad_words() -> set[str]:
    words: set[str] = set()
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    if message.chat.type not in ("group", "supergroup"):
        return

    if not contains_bad_word(message.text):
        return

    user = message.from_user
    chat_id = message.chat_id
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        logger.info(f"Deleted message from {username} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")
        return

    key = get_warning_key(chat_id, user_id)
    warnings_data[key] = warnings_data.get(key, 0) + 1
    save_warnings(warnings_data)

    count = warnings_data[key]

    if count >= MAX_WARNINGS:
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🔇 {username} has been muted after reaching {MAX_WARNINGS} warnings "
                    f"for using inappropriate language."
                ),
            )
            logger.info(f"Muted {username} in chat {chat_id}")
        except Exception as e:
            logger.warning(f"Could not mute user {username}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ Warning {count}/{MAX_WARNINGS} for {username}: "
                    f"Your message was removed. (Note: I need admin rights to mute users.)"
                ),
            )
    else:
        remaining = MAX_WARNINGS - count
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⚠️ Warning {count}/{MAX_WARNINGS} for {username}: "
                f"Your message was removed for containing inappropriate language. "
                f"{remaining} more warning(s) before you are muted."
            ),
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    if message.chat.type != "private":
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ My Features", callback_data="features"),
            InlineKeyboardButton("📖 How to Use", callback_data="howto"),
        ]
    ])

    await message.reply_text(
        "👋 Hello! I am *Guard Bot*.\n\n"
        "My job is to protect your groups from abusive language and bad words. "
        "I silently watch every message, delete anything inappropriate, and warn repeat offenders automatically.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "features":
        await query.edit_message_text(
            "✨ *My Features*\n\n"
            "🗑 *Deletes bad words* — Any message containing abusive or inappropriate language is removed instantly.\n\n"
            "⚠️ *Warns users* — The offender gets a public warning (1/3, 2/3, 3/3) so the group knows.\n\n"
            "🔇 *Mutes after 3 strikes* — If a user hits 3 warnings, they are muted and can no longer send messages.\n\n"
            "🌐 *English + Hindi filtering* — I check against a combined list of 1,000+ English and Hindi/Hinglish bad words, downloaded automatically.\n\n"
            "🛡 *Admin commands* — Admins can check warnings, reset them, or manually unmute a user at any time.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ]),
        )

    elif query.data == "howto":
        await query.edit_message_text(
            "📖 *How to Use Guard Bot*\n\n"
            "1️⃣ Add me to your Telegram group.\n\n"
            "2️⃣ Open group *Settings → Administrators* and promote me to admin.\n\n"
            "3️⃣ Make sure I have these two permissions:\n"
            "   • ✅ *Delete Messages*\n"
            "   • ✅ *Restrict Members*\n\n"
            "4️⃣ That's it! I will start moderating immediately — no setup needed.\n\n"
            "💡 Without admin rights I cannot delete messages or mute users.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back")]
            ]),
        )

    elif query.data == "back":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✨ My Features", callback_data="features"),
                InlineKeyboardButton("📖 How to Use", callback_data="howto"),
            ]
        ])
        await query.edit_message_text(
            "👋 Hello! I am *Guard Bot*.\n\n"
            "My job is to protect your groups from abusive language and bad words. "
            "I silently watch every message, delete anything inappropriate, and warn repeat offenders automatically.",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


async def warn_count_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.reply_text("This command only works in groups.")
        return

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        target_user = message.from_user

    key = get_warning_key(message.chat_id, target_user.id)
    count = warnings_data.get(key, 0)
    username = f"@{target_user.username}" if target_user.username else target_user.first_name
    await message.reply_text(f"{username} has {count}/{MAX_WARNINGS} warning(s).")


async def reset_warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.reply_text("This command only works in groups.")
        return

    admins = await context.bot.get_chat_administrators(message.chat_id)
    admin_ids = {admin.user.id for admin in admins}
    if message.from_user.id not in admin_ids:
        await message.reply_text("Only admins can reset warnings.")
        return

    if not message.reply_to_message:
        await message.reply_text("Reply to a user's message to reset their warnings.")
        return

    target_user = message.reply_to_message.from_user
    key = get_warning_key(message.chat_id, target_user.id)
    username = f"@{target_user.username}" if target_user.username else target_user.first_name

    if key in warnings_data:
        del warnings_data[key]
        save_warnings(warnings_data)
        await message.reply_text(f"✅ Warnings for {username} have been reset.")
    else:
        await message.reply_text(f"{username} has no warnings to reset.")


async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.reply_text("This command only works in groups.")
        return

    admins = await context.bot.get_chat_administrators(message.chat_id)
    admin_ids = {admin.user.id for admin in admins}
    if message.from_user.id not in admin_ids:
        await message.reply_text("Only admins can unmute users.")
        return

    if not message.reply_to_message:
        await message.reply_text("Reply to a user's message to unmute them.")
        return

    target_user = message.reply_to_message.from_user
    username = f"@{target_user.username}" if target_user.username else target_user.first_name

    try:
        await context.bot.restrict_chat_member(
            chat_id=message.chat_id,
            user_id=target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        key = get_warning_key(message.chat_id, target_user.id)
        if key in warnings_data:
            del warnings_data[key]
            save_warnings(warnings_data)
        await message.reply_text(f"✅ {username} has been unmuted and their warnings have been cleared.")
    except Exception as e:
        logger.warning(f"Could not unmute {username}: {e}")
        await message.reply_text(f"Failed to unmute {username}. Make sure I have admin rights.")


async def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    global bad_words
    bad_words = load_bad_words()
    if not bad_words:
        logger.warning("No bad words loaded — word lists may be unreachable. Bot will not filter anything.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("warnings", warn_count_command))
    app.add_handler(CommandHandler("resetwarnings", reset_warnings_command))
    app.add_handler(CommandHandler("unmute", unmute_command)
                        await app.run_polling(allowed_updates=Update.ALL_TYPES)
    
import asyncio

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(main)
    
