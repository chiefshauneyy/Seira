import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

import seira_core as core

load_dotenv(dotenv_path=".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()

def is_allowed(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    try:
        return str(update.effective_user.id) == str(ALLOWED_USER_ID)
    except Exception:
        return False

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(f"{core.AGENT_NAME} online. Use /help.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(core.HELP_TEXT)

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(f"Your Telegram user id: {update.effective_user.id}")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    memory = core.load_memory()

    # Run Seira slash commands immediately
    handled, reply, memory = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return

    lower = text.lower()

    # Approval-gated quick actions
    if lower.startswith("note:"):
        note_text = text.split(":", 1)[1].strip()
        action = {"type": "add_note", "summary": f"Add note: {note_text}", "payload": {"text": note_text}}
        action_id = core.save_pending_action(core.load_memory(), {"action": action})
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{action_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action_id}")]
        ])
        await update.message.reply_text(f"Approval required:\n{action['summary']}", reply_markup=keyboard)
        return

    if lower.startswith("checkin:"):
        payload_str = text.split(":", 1)[1].strip()
        kv = core.parse_kv_pairs(payload_str)
        action = {"type": "log_checkin", "summary": f"Log check-in: {payload_str}", "payload": kv}
        action_id = core.save_pending_action(core.load_memory(), {"action": action})
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{action_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action_id}")]
        ])
        await update.message.reply_text(f"Approval required:\n{action['summary']}", reply_markup=keyboard)
        return

    # Otherwise: normal chat reply
    system = (
        f"You are {core.AGENT_NAME}. Be practical and concise. "
        "Use memory for context."
    )
    user = f"Memory:\n{core.memory_pretty(memory)}\n\nUser:\n{text}"
    reply_text = core.llm(system, user)
    await update.message.reply_text(reply_text)

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    if ":" not in data:
        await query.edit_message_text("Invalid action callback.")
        return

    verb, action_id = data.split(":", 1)
    memory = core.load_memory()

    if verb == "approve":
        result = core.execute_action(memory, action_id)
        await query.edit_message_text(result)
        return

    if verb == "reject":
        pending = memory.get("pending_actions", {})
        if action_id in pending:
            del pending[action_id]
            core.save_memory(memory)
        await query.edit_message_text("Rejected. No action taken.")
        return

    await query.edit_message_text("Unknown callback.")

def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing in .env")

    # Python 3.14 compatibility: ensure event loop exists
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print(f"{core.AGENT_NAME} Telegram bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
