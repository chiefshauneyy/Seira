import os
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.getenv("MEMORY_PATH", "memory.json")

# Regex for command parsing
REMEMBER_RE = re.compile(r"^/remember\s+([^=\s]+)\s*=\s*(.+)\s*$", re.IGNORECASE)

HELP_TEXT = f"""
{AGENT_NAME} commands:
  /help                Show this help
  /memory              Print current memory
  /remember <k>=<v>    Save a specific key/value
  /note <text>         Append a note
  /today               Readiness score
""".strip()

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {"telegram_chat_id": None},
        "preferences": {},
        "rules": {"execution_mode": "approval"},
        "fitness": {},
        "notes": [],
        "checkins": [],
        "reminders": [],
        "pending_actions": {}
    }

def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PATH):
        return _default_memory()
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = _default_memory()
        for k, v in base.items():
            data.setdefault(k, v)
        return data
    except Exception:
        return _default_memory()

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def memory_pretty(memory: Dict[str, Any]) -> str:
    return json.dumps(memory, indent=2, ensure_ascii=False)

def memory_summary(memory: Dict[str, Any]) -> str:
    notes_count = len(memory.get("notes", []))
    prefs = memory.get("preferences", {})
    summary = [
        f"🧠 {AGENT_NAME} Memory Status",
        f"📝 Notes: {notes_count}",
        f"⚙️ Preferences: {list(prefs.keys()) if prefs else 'None'}"
    ]
    return "\n".join(summary)

def memory_set(memory: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur = memory
    # We default to saving custom things in 'preferences' if no root is specified
    if parts[0] not in memory:
        parts.insert(0, "preferences")
        
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def llm(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    return resp.choices[0].message.content.strip()

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip()
    
    if cmd.lower() == "/help":
        return True, HELP_TEXT, memory
    
    if cmd.lower() == "/memory":
        return True, memory_pretty(memory), memory

    # Handle /remember key=value
    m = REMEMBER_RE.match(cmd)
    if m:
        key = m.group(1).strip()
        val = m.group(2).strip()
        memory_set(memory, key, val)
        save_memory(memory)
        return True, f"✅ I've remembered that {key} is {val}.", memory

    return False, "", memory

def execute_action(memory: Dict[str, Any], action_id: str) -> str:
    pending = memory.get("pending_actions", {})
    if action_id not in pending: return "Action not found."
    del pending[action_id]
    save_memory(memory)
    return "Action executed."