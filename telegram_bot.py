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

# --- SCHEDULED JOBS & TEST COMMANDS ---

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    
    if not chat_id:
        logging.error("No chat_id found in memory.")
        return

    # Determine topic
    topic = "warfare" if "warfare" in job.name else "astrophysics"
    
    # 1. Get the Lesson Text with Instagram Constraints
    ig_constraint = (
        "Write a concise, engaging lesson (max 1200 characters). "
        "Use bullet points and clear headings. End with 3 relevant hashtags."
    )
    briefing_content = core.get_scheduled_lesson(topic, memory, extra_instructions=ig_constraint)
    
    # 2. Adaptive Art Director Logic
    if topic == "warfare":
        art_director_system = (
            "You are a combat photographer using a vintage Leica. "
            "Create a technical, comma-separated prompt (max 60 words). "
            "STYLE: High-contrast black and white, heavy film grain, motion blur, "
            "f/1.4 lens, harsh shadows, authentic historical textures, raw documentary style. "
            "No digital smoothing, no text."
        )
    else: # Astrophysics
        art_director_system = (
            "You are a NASA deep-space imaging specialist. "
            "Create a technical, comma-separated prompt (max 60 words). "
            "STYLE: James Webb Telescope infrared aesthetic, ultra-sharp detail, "
            "vibrant cosmic colors, high dynamic range, deep blacks, "
            "cinematic sci-fi lighting, 8k resolution. No text."
        )
    
    visual_prompt = core.llm(art_director_system, f"Lesson Text: {briefing_content}")
    print(f"DEBUG: Art Director ({topic}) Prompt: {visual_prompt}")
    
    try:
        pipeline = ImagePipeline()
        local_path = pipeline.generate_free_image(visual_prompt)
        
        if local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as photo:
                # Caption character limit is handled by the 1200 char constraint above
                await context.bot.send_photo(
                    chat_id=chat_id, 
                    photo=photo, 
                    caption=briefing_content,
                    parse_mode="Markdown"
                )
        else:
            await context.bot.send_message(chat_id=chat_id, text=briefing_content)
            
    except Exception as e:
        logging.error(f"Briefing generation error: {e}")
        await context.bot.send_message(chat_id=chat_id, text=briefing_content)

async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers the Warfare flow."""
    if not is_allowed(update): return
    await update.message.reply_text("Copy that. Initializing Warfare Briefing (Instagram Optimized)...")
    class MockJob:
        def __init__(self, name): self.name = name
    context.job = MockJob("daily_warfare")
    await send_scheduled_briefing(context)

async def trigger_astro_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually triggers the Astrophysics flow."""
    if not is_allowed(update): return
    await update.message.reply_text("Copy that. Initializing Astrophysics Briefing (Instagram Optimized)...")
    class MockJob:
        def __init__(self, name): self.name = name
    context.job = MockJob("daily_astrophysics")
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
    if not is_allowed(update): return
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
            await update.message.reply_text("❌ Failed to secure the asset.")
    except Exception as e:
        logging.error(f"Generation error: {e}")
        await update.message.reply_text(f"⚠️ System error: {str(e)}")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    memory = core.load_memory()
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return
    system = f"You are {core.AGENT_NAME}, Shaun's personal AI companion. Maintain military bearing: concise and lethal."
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

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("test_astro", trigger_astro_test))
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