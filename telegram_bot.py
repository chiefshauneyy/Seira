import os
import asyncio
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
    if not user:
        return False
    
    current_id = str(user.id)
    # DEBUG PRINT: This will show up in your Mac terminal
    print(f"--- AUTH CHECK ---")
    print(f"Incoming ID: {current_id}")
    print(f"Allowed ID : {ALLOWED_USER_ID}")
    
    if not ALLOWED_USER_ID:
        print("WARNING: TELEGRAM_ALLOWED_USER_ID is empty in .env. Allowing all users.")
        return True
        
    allowed = current_id == ALLOWED_USER_ID
    print(f"Access Granted: {allowed}")
    print(f"------------------")
    return allowed


def _approval_keyboard(action_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{action_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{action_id}")
        ]
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /start")
    if not is_allowed(update):
        return
    mem = core.load_memory()
    mem.setdefault("profile", {})
    mem["profile"]["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Use /help.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /help")
    if not is_allowed(update):
        return
    await update.message.reply_text(core.HELP_TEXT)

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /memory")
    if not is_allowed(update):
        return
    memory = core.load_memory()
    text = core.memory_pretty(memory)
    # Telegram message limit is 4096. If it's too big, send summary.
    if len(text) > 4000:
        text = core.memory_summary(memory) + "\n\n(Full JSON too large for Telegram)"
    
    await update.message.reply_text(f"```json\n{text}\n```", parse_mode="MarkdownV2")

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Command Triggered: /today")
    if not is_allowed(update):
        return
    memory = core.load_memory()
    handled, reply, _ = core.handle_command("/today", memory)
    await update.message.reply_text(reply)

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"Command Triggered: /whoami (User ID: {user_id})")
    await update.message.reply_text(f"Your Telegram user id: {user_id}")


async def reminder_tick(context: ContextTypes.DEFAULT_TYPE):
    mem = core.load_memory()
    chat_id = mem.get("profile", {}).get("telegram_chat_id")
    if not chat_id:
        return
    now = datetime.now()
    changed = False
    for r in mem.get("reminders", []):
        if r.get("sent"):
            continue
        try:
            due_dt = datetime.fromisoformat(r.get("due", ""))
        except Exception:
            continue
        if due_dt <= now:
            await context.bot.send_message(chat_id=chat_id, text=f"⏰ Reminder: {r.get('text','')}")
            r["sent"] = True
            changed = True
    if changed:
        core.save_memory(mem)


async def daily_checkin(context: ContextTypes.DEFAULT_TYPE):
    mem = core.load_memory()
    chat_id = mem.get("profile", {}).get("telegram_chat_id")
    if not chat_id:
        return
    msg = (
        "🧠 Daily check-in:\n"
        "Reply with:\n"
        "checkin: sleep=__ soreness=__ mood=__ stress=__ [hrv=__ rhr=__]"
    )
    await context.bot.send_message(chat_id=chat_id, text=msg)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    print(f"Message Received: {text}")
    memory = core.load_memory()

    # Route slash commands to core first (fallback)
    if text.startswith("/"):
        handled, reply, _ = core.handle_command(text, memory)
        if handled:
            await update.message.reply_text(reply)
            return

    lower = text.lower()
    if lower.startswith("note:"):
        note_text = text.split(":", 1)[1].strip()
        action = {"type": "add_note", "summary": f"Add note: {note_text}", "payload": {"text": note_text}}
        action_id = core.save_pending_action(core.load_memory(), {"action": action})
        await update.message.reply_text(f"Approval required:\n{action['summary']}", reply_markup=_approval_keyboard(action_id))
        return

    if lower.startswith("checkin:"):
        payload_str = text.split(":", 1)[1].strip()
        kv = core.parse_kv_pairs(payload_str)
        action = {"type": "log_checkin", "summary": f"Log check-in: {payload_str}", "payload": kv}
        action_id = core.save_pending_action(core.load_memory(), {"action": action})
        await update.message.reply_text(f"Approval required:\n{action['summary']}", reply_markup=_approval_keyboard(action_id))
        return

    if lower.startswith("remind:"):
        spec = text.split(":", 1)[1].strip()
        due_dt, reminder_text = core.parse_remind_spec(spec)
        if not due_dt or not reminder_text:
            await update.message.reply_text("I couldn't parse that. Try 'remind: in 30m stretch'")
            return
        action = {
            "type": "set_reminder",
            "summary": f"Set reminder for {due_dt.isoformat(timespec='minutes')}: {reminder_text}",
            "payload": {"due": due_dt.isoformat(timespec="seconds"), "text": reminder_text},
        }
        action_id = core.save_pending_action(core.load_memory(), {"action": action})
        await update.message.reply_text(f"Approval required:\n{action['summary']}", reply_markup=_approval_keyboard(action_id))
        return

    # Default LLM chat
    system = f"You are {core.AGENT_NAME}. Be practical and concise. Use memory for context."
    user = f"Memory Summary:\n{core.memory_summary(memory)}\n\nUser:\n{text}"
    reply_text = core.llm(system, user)
    await update.message.reply_text(reply_text)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    query = update.callback_query
    await query.answer()
    verb, action_id = query.data.split(":", 1)
    memory = core.load_memory()

    if verb == "approve":
        result = core.execute_action(memory, action_id)
        await query.edit_message_text(result)
    elif verb == "reject":
        pending = memory.get("pending_actions", {})
        if action_id in pending:
            del pending[action_id]
            core.save_memory(memory)
        await query.edit_message_text("Rejected.")


def main():
    if not TOKEN:
        print("CRITICAL ERROR: TELEGRAM_BOT_TOKEN missing in .env")
        return

    print("--- SEIRA STARTUP ---")
    print(f"Target User ID: {ALLOWED_USER_ID if ALLOWED_USER_ID else 'ALL'}")
    
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("whoami", cmd_whoami))

    # General Handlers
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # Background
    app.job_queue.run_repeating(reminder_tick, interval=30, first=5)
    
    print(f"{core.AGENT_NAME} Telegram bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    main()