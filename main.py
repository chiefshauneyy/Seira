import datetime
import pytz
import os
import asyncio
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import seira_core as core

# --- MISSION CONFIG ---
AGENT_NAME = "Seira"
# You'll need to find your Chat ID (I'll help with that in the next step)
MY_CHAT_ID = "REPLACE_WITH_YOUR_CHAT_ID" 

# --- AUTOMATED JOBS ---

async def send_warfare_lesson(context: ContextTypes.DEFAULT_TYPE):
    memory = core.load_memory()
    past_topics = memory.get("warfare_history", [])
    
    system = "You are a military historian. Provide a concise, epic lesson on a battle or warfare tale."
    prompt = f"Provide a new lesson. Do NOT repeat these topics: {', '.join(past_topics[-5:])}"
    
    lesson = core.llm(system, prompt)
    
    # Save gists to memory to prevent repeats
    past_topics.append(lesson[:50]) 
    core.update_memory(memory, {"warfare_history": past_topics})
    
    await context.bot.send_message(chat_id=MY_CHAT_ID, text=f"⚔️ **Morning Brief: Warfare History**\n\n{lesson}")

async def send_astrophysics_lesson(context: ContextTypes.DEFAULT_TYPE):
    system = "You are a brilliant astrophysicist."
    prompt = "Share a random, mind-bending lesson or fact about astrophysics."
    lesson = core.llm(system, prompt)
    await context.bot.send_message(chat_id=MY_CHAT_ID, text=f"🌌 **Astro Update**\n\n{lesson}")

# --- BOT INTERACTION ---

async def handle_message(update, context):
    user_input = update.message.text
    # Ensure seira_core has a function named generate_response or adjust this call
    response = core.generate_response(user_input) 
    await update.message.reply_text(response)

async def start_bot():
    token = os.environ.get("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(token).build()

    # Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler (Job Queue)
    jq = app.job_queue
    tz = pytz.timezone("America/Chicago") # Change to your timezone

    # Schedule: 0800 Warfare, 1200 & 1900 Astrophysics
    jq.run_daily(send_warfare_lesson, time=datetime.time(hour=8, minute=0, tzinfo=tz))
    jq.run_daily(send_astrophysics_lesson, time=datetime.time(hour=12, minute=0, tzinfo=tz))
    jq.run_daily(send_astrophysics_lesson, time=datetime.time(hour=19, minute=0, tzinfo=tz))

    print(f"{AGENT_NAME} background service initiated...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(start_bot())