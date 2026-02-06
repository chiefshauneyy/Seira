import os
import asyncio
import sys
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import seira_core as core

load_dotenv(dotenv_path=".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()

CHECKIN_HOUR = int(os.getenv("CHECKIN_HOUR", "9"))
CHECKIN_MINUTE = int(os.getenv("CHECKIN_MINUTE", "0"))

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user: return False
    current_id = str(user.id)
    print(f"DEBUG: Auth Check - Incoming: {current_id} | Allowed: {ALLOWED_USER_ID}")
    if not ALLOWED_USER_ID: return True
    return current_id == ALLOWED_USER_ID

def _approval_keyboard(action_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{action_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action_id}")
        ]
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Use /help.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text(core.HELP_TEXT)

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    memory = core.load_memory()
    text = core.memory_pretty(memory)
    if len(text) > 4000:
        text = core.memory_summary(memory) + "\n\n(Full JSON too large)"
    await update.message.reply_text(f"```json\n{text}\n```", parse_mode="Markdown")

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram user id: {update.effective_user.id}")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    print(f"Message: {text}")
    memory = core.load_memory()
    
    # Handle core commands
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return

    # Natural Language Logic (LLM Fallback)
    system = f"You are {core.AGENT_NAME}. Be practical."
    user_msg = f"Memory: {core.memory_summary(memory)}\nUser: {text}"
    await update.message.reply_text(core.llm(system, user_msg))

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    query = update.callback_query
    await query.answer()
    verb, action_id = query.data.split(":", 1)
    result = core.execute_action(core.load_memory(), action_id) if verb == "approve" else "Rejected."
    await query.edit_message_text(result)

async def main_async():
    """Main async entry point for Python 3.14 compatibility."""
    if not TOKEN:
        print("CRITICAL: Token missing.")
        return

    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print(f"--- {core.AGENT_NAME} STARTUP ---")
    print(f"User ID: {ALLOWED_USER_ID}")
    
    async with app:
        await app.initialize()
        await app.start()
        print("Seira is now polling...")
        await app.updater.start_polling()
        # Keep the bot running until interrupted
        while True:
            await asyncio.sleep(1)

def main():
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        print("\nSeira shutting down...")

if __name__ == "__main__":
    main()