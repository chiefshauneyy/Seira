import os
import json
import re
import io
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List
from dotenv import load_dotenv

# Absolute pathing for launchd stability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.path.join(BASE_DIR, os.getenv("MEMORY_PATH", "memory.json"))

# Regex for command parsing
REMEMBER_RE = re.compile(r"^/remember\s+([^=\s]+)\s*=\s*(.+)\s*$", re.IGNORECASE)
NOTE_RE = re.compile(r"^/note\s+(.+)\s*$", re.IGNORECASE)

HELP_TEXT = f"""
{AGENT_NAME} Operator Commands:
  /help                Show this help
  /memory              Print current memory
  /remember <k>=<v>    Save a specific key/value
  /note <text>         Append a timestamped note
""".strip()

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {
            "name": "Shaun Constantino",
            "age": 27,
            "background": "USMC Scout Sniper / PMC / Cloud Architecture",
            "identity": "Mexican & Native American (Red Cloud descendant)",
            "location": "San Antonio, TX",
            "telegram_chat_id": None
        },
        "work": {
            "role": "Cloud Architecture Contractor",
            "projects": ["CCTAT", "n8n Ag-Market Automation", "$henanomics"],
            "rules": "Keep AOL and CCTAT documentation strictly separate."
        },
        "history": {
            "warfare": [],
            "astrophysics": []
        },
        "notes": [],
        "preferences": {
            "workflow": "Full code updates only. Git: PC push -> Mac pull."
        }
    }

def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PATH):
        return _default_memory()
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = _default_memory()
        # Ensure structural integrity for history tracking
        if "history" not in data: 
            data["history"] = base["history"]
        return data
    except Exception:
        return _default_memory()

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def llm(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    return resp.choices[0].message.content.strip()

# --- INTERFACE FUNCTIONS ---

async def on_voice(update, context):
    """Downloads voice note, transcribes with Whisper, and routes to on_message logic."""
    from telegram_bot import on_message 
    
    logging.info("Voice note received. Transcribing...")
    voice_file = await update.message.voice.get_file()
    audio_data = io.BytesIO()
    await voice_file.download_to_memory(audio_data)
    audio_data.seek(0)
    audio_data.name = "voice.ogg"

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_data).text
    
    logging.info(f"Transcript: {transcript}")
    update.message.text = transcript
    await on_message(update, context)

# --- THE LESSON ENGINE ---

def get_scheduled_lesson(topic: str, memory: Dict[str, Any]) -> str:
    history = memory.get("history", {}).get(topic, [])
    avoidance_str = ", ".join(history[-10:]) if history else "None yet."
    
    if topic == "warfare":
        system = f"You are {AGENT_NAME}. Provide a briefing on an obscure moment in warfare history."
        user = f"Operator Background: {memory['profile']['background']}. Avoid these: {avoidance_str}. Focus on tactics/snipers."
    else:
        system = f"You are {AGENT_NAME}. Provide a briefing on a complex astrophysics concept."
        user = f"Avoid these: {avoidance_str}. Explain with professional precision."

    content = llm(system, user)
    gist = llm("Summarize this lesson in 3-5 words for a log:", content)
    
    memory["history"].setdefault(topic, []).append(f"{_now_iso()}: {gist}")
    save_memory(memory)
    return f"🚀 {topic.upper()} BRIEFING:\n\n{content}"

# --- COMMAND HANDLERS ---

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip()
    if cmd.lower() == "/help": return True, HELP_TEXT, memory
    if cmd.lower() == "/memory": return True, json.dumps(memory, indent=2), memory
    
    m_rem = REMEMBER_RE.match(cmd)
    if m_rem:
        key, val = m_rem.group(1).strip(), m_rem.group(2).strip()
        memory["preferences"][key] = val
        save_memory(memory)
        return True, f"✅ Updated {key}.", memory

    m_note = NOTE_RE.match(cmd)
    if m_note:
        note_text = m_note.group(1).strip()
        memory.setdefault("notes", []).append({"ts": _now_iso(), "text": note_text})
        save_memory(memory)
        return True, "📝 Note logged.", memory

    return False, "", memory

def memory_summary(memory: Dict[str, Any]) -> str:
    p = memory.get("profile", {})
    return f"Operator: {p.get('name')} | Identity: {p.get('identity')}"