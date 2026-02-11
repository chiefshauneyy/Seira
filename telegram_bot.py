import os
import asyncio
import logging
from datetime import time, datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import seira_core as core
from image_pipeline import ImagePipeline

TIMEZONE = pytz.timezone("America/Chicago")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "7065094951").strip()

async def send_briefing(context: ContextTypes.DEFAULT_TYPE):
    job_name = context.job.name
    memory = core.load_memory()
    chat_id = memory.get("profile", {}).get("telegram_chat_id")
    if not chat_id: return

    # Determine Topic
    if "warfare" in job_name: topic = "warfare"
    elif "astrophysics" in job_name: topic = "astrophysics"
    elif "lore" in job_name: topic = "lore"
    else: topic = "cybersecurity" # News fallback

    try:
        if topic in ["warfare", "astrophysics"]:
            raw = core.get_scheduled_lesson(topic, memory)
            formatter = "Tactical Intelligence Officer. Cold, academic. Bold headers. 3-4 bullets. Max 800 chars. No emojis."
            content = core.llm(formatter, raw)
            
            prompt = "Cinematic 35mm film photography, 1940s grain, B&W, raw realism." if topic == "warfare" else "Dune 2021 aesthetic, massive brutalist monolith, 8k."
            path = ImagePipeline().generate_free_image(prompt)
            if path:
                with open(path, 'rb') as f:
                    await context.bot.send_photo(chat_id=chat_id, photo=f, caption=content, parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=chat_id, text=content, parse_mode="Markdown")
        else:
            # News/Lore: Text Only
            content = core.get_scheduled_lesson(topic, memory) if topic == "lore" else core.llm("Briefing on cybersecurity trends.", "Generate pulse.")
            await context.bot.send_message(chat_id=chat_id, text=content, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Pulse Error: {e}")

# --- COMMANDS ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ALLOWED_USER_ID: return
    mem = core.load_memory()
    mem["profile"]["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text("SEIRA Initialized. Pulse Sync: Active.")

async def test_war(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ALLOWED_USER_ID: return
    class MockJob: name = "daily_warfare"
    context.job = MockJob(); await send_briefing(context)

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ALLOWED_USER_ID: return
    text = update.message.text
    memory = core.load_memory()
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return
    await update.message.reply_text(core.llm(f"You are {core.AGENT_NAME}, military bearing.", text))

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("test_war", test_war))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    jq = app.job_queue
    jq.run_daily(send_briefing, time(7, 0, tzinfo=TIMEZONE), name="morning_lore")
    jq.run_daily(send_briefing, time(8, 0, tzinfo=TIMEZONE), name="daily_warfare")
    jq.run_daily(send_briefing, time(12, 0, tzinfo=TIMEZONE), name="noon_astrophysics")
    jq.run_daily(send_briefing, time(15, 0, tzinfo=TIMEZONE), name="news_cyber")
    jq.run_daily(send_briefing, time(19, 0, tzinfo=TIMEZONE), name="evening_astrophysics")
    jq.run_daily(send_briefing, time(20, 0, tzinfo=TIMEZONE), name="news_quantum")
    jq.run_daily(send_briefing, time(21, 0, tzinfo=TIMEZONE), name="night_lore")

    print(f"--- {core.AGENT_NAME} ONLINE ---")
    app.run_polling()

if __name__ == "__main__":
    main()