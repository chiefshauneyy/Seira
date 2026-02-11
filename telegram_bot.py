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
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()

# --- HANDLERS ---

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ALLOWED_USER_ID: return
    text = update.message.text
    memory = core.load_memory()
    handled, reply = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return
    response = core.llm(f"You are {core.AGENT_NAME}, tactical AI.", text)
    await update.message.reply_text(response)

async def send_pulse(context: ContextTypes.DEFAULT_TYPE):
    job_name = context.job.name.lower()
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id") or ALLOWED_USER_ID

    if "warfare" in job_name or "astrophysics" in job_name:
        topic = "warfare" if "warfare" in job_name else "astrophysics"
        raw = core.get_scheduled_lesson(topic, memory)
        briefing = core.llm("Tactical Officer. Cold academic summary. Bold headers.", raw)
        prompt = "Cinematic 35mm film photography, 1940s grain, B&W." if topic == "warfare" else "Dune 2021 aesthetic, 8k."
        path = ImagePipeline().generate_free_image(prompt)
        if path:
            with open(path, 'rb') as f:
                await context.bot.send_photo(chat_id=chat_id, photo=f, caption=briefing, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=briefing)
    elif "lore" in job_name:
        raw = core.get_scheduled_lesson("lore", memory)
        await context.bot.send_message(chat_id=chat_id, text=f"📜 **LORE:**\n\n{raw}")
    else:
        raw = core.llm("Briefing on cybersecurity trends.", "Generate pulse.")
        await context.bot.send_message(chat_id=chat_id, text=f"📡 **INTEL:**\n\n{raw}")

# --- TEST COMMANDS ---
async def test_war(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class MockJob: name = "daily_warfare"
    context.job = MockJob()
    await send_pulse(context)

async def test_astro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class MockJob: name = "noon_astrophysics"
    context.job = MockJob()
    await send_pulse(context)

async def test_lore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    class MockJob: name = "morning_lore"
    context.job = MockJob()
    await send_pulse(context)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem = core.load_memory()
    mem["profile"]["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text("SEIRA online. 7-pulse schedule active.")

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("test_war", test_war))
    app.add_handler(CommandHandler("test_astro", test_astro))
    app.add_handler(CommandHandler("test_lore", test_lore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    jq = app.job_queue
    jq.run_daily(send_pulse, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    # ... other 6 slots follow this pattern ...

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())