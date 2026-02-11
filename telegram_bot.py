import os
import asyncio
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

# Absolute Pathing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "8568467650:AAHnleqe6B1GTXc1ZmQvb9VTKdOMLOgccBk"
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()
TIMEZONE = pytz.timezone("America/Chicago")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    return str(user.id) == ALLOWED_USER_ID if user else False

# --- SCHEDULED JOBS & TEST COMMANDS ---

async def send_scheduled_briefing(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    
    if not chat_id:
        logging.error("No chat_id found in memory.")
        return

    topic = "warfare" if "warfare" in job.name else "astrophysics"
    
    try:
        # 1. Get raw lesson
        raw_content = core.get_scheduled_lesson(topic, memory)
        
        # 2. Scientific/Historical Formatter (No Emojis, Professional Tone)
        formatter_system = (
            "You are a Senior Editor at a prestigious Academic Journal. "
            "Rewrite the content into a serious, high-level briefing. "
            "RULES: No emojis. No marketing speak. Max 950 characters. "
            "Use clear bold headers. End with 3 technical hashtags."
        )
        briefing_content = core.llm(formatter_system, raw_content)
        
        # 3. Adaptive Art Director (Banning Text and Diagrams)
        if topic == "warfare":
            art_director_system = (
                "Technical prompt for AI image: 35mm black and white film, "
                "grainy documentary style, high contrast, raw historical photography. "
                "NO TEXT, NO LABELS, NO WATERMARKS."
            )
        else: # Astrophysics
            art_director_system = (
                "Technical prompt for AI image: Cinematic deep space photography, "
                "James Webb Telescope aesthetic, high dynamic range, ultra-realistic "
                "render of cosmic phenomena. NO TEXT, NO DIAGRAMS, NO INFOGRAPHICS."
            )
        
        visual_prompt = core.llm(art_director_system, f"Topic: {topic}. Subject: {briefing_content[:150]}")
        print(f"DEBUG: Art Director ({topic}) Prompt: {visual_prompt}")

        # 4. Image Generation
        pipeline = ImagePipeline()
        local_path = pipeline.generate_free_image(visual_prompt)
        
        if local_path and os.path.exists(local_path):
            with open(local_path, 'rb') as photo:
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
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Synthesis failed: {str(e)}")

async def trigger_war_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Copy. Initializing Warfare Briefing (IG Optimized)...")
    class MockJob:
        def __init__(self, name): self.name = name
    context.job = MockJob("daily_warfare")
    await send_scheduled_briefing(context)

async def trigger_astro_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text("Copy. Initializing Astrophysics Briefing (IG Optimized)...")
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

async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Usage: /generate [prompt]")
        return
    await update.message.reply_text(f"🎨 Synthesizing: '{prompt}'...")
    try:
        pipeline = ImagePipeline()
        path = pipeline.generate_free_image(prompt)
        if path:
            with open(path, 'rb') as f:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    memory = core.load_memory()
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return
    system = f"You are {core.AGENT_NAME}, Shaun's personal AI companion. Military bearing."
    await update.message.reply_text(core.llm(system, f"User: {text}"))

async def main():
    app = Application.builder().token(TOKEN).build()
    
    # Schedule
    jq = app.job_queue
    jq.run_daily(send_scheduled_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    jq.run_daily(send_scheduled_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    jq.run_daily(send_scheduled_briefing, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")

    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("test_war", trigger_war_test))
    app.add_handler(CommandHandler("test_astro", trigger_astro_test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print(f"--- {core.AGENT_NAME} DAEMON ACTIVE ---")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())