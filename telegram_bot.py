import os
import asyncio
import io
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import seira_core as core

load_dotenv(dotenv_path=".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()

def is_allowed(update: Update) -> bool:
    user = update.effective_user
    if not user: return False
    current_id = str(user.id)
    if not ALLOWED_USER_ID: return True
    return current_id == ALLOWED_USER_ID

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    mem = core.load_memory()
    mem.setdefault("profile", {})["telegram_chat_id"] = update.effective_chat.id
    core.save_memory(mem)
    await update.message.reply_text(f"{core.AGENT_NAME} online. Use /help.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    await update.message.reply_text(core.HELP_TEXT)

async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    memory = core.load_memory()
    await update.message.reply_text(f"```json\n{core.memory_pretty(memory)}\n```", parse_mode="Markdown")

async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    full_text = f"/remember {' '.join(context.args)}"
    handled, reply, _ = core.handle_command(full_text, core.load_memory())
    await update.message.reply_text(reply if handled else "Usage: /remember key=value")

async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    full_text = f"/note {' '.join(context.args)}"
    handled, reply, _ = core.handle_command(full_text, core.load_memory())
    await update.message.reply_text(reply if handled else "Usage: /note your text here")

async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Downloads voice note, transcribes with Whisper, and processes."""
    if not is_allowed(update): return
    print("Voice note received. Transcribing...")
    
    voice_file = await update.message.voice.get_file()
    audio_data = io.BytesIO()
    await voice_file.download_to_memory(audio_data)
    audio_data.seek(0)
    audio_data.name = "voice.ogg"

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_data).text
    
    print(f"Transcript: {transcript}")
    update.message.text = transcript
    await on_message(update, context)

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update): return
    text = update.message.text.strip()
    memory = core.load_memory()
    
    # Check for core commands hidden in text
    handled, reply, _ = core.handle_command(text, memory)
    if handled:
        await update.message.reply_text(reply)
        return

    system = (
        f"You are {core.AGENT_NAME}, Shaun's personal stateful AI companion. "
        "You are an expert in USMC scout sniper discipline and cloud architecture. "
        "Use memory to provide structured, step-by-step assistance."
    )
    user_msg = f"Memory Summary:\n{core.memory_summary(memory)}\n\nUser: {text}"
    await update.message.reply_text(core.llm(system, user_msg))

async def main_async():
    if not TOKEN: return
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("note", cmd_note))
    
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    async with app:
        await app.initialize()
        await app.start()
        print(f"--- {core.AGENT_NAME} READY ---")
        await app.updater.start_polling()
        while True: await asyncio.sleep(1)

def main():
    try: asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit): pass

if __name__ == "__main__":
    main()