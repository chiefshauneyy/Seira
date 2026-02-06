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

# 1. FIX: Absolute Pathing for Daemon Stability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
TIMEZONE = pytz.timezone("America/Chicago")

# Logging setup for /tmp/seira.log
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user: return False
    return str(user.id) == ALLOWED_USER_ID

# --- SCHEDULED JOBS ---

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    """Triggered by the JobQueue for Warfare and Astrophysics."""
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    
    if not chat_id:
        logging.error("No chat_id found in memory. Cannot send briefing.")
        return

    # Determine briefing type from job name
    topic = "warfare" if "warfare" in job.name else "astrophysics"
    
    # Brain logic: seira_core handles the anti-repeat and content generation
    briefing_content = core.get_scheduled_lesson(topic, memory)
    
    await context.bot.send_message(chat_id=chat_id, text=briefing_content)

# --- COMMANDS ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Scheduled briefings active (08:00, 12:00, 19:00).")

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    memory = core.load_memory()
    await update.message.reply_text(f"```json\n{core.memory_pretty(memory)}\n```", parse_mode="Markdown")
    async def trigger_war_test(update, context):
    """Manually triggers a warfare briefing for testing."""
    from seira_core import get_scheduled_lesson, load_memory
    await update.message.reply_text("Copy that, Operator. Forcing a Warfare Briefing now...")
    
    memory = load_memory()
    lesson = get_scheduled_lesson("warfare", memory)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=lesson
    )

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    memory = core.load_memory()
    
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return

    system = (
        f"You are {core.AGENT_NAME}, Shaun's personal stateful AI companion. "
        "You are an expert in USMC scout sniper discipline and cloud architecture. "
        "Maintain military bearing: concise, lethal, and helpful."
    )
    user_msg = f"Memory Summary:\n{core.memory_summary(memory)}\n\nUser: {text}"
    await update.message.reply_text(core.llm(system, user_msg))

# --- MAIN RUNNER ---

def main():
    if not TOKEN:
        print("Error: No TELEGRAM_BOT_TOKEN found.")
        return

    # Build application with JobQueue support
    app = Application.builder().token(TOKEN).build()
    job_queue = app.job_queue

    # Schedule Briefings (Central Time)
    # 08:00 Warfare
    job_queue.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    # 12:00 Astrophysics
    job_queue.run_daily(send_scheduled_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    # 19:00 Astrophysics
    job_queue.run_daily(send_scheduled_briefing, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")

    # Handlers
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.VOICE, core.on_voice)) # Assuming logic moved to core or kept

    print(f"--- {core.AGENT_NAME} DAEMON ACTIVE ---")
    app.run_polling()

if __name__ == "__main__":
    main()