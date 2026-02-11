import os
import asyncio
import logging
import time as time_module
from datetime import time, datetime
import pytz
from dotenv import load_dotenv
from image_pipeline import ImagePipeline
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import seira_core as core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()
TIMEZONE = pytz.timezone("America/Chicago")

def is_allowed(update: Update) -> bool:
    return str(update.effective_user.id) == ALLOWED_USER_ID if update.effective_user else False

# --- CORE JOBS ---

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    job_name = context.job.name.lower()
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id") or ALLOWED_USER_ID

    if "lore" in job_name:
        system = "You are SEIRA. Provide a cold, academic briefing on Dune universe lore. Focus on strategy and history. Max 600 chars."
        prompt = "Provide a lesson on a random aspect of Dune lore (e.g. Great Houses, Fremen, Spice)."
        header = "📜 **DUNE LORE ARCHIVE**"
        visual = "Cinematic wide shot, Dune 2021 aesthetic, brutalist architecture, 8k."
    else:
        topic = "warfare" if "warfare" in job_name else "astrophysics"
        if "cyber" in job_name: topic = "cybersecurity"
        if "quantum" in job_name: topic = "quantum computing"
        
        raw_intel = core.get_scheduled_lesson(topic, memory)
        system = "You are a Tactical Intelligence Officer. Rewrite into a cold, academic summary. Bold headers, 3-4 bullets. Max 800 chars."
        prompt = raw_intel
        header = f"📡 **INTELLIGENCE PULSE: {topic.upper()}**"
        visual = "Cyberpunk brutalist terminal, glowing code, dark glass, 8k."

    briefing = core.llm(system, prompt)
    pipeline = ImagePipeline()
    path = pipeline.generate_free_image(visual)

    output = f"{header}\n\n{briefing}"
    if path and os.path.exists(path):
        with open(path, 'rb') as f:
            await context.bot.send_photo(chat_id=chat_id, photo=f, caption=output, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=output, parse_mode="Markdown")

# --- MANUAL TEST HANDLERS ---

async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Initializing Warfare Briefing Test...")
    class MockJob:
        def __init__(self, name): self.name = name
    context.job = MockJob("daily_warfare")
    await send_scheduled_briefing(context)

async def trigger_astro_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Initializing Astrophysics Briefing Test...")
    class MockJob:
        def __init__(self, name): self.name = name
    context.job = MockJob("noon_astrophysics")
    await send_scheduled_briefing(context)

async def test_intel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("📡 Intercepting global signals...")
    memory = core.load_memory()
    report = core.get_scheduled_lesson("Global Intelligence", memory)
    await update.message.reply_text(report, parse_mode='Markdown')

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    now = datetime.now(TIMEZONE)
    memory = core.load_memory()
    lessons = memory.get("lessons_taught", 0)
    
    job_times = [time(7, 0), time(8, 0), time(12, 0), time(15, 0), time(20, 0), time(21, 0)]
    next_pulse = "Calculated for tomorrow"
    for t in job_times:
        pulse_time = TIMEZONE.localize(datetime.combine(now.date(), t))
        if pulse_time > now:
            diff = pulse_time - now
            h, m = divmod(diff.seconds // 60, 60)
            next_pulse = f"Next pulse in {h}h {m}m"
            break

    await update.message.reply_text(
        f"🛰️ **{core.AGENT_NAME} HEARTBEAT**\n"
        f"Status: Operational\n"
        f"Timing: {next_pulse}\n"
        f"Memory: {lessons} Logged", 
        parse_mode="Markdown"
    )

async def main():
    app = Application.builder().token(TOKEN).build()
    jq = app.job_queue

    # 6-Pulse Schedule
    jq.run_daily(send_scheduled_briefing, time(7, 0, tzinfo=TIMEZONE), name="morning_lore")
    jq.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    jq.run_daily(send_scheduled_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    jq.run_daily(send_scheduled_briefing, time(15, 0, tzinfo=TIMEZONE), name="afternoon_cyber")
    jq.run_daily(send_scheduled_briefing, time(20, 0, tzinfo=TIMEZONE), name="evening_quantum")
    jq.run_daily(send_scheduled_briefing, time(21, 0, tzinfo=TIMEZONE), name="night_lore")

    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("test_astro", trigger_astro_test))
    app.add_handler(CommandHandler("test_intel", test_intel))
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("SEIRA online.")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text(core.llm(f"You are {core.AGENT_NAME}, military bearing.", u.message.text))))

    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())