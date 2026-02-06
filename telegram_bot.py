import os
import asyncio
import io
import logging
from datetime import time
import pytz
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import seira_core as core

# Absolute Pathing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
TIMEZONE = pytz.timezone("America/Chicago")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user: return False
    return str(user.id) == ALLOWED_USER_ID

# --- SCHEDULED JOBS ---

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    
    if not chat_id:
        logging.error("No chat_id found in memory.")
        return

    topic = "warfare" if "warfare" in job.name else "astrophysics"
    briefing_content = core.get_scheduled_lesson(topic, memory)
    await context.bot.send_message(chat_id=chat_id, text=briefing_content)

# --- NEW: TEST COMMAND ---

async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers a warfare briefing for testing."""
    if not is_allowed(update): return
    
    await update.message.reply_text("Copy that, Operator. Forcing a Warfare Briefing now...")
    
    memory = core.load_memory()
    lesson = core.get_scheduled_lesson("warfare", memory)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=lesson
    )

# --- COMMANDS ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Scheduled briefings active.")

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    memory = core.load_memory()
    await update.message.reply_text(f"```json\n{json.dumps(memory, indent=2)}\n```", parse_mode="Markdown")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    memory = core.load_memory()
    
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return

    system = (
        f"You are {core.AGENT_NAME}, Shaun's personal AI companion. "
        "Maintain military bearing: concise and lethal."
    )
    user_msg = f"Memory Summary:\n{core.memory_summary(memory)}\n\nUser: {text}"
    await update.message.reply_text(core.llm(system, user_msg))

# --- MAIN ---

def main():
    if not TOKEN: return

    app = Application.builder().token(TOKEN).build()
    job_queue = app.job_queue

    # Schedule Briefings
    job_queue.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    job_queue.run_daily(send_scheduled_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    job_queue.run_daily(send_scheduled_briefing, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")

    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.VOICE, core.on_voice))

    print(f"--- {core.AGENT_NAME} DAEMON ACTIVE ---")
    app.run_polling()

if __name__ == "__main__":
    main()