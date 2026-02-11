import os
import asyncio
import logging
import pytz
from datetime import time, datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import seira_core as core
from image_pipeline import ImagePipeline

# Absolute Pathing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TIMEZONE = pytz.timezone("America/Chicago")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()

logging.basicConfig(level=logging.INFO)

def is_allowed(update: Update) -> bool:
    return str(update.effective_user.id) == ALLOWED_USER_ID if update.effective_user else False

# --- CORE PULSE ENGINE ---

async def send_pulse(context: ContextTypes.DEFAULT_TYPE):
    job_name = context.job.name.lower()
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id") or ALLOWED_USER_ID

    # 1. LESSONS (Warfare & Astrophysics) - High Fidelity + Image
    if "warfare" in job_name or "astrophysics" in job_name:
        topic = "warfare" if "warfare" in job_name else "astrophysics"
        raw_lesson = core.get_scheduled_lesson(topic, memory)
        
        formatter_sys = "You are a Tactical Intelligence Officer. Cold academic summary. No emojis. Bold headers. 3-4 bullets. Max 800 chars."
        briefing = core.llm(formatter_sys, raw_lesson)
        
        if topic == "warfare":
            visual = "Cinematic 35mm film photography, 1940s grain, black and white, moody shadows, raw historical realism. NO TEXT."
            header = "⚔️ **WARFARE HISTORY BRIEFING**"
        else:
            visual = "Cinematic wide shot, Dune 2021 aesthetic, massive brutalist monolith, desolate orange planet, 8k. NO TEXT."
            header = "🔭 **ASTROPHYSICS BRIEFING**"

        path = ImagePipeline().generate_free_image(visual)
        output = f"{header}\n\n{briefing}"
        
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=output, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=output, parse_mode="Markdown")

    # 2. DUNE LORE - History Archive (Text Only)
    elif "lore" in job_name:
        raw_lore = core.get_scheduled_lesson("lore", memory)
        await context.bot.send_message(chat_id=chat_id, text=f"📜 **DUNE LORE ARCHIVE**\n\n{raw_lore}", parse_mode="Markdown")

    # 3. MODERN NEWS - Real-time Intel (Text Only)
    else:
        topic = "cybersecurity" if "cyber" in job_name else "quantum computing"
        # Simulating news pulse using core.llm directly
        news_raw = core.llm(f"Briefing on {topic} latest trends for 2026.", "Generate pulse.")
        await context.bot.send_message(chat_id=chat_id, text=f"📡 **INTEL PULSE: {topic.upper()}**\n\n{news_raw}", parse_mode="Markdown")

# --- TEST HANDLERS ---

async def test_war(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Initializing Warfare Test (35mm B&W)...")
    class MockJob: name = "daily_warfare"
    context.job = MockJob(); await send_pulse(context)

async def test_astro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Initializing Astrophysics Test (Brutalist)...")
    class MockJob: name = "noon_astrophysics"
    context.job = MockJob(); await send_pulse(context)

async def test_lore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Accessing Lore Archive...")
    class MockJob: name = "morning_lore"
    context.job = MockJob(); await send_pulse(context)

async def test_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Intercepting News Signal...")
    class MockJob: name = "news_cyber"
    context.job = MockJob(); await send_pulse(context)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem["profile"]["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text("SEIRA online. Identity confirmed. 7-pulse schedule active.")

async def main():
    app = Application.builder().token(TOKEN).build()
    
    # Register Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("test_war", test_war))
    app.add_handler(CommandHandler("test_astro", test_astro))
    app.add_handler(CommandHandler("test_lore", test_lore))
    app.add_handler(CommandHandler("test_news", test_news))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, core.on_message))

    # 7-Pulse Schedule
    jq = app.job_queue
    jq.run_daily(send_pulse, time(7, 0, tzinfo=TIMEZONE), name="morning_lore")
    jq.run_daily(send_pulse, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    jq.run_daily(send_pulse, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    jq.run_daily(send_pulse, time(15, 0, tzinfo=TIMEZONE), name="news_cyber")
    jq.run_daily(send_pulse, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")
    jq.run_daily(send_pulse, time(20, 0, tzinfo=TIMEZONE), name="news_quantum")
    jq.run_daily(send_pulse, time(21, 0, tzinfo=TIMEZONE), name="night_lore")

    print(f"--- {core.AGENT_NAME} DAEMON ACTIVE ---")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())