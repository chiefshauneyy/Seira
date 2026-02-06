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

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user: return False
    current_id = str(user.id)
    print(f"DEBUG: Auth Check - Incoming: {current_id} | Allowed: {ALLOWED_USER_ID}")
    if not ALLOWED_USER_ID: return True
    return current_id == ALLOWED_USER_ID

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /start")
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Use /help.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /help")
    if not is_allowed(update): return
    await update.message.reply_text(core.HELP_TEXT)

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /memory")
    if not is_allowed(update): return
    memory = core.load_memory()
    text = core.memory_pretty(memory)
    if len(text) > 4000:
        text = core.memory_summary(memory) + "\n\n(Full JSON too large)"
    await update.message.reply_text(f"```json\n{text}\n```", parse_mode="Markdown")

async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explicitly handles the /remember command."""
    print(f"Command Triggered: /remember with args: {context.args}")
    if not is_allowed(update): return
    
    # Reconstruct the command for the core parser
    full_text = f"/remember {' '.join(context.args)}"
    handled, reply, _ = core.handle_command(full_text, core.load_memory())
    
    if handled:
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("Usage: /remember key=value")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    print(f"Message Received: {text}")
    
    memory = core.load_memory()
    
    # Identity-driven response
    system = (
        f"You are {core.AGENT_NAME}, Shaun's personal companion. "
        "Use the current memory to be helpful. If the user wants to save "
        "a fact, tell them to use '/remember key=value'."
    )
    user_msg = f"Memory Summary:\n{core.memory_summary(memory)}\n\nUser: {text}"
    await update.message.reply_text(core.llm(system, user_msg))

async def main_async():
    if not TOKEN:
        print("CRITICAL: Token missing.")
        return

    app = Application.builder().token(TOKEN).build()

    # Explicit Command Registration
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("remember", cmd_remember)) # Added this
    
    # Message handler (Now catches everything NOT a registered command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    async with app:
        await app.initialize()
        await app.start()
        print("--- SEIRA STARTUP COMPLETE ---")
        await app.updater.start_polling()
        while True:
            await asyncio.sleep(1)

def main():
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        print("\nSeira shutting down...")

if __name__ == "__main__":
    main()