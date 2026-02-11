import os
import asyncio
import io
import json
import logging
from datetime import time
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

# Absolute Pathing to ensure .env is found by the background process
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Fallback values if .env isn't loaded correctly
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8568467650:AAHnleqe6B1GTXc1ZmQvb9VTKdOMLOgccBk"
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()
TIMEZONE = pytz.timezone("America/Chicago")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user: return False
    return str(user.id) == ALLOWED_USER_ID

# --- SCHEDULED JOBS & TEST COMMAND ---

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    
    if not chat_id:
        logging.error("No chat_id found in memory.")
        return

    # Determine topic based on job name
    topic = "warfare" if "warfare" in job.name else "astrophysics"
    
    # 1. Get the Lesson Text
    briefing_content = core.get_scheduled_lesson(topic, memory)
    
    # 2. Art Director Logic - Generate a gritty, cinematic prompt
    # --- REFINED ART DIRECTOR STEP ---
    art_director_system = (
        "You are a 20th-century historical archivist. Create a descriptive, calm visual scene "
        "based on the provided text. Focus purely on the setting, the specific historical attire, "
        "and the atmospheric conditions. Avoid all mentions of conflict or weapons. "
        "STYLE: National Geographic photography, shot on 35mm grainy film, soft natural lighting, "
        "authentic textures, muted colors, cinematic composition. No text."
    )
    
    visual_prompt = core.llm(art_director_system, f"Lesson Text: {briefing_content}")
    print(f"DEBUG: Art Director Prompt: {visual_prompt}")
    
    try:
        pipeline = ImagePipeline()
        local_path = pipeline.generate_free_image(visual_prompt)
        
        if local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as photo:
                # Telegram captions have a 1024 character limit
                if len(briefing_content) <= 1000:
                    await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=briefing_content)
                else:
                    await context.bot.send_photo(chat_id=chat_id, photo=photo)
                    await context.bot.send_message(chat_id=chat_id, text=briefing_content)
        else:
            await context.bot.send_message(chat_id=chat_id, text=briefing_content)
            
    except Exception as e:
        logging.error(f"Briefing generation error: {e}")
        await context.bot.send_message(chat_id=chat_id, text=briefing_content)

async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers the full briefing flow (Text + Image) for testing."""
    if not is_allowed(update): 
        return
    
    await update.message.reply_text("Copy that, Operator. Initializing full Warfare Briefing protocol...")
    
    class MockJob:
        def __init__(self, name): self.name = name
    
    # Set the job name in the current context so the function knows what to generate
    context.job = MockJob("daily_warfare")
    await send_scheduled_briefing(context)

# --- TELEGRAM COMMAND HANDLERS ---

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

async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates an image based on user prompt and sends it back."""
    if not is_allowed(update): 
        return

    if not context.args:
        await update.message.reply_text("Operator, I need a prompt. Usage: /generate [description]")
        return

    prompt = " ".join(context.args)
    await update.message.reply_text(f"🎨 Synthesizing visual data for: '{prompt}'...")

    try:
        pipeline = ImagePipeline()
        local_path = pipeline.generate_free_image(prompt)

        if local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id, 
                    photo=photo,
                    caption=f"Visualized: {prompt[:50]}..."
                )
        else:
            await update.message.reply_text("❌ Failed to secure the asset. Check logs.")
    except Exception as e:
        logging.error(f"Generation error: {e}")
        await update.message.reply_text(f"⚠️ System error during synthesis: {str(e)}")

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

async def main():
    if not TOKEN or len(TOKEN) < 10:
        print("CRITICAL ERROR: Telegram Token is missing or invalid!")
        return

    print(f"DEBUG: Attempting connection (Token ends in: {TOKEN[-5:]})")

    app = Application.builder().token(TOKEN).build()
    
    job_queue = app.job_queue
    job_queue.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    job_queue.run_daily(send_scheduled_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    job_queue.run_daily(send_scheduled_briefing, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")

    # --- HANDLERS (ORDER MATTERS) ---
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(MessageHandler(filters.VOICE, core.on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print(f"--- {core.AGENT_NAME} DAEMON ACTIVE ---")
    
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping Seira...")