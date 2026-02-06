import os
import json
import re
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
        # Ensure new keys (like history) exist in old memory files
        base = _default_memory()
        if "history" not in data: data["history"] = base["history"]
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

# --- THE LESSON ENGINE (Anti-Repeat Logic) ---

def get_scheduled_lesson(topic: str, memory: Dict[str, Any]) -> str:
    """Generates a proactive briefing while checking memory to avoid repetition."""
    history = memory.get("history", {}).get(topic, [])
    
    # Construct the Avoidance List
    avoidance_str = ", ".join(history[-10:]) if history else "None yet."
    
    if topic == "warfare":
        system = f"You are {AGENT_NAME}. Provide a briefing on a specific, obscure moment in warfare history."
        user = f"Operator Background: {memory['profile']['background']}. Do NOT talk about these recently covered topics: {avoidance_str}. Focus on tactics or snipers if possible."
    else: # astrophysics
        system = f"You are {AGENT_NAME}. Provide a briefing on a complex astrophysics concept."
        user = f"Do NOT talk about these recently covered topics: {avoidance_str}. Explain like I am a professional who values precision."

    content = llm(system, user)
    
    # Save a 'gist' to memory to prevent future repeats
    gist_prompt = f"Summarize this lesson in 3-5 words for a memory log:\n{content}"
    gist = llm("You are a summarizer.", gist_prompt)
    
    memory["history"].setdefault(topic, []).append(f"{_now_iso()}: {gist}")
    save_memory(memory)
    
    return f"🚀 {topic.upper()} BRIEFING:\n\n{content}"

# --- HANDLERS ---

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip()
    if cmd.lower() == "/help": return True, HELP_TEXT, memory
    if cmd.lower() == "/memory": 
        # Clean view for Telegram
        return True, json.dumps(memory, indent=2), memory
    
    m_rem = REMEMBER_RE.match(cmd)
    if m_rem:
        key, val = m_rem.group(1).strip(), m_rem.group(2).strip()
        # logic to set dotted keys omitted for brevity, but keep your memory_set if needed
        memory["preferences"][key] = val
        save_memory(memory)
        return True, f"✅ Updated {key}.", memory

    return False, "", memory

def memory_summary(memory: Dict[str, Any]) -> str:
    p = memory.get("profile", {})
    return f"Operator: {p.get('name')} | Identity: {p.get('identity')}"