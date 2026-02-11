import os
import asyncio
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
    assets_dir = os.path.join(BASE_DIR, "assets")
    if not os.path.exists(assets_dir): return
    now = time_module.time()
    cutoff = now - (days * 86400)
    for f in os.listdir(assets_dir):
        file_path = os.path.join(assets_dir, f)
        if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff:
            os.remove(file_path)

# --- JOBS ---

async def send_cryo_lore(context: ContextTypes.DEFAULT_TYPE):
    purge_old_assets(days=1)
    memory = core.load_memory()
    
    # Try to find chat_id from memory, or from the active update if manual test
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    if not chat_id and hasattr(context, "user_data"):
        chat_id = ALLOWED_USER_ID # Fallback to owner

    system = (
        "You are 'The Archivist,' a weary historian in the Dune universe. "
        "You speak to a human from Earth (2026) recently awoken from 20,000 years of cryo. "
        "Explain Dune lore by comparing it to their 21st-century past. "
        "Tone: Scholarly, grim, pitying. Max 700 chars."
    )
    
    regrad_count = memory.get("lessons_taught", 0)
    lesson = core.llm(system, f"Lesson #{regrad_count}: Focus on the transition from Earth to the Imperium.")

    visual_prompt = "Cinematic film still, dimly lit stone archive room, robed historian, Dune aesthetic, 8k."
    pipeline = ImagePipeline()
    local_path = pipeline.generate_free_image(visual_prompt)
    output = f"📜 **RE-INTEGRATION CHRONICLE**\n\n{lesson}"

    if local_path and os.path.exists(local_path):
        with open(local_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=output, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=output, parse_mode="Markdown")
    
    memory["lessons_taught"] = regrad_count + 1
    core.save_memory(memory)

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    purge_old_assets(days=1)
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id") or ALLOWED_USER_ID
    
    job_name = job.name.lower()
    topic = "warfare" if "warfare" in job_name else "astrophysics"
    if "cyber" in job_name: topic = "cybersecurity"
    if "quantum" in job_name: topic = "quantum computing"
    
    raw_content = core.get_scheduled_lesson(topic, memory)
    briefing = core.llm("Tactical Intelligence Officer summary. No emojis. Bold headers.", raw_content)
    
    pipeline = ImagePipeline()
    path = pipeline.generate_free_image(f"Brutalist architecture, {topic} theme, Dune style.")
    
    if path:
        with open(path, 'rb') as f:
            await context.bot.send_photo(chat_id=chat_id, photo=f, caption=briefing[:1024], parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=briefing, parse_mode="Markdown")

# --- COMMANDS ---

async def test_lore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("📜 Accessing the Cryo-Archives...")
    await send_cryo_lore(context)

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    now = datetime.now(TIMEZONE)
    memory = core.load_memory()
    lessons = memory.get("lessons_taught", 0)
    await update.message.reply_text(f"🛰️ **SEIRA HEARTBEAT**\nStatus: Operational\nTime: {now.strftime('%H:%M:%S')}\nMemory: {lessons} Logged", parse_mode="Markdown")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text("Cryo-recovery engaged. Profile locked.")

async def main():
    app = Application.builder().token(TOKEN).build()
    jq = app.job_queue
    jq.run_daily(send_cryo_lore, time(7, 0, tzinfo=TIMEZONE), name="morning_archivist")
    jq.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    # ... other jobs ...

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("test_lore", test_lore))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None)) # Basic handler
    
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())