import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration (Set these values) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID")) # Your Telegram User ID
LONG_MESSAGE_THRESHOLD = 500  # Characters
DELETE_AFTER_SECONDS = 600 # 10 minutes * 60 seconds/minute

# Store messages to be deleted
messages_to_delete = {} # {chat_id: {message_id: timestamp}}

# --- Helper Functions ---

# Decorator to restrict access to admin
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("You are not authorized to use this command.")
            return
        await func(update, context)
    return wrapper

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Visit My Website", url="https://example.com")]] # Replace with your URL
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to the group! I'm your group management bot. "
        "I'll help keep things tidy here.",
        reply_markup=reply_markup
    )

# --- Message Handlers ---

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.message.chat_id
    message_id = update.message.message_id
    text = update.message.text

    # 1. Store message for auto-deletion
    if chat_id not in messages_to_delete:
        messages_to_delete[chat_id] = {}
    messages_to_delete[chat_id][message_id] = update.message.date.timestamp()

    # 2. Check for long messages
    if text and len(text) > LONG_MESSAGE_THRESHOLD:
        await update.message.reply_text(
            f"Please keep your messages concise, {update.effective_user.mention_html()}! "
            f"Long messages can be difficult to read.",
            parse_mode='HTML'
        )

    # 3. Check for messages with usernames (e.g., @username)
    if text and "@" in text:
        # A simple regex could be more robust here to check for actual usernames
        # For now, a basic check:
        words = text.split()
        for word in words:
            if word.startswith('@') and len(word) > 1: # Basic check for potential username
                try:
                    await update.message.delete()
                    logger.info(f"Deleted message containing username from {update.effective_user.username}")
                except Exception as e:
                    logger.error(f"Could not delete message with username: {e}")
                break # Only delete once even if multiple usernames

# --- Auto-deletion Logic ---
async def auto_delete_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_time = asyncio.get_event_loop().time()
    for chat_id in list(messages_to_delete.keys()):
        for message_id, timestamp in list(messages_to_delete[chat_id].items()):
            if current_time - timestamp > DELETE_AFTER_SECONDS:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                    logger.info(f"Auto-deleted message {message_id} in chat {chat_id}")
                except Exception as e:
                    logger.error(f"Could not auto-delete message {message_id} in chat {chat_id}: {e}")
                finally:
                    del messages_to_delete[chat_id][message_id]
        if not messages_to_delete[chat_id]:
            del messages_to_delete[chat_id]

# --- Main function ---
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    # Schedule auto-deletion
    job_queue = application.job_queue
    job_queue.run_repeating(auto_delete_messages, interval=60, first=0) # Run every minute

    # Run the bot until you press Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
