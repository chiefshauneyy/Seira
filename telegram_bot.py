import os
import asyncio
import logging
from datetime import time, datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import seira_core as core
from image_pipeline import ImagePipeline

# Config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TIMEZONE = pytz.timezone("America/Chicago")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951")

async def send_pulse(context: ContextTypes.DEFAULT_TYPE):
    job_name = context.job.name
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    if not chat_id: return

    # Category Logic
    if any(x in job_name for x in ["warfare", "astrophysics"]):
        topic = "warfare" if "warfare" in job_name else "astrophysics"
        raw = core.get_scheduled_lesson(topic, memory)
        
        # Formatter
        briefing = core.llm("You are a Tactical Intelligence Officer. Cold, academic summary. No emojis. Bold headers. 3-4 bullets. Max 800 chars.", raw)
        
        # Art Director Logic
        if topic == "warfare":
            prompt = "Cinematic 35mm film photography, 1940s grain, black and white, moody shadows, raw historical realism. NO TEXT."
        else:
            prompt = "Cinematic wide shot, Dune 2021 aesthetic, massive brutalist monolith, desolate orange planet, 8k. NO TEXT."
        
        path = ImagePipeline().generate_free_image(prompt)
        if path:
            with open(path, 'rb') as f:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=briefing, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=briefing, parse_mode="Markdown")

    elif "news" in job_name:
        # Live Intel Pulses
        topic = "cybersecurity" if "cyber" in job_name else "quantum computing"
        # Using simple LLM call for news simulation/formatting here
        briefing = core.llm(f"Provide a cold intel briefing on recent {topic} trends.", "Brief me.")
        await context.bot.send_message(chat_id=chat_id, text=f"📡 **INTEL PULSE: {topic.upper()}**\n\n{briefing}", parse_mode="Markdown")

    elif "lore" in job_name:
        # Lore Archives
        briefing = core.get_scheduled_lesson("lore", memory)
        await context.bot.send_message(chat_id=chat_id, text=f"📜 **LORE ARCHIVE**\n\n{briefing}", parse_mode="Markdown")

# --- COMMANDS ---
async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class MockJob: name = "daily_warfare"
    context.job = MockJob(); await send_pulse(context)

async def trigger_astro_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class MockJob: name = "noon_astrophysics"
    context.job = MockJob(); await send_pulse(context)

async def trigger_lore_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class MockJob: name = "morning_lore"
    context.job = MockJob(); await send_pulse(context)

async def main():
    app = Application.builder().token(TOKEN).build()
    jq = app.job_queue

    # The 7-Pulse Schedule
    jq.run_daily(send_pulse, time(7, 0, tzinfo=TIMEZONE), name="morning_lore")
    jq.run_daily(send_pulse, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    jq.run_daily(send_pulse, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    jq.run_daily(send_pulse, time(15, 0, tzinfo=TIMEZONE), name="news_cyber")
    jq.run_daily(send_pulse, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")
    jq.run_daily(send_pulse, time(20, 0, tzinfo=TIMEZONE), name="news_quantum")
    jq.run_daily(send_pulse, time(21, 0, tzinfo=TIMEZONE), name="night_lore")

    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("test_astro", trigger_astro_test))
    app.add_handler(CommandHandler("test_lore", trigger_lore_test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, core.on_message))

    async with app:
        await app.initialize(); await app.start(); await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())