import os
import asyncio
import logging
import pytz
from datetime import time, datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import seira_core as core
from image_pipeline import ImagePipeline

TIMEZONE = pytz.timezone("America/Chicago")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951")

async def send_pulse(context: ContextTypes.DEFAULT_TYPE):
    job_name = context.job.name
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    if not chat_id: return

    if any(x in job_name for x in ["warfare", "astrophysics"]):
        topic = "warfare" if "warfare" in job_name else "astrophysics"
        raw = core.get_scheduled_lesson(topic, memory)
        briefing = core.llm("Tactical Officer. Cold academic summary. No emojis. Bold headers. Max 800 chars.", raw)
        
        prompt = "Cinematic 35mm film photography, 1940s grain, B&W." if topic == "warfare" else "Dune 2021 aesthetic, brutalist monolith, 8k."
        path = ImagePipeline().generate_free_image(prompt)
        
        if path:
            with open(path, 'rb') as f:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=briefing, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=briefing, parse_mode="Markdown")
    else:
        # News or Lore (Text only)
        topic = "cybersecurity" if "cyber" in job_name else "Dune Lore"
        raw = core.llm(f"Briefing on {topic}.", "Generate.")
        await context.bot.send_message(chat_id=chat_id, text=f"📡 **INTEL: {topic.upper()}**\n\n{raw}", parse_mode="Markdown")

# --- COMMANDS ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ALLOWED_USER_ID: return
    mem = core.load_memory()
    mem["profile"]["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text("SEIRA Initialized. Chat ID Secured. Pulse Sync: Active.")

async def test_war(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ALLOWED_USER_ID: return
    class MockJob: name = "daily_warfare"
    context.job = MockJob()
    await send_pulse(context)

async def main():
    app = Application.builder().token(TOKEN).build()
    
    # Handlers FIRST
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("test_war", test_war))
    
    # Schedule
    jq = app.job_queue
    jq.run_daily(send_pulse, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    # ... add others as needed ...

    print("--- SEIRA ACTIVE ---")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())