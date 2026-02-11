import os
import asyncio
import json
import logging
import time as time_module
from datetime import time, datetime
import pytz
from dotenv import load_dotenv
from image_pipeline import ImagePipeline
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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()
TIMEZONE = pytz.timezone("America/Chicago")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    return str(user.id) == ALLOWED_USER_ID if user else False

def purge_old_assets(days=1):
    """Deletes files in the assets folder older than X days to save disk space."""
    assets_dir = os.path.join(BASE_DIR, "assets")
    if not os.path.exists(assets_dir):
        return
    
    now = time_module.time()
    cutoff = now - (days * 86400)
    
    purged_count = 0
    for f in os.listdir(assets_dir):
        file_path = os.path.join(assets_dir, f)
        if os.path.isfile(file_path):
            if os.path.getmtime(file_path) < cutoff:
                try:
                    os.remove(file_path)
                    purged_count += 1
                except Exception as e:
                    logging.error(f"Failed to purge {f}: {e}")
    if purged_count > 0:
        logging.info(f"Cleanup complete. Purged {purged_count} old assets.")

# --- SCHEDULED JOBS ---

async def send_cryo_lore(context: ContextTypes.DEFAULT_TYPE):
    """The Archivist delivers lessons to the 'Ancient One' from 2026."""
    purge_old_assets(days=1)
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    if not chat_id: return

    system = (
        "You are 'The Archivist,' a weary historian in the Dune universe. "
        "You are speaking to a human who has just woken up from cryosleep after 20,000 years. "
        "They originated from Earth in the year 2026. "
        "Explain a piece of Dune lore (The Butlerian Jihad, Shai-Hulud, The Guild, or Water Discipline) "
        "by comparing it to their primitive 21st-century understanding. "
        "Tone: Respectful but grim, scholarly, and slightly pitying of their 'ancient' ignorance. "
        "Max 700 characters."
    )
    
    regrad_count = memory.get("lessons_taught", 0)
    lesson = core.llm(system, f"Re-integration Lesson #{regrad_count}: Focus on the transition from Earth to the Imperium.")

    visual_prompt = (
        "Cinematic film still, a dimly lit stone archive room, holographic star maps "
        "flickering over ancient parchment, a robed historian in shadows, "
        "Dune 2021 aesthetic, moody amber lighting, 8k."
    )
    
    pipeline = ImagePipeline()
    local_path = pipeline.generate_free_image(visual_prompt)
    output = f"📜 **RE-INTEGRATION CHRONICLE**\n*Subject: The Great Transition*\n\n{lesson}"

    try:
        if local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=output, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=output, parse_mode="Markdown")
        
        # Update memory count
        memory["lessons_taught"] = regrad_count + 1
        core.save_memory(memory)
    except Exception as e:
        logging.error(f"Archivist Error: {e}")

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    purge_old_assets(days=1)
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    
    if not chat_id: return

    job_name = job.name.lower()
    if "warfare" in job_name:
        topic = "warfare"
    elif "astro" in job_name:
        topic = "astrophysics"
    elif "cyber" in job_name:
        topic = "cybersecurity"
    elif "quantum" in job_name:
        topic = "quantum computing"
    else:
        topic = "general intelligence"
    
    try:
        raw_content = core.get_scheduled_lesson(topic, memory)
        formatter_system = (
            "You are a Tactical Intelligence Officer. Rewrite the text into a cold, "
            "academic summary. No emojis. Max 800 characters. "
            "Use bold headers and 3-4 bullet points. End with 3 hashtags."
        )
        briefing_content = core.llm(formatter_system, raw_content)
        
        if len(briefing_content) > 1000:
            briefing_content = briefing_content[:990] + "..."
        
        if topic == "warfare":
            visual_prompt = "Cinematic 35mm film photography, 1940s grain, black and white, raw historical realism."
        elif "cyber" in topic or "quantum" in topic:
            visual_prompt = "Cyberpunk brutalist terminal, glowing green code on dark glass, highly detailed, 8k."
        else:
            visual_prompt = "Cinematic wide shot, Dune 2021 aesthetic, massive brutalist monolith, harsh sunlight."
        
        pipeline = ImagePipeline()
        local_path = pipeline.generate_free_image(visual_prompt)
        
        if local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=briefing_content, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=briefing_content)
            
    except Exception as e:
        logging.error(f"Briefing generation error: {e}")

# --- MANUAL TEST HANDLERS ---

async def test_lore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Opening the restricted archives... stand by, Ancient One.")
    await send_cryo_lore(context)

async def test_intel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("📡 Intercepting global signals... stand by.")
    memory = core.load_memory()
    report = core.get_scheduled_lesson("Global Intelligence", memory)
    await update.message.reply_text(report, parse_mode='Markdown')

async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Copy. Initializing Warfare Briefing...")
    class MockJob:
        def __init__(self, name): self.name = name
    context.job = MockJob("daily_warfare")
    await send_scheduled_briefing(context)

# --- TELEGRAM COMMAND HANDLERS ---

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    now = datetime.now(TIMEZONE)
    current_time = now.strftime("%H:%M:%S")
    
    # 07:00, 08:00, 12:00, 15:00, 20:00, 21:00
    job_times = [time(7, 0), time(8, 0), time(12, 0), time(15, 0), time(20, 0), time(21, 0)]
    next_brief = "Calculated for tomorrow"
    
    for t in job_times:
        brief_time = TIMEZONE.localize(datetime.combine(now.date(), t))
        if brief_time > now:
            diff = brief_time - now
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            next_brief = f"Next pulse in {hours}h {minutes}m"
            break

    memory = core.load_memory()
    lessons = memory.get("lessons_taught", 0)
    
    status_msg = (
        f"🛰️ **{core.AGENT_NAME} HEARTBEAT**\n"
        f"--- Status: Operational ---\n"
        f"System Time: {current_time}\n"
        f"Timing: {next_brief}\n"
        f"Memory: {lessons} Lessons Logged"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Cryo-recovery sequence engaged.")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    system = f"You are {core.AGENT_NAME}, Shaun's personal AI companion. Military bearing."
    await update.message.reply_text(core.llm(system, f"User: {text}"))

async def main():
    app = Application.builder().token(TOKEN).build()
    jq = app.job_queue

    # Archivist Lore Lessons (07:00 and 21:00)
    jq.run_daily(send_cryo_lore, time(7, 0, tzinfo=TIMEZONE), name="morning_archivist")
    jq.run_daily(send_cryo_lore, time(21, 0, tzinfo=TIMEZONE), name="night_archivist")

    # News Briefings
    jq.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    jq.run_daily(send_scheduled_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    jq.run_daily(send_scheduled_briefing, time(15, 0, tzinfo=TIMEZONE), name="afternoon_cyber")
    jq.run_daily(send_scheduled_briefing, time(20, 0, tzinfo=TIMEZONE), name="evening_quantum")

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("test_intel", test_intel))
    app.add_handler(CommandHandler("test_lore", test_lore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print(f"--- {core.AGENT_NAME} DAEMON ACTIVE ---")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())