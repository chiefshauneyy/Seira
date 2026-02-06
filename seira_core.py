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
NOTE_RE = re.compile(r"^/note\s+(.+)\s*$", re.IGNORECASE)

HELP_TEXT = f"""
{AGENT_NAME} Operator Commands:
  /help                Show this help
  /memory              Print current memory
  /remember <k>=<v>    Save a specific key/value
  /note <text>         Append a timestamped note
  /today               Readiness score & training rec
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
            "projects": ["CCTAT (formerly TDY Tracker)", "n8n Ag-Market Automation", "$henanomics"],
            "rules": "Keep AOL and CCTAT documentation strictly separate."
        },
        "fitness": {
            "weight_goal": "Recomp/Cut",
            "program": "2x/day Tue-Sat, Arms 3x/week, Recon Ron Pull-ups",
            "stats": {"last_reported_weight": 192}
        },
        "preferences": {
            "workflow": "Full code updates only. Git: PC push -> Mac pull.",
            "communication": "Step-by-step, clean checklists, exact commands."
        },
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
            if k not in data:
                data[k] = v
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    data[k].setdefault(sub_k, sub_v)
        return data
    except Exception:
        return _default_memory()

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def memory_pretty(memory: Dict[str, Any]) -> str:
    return json.dumps(memory, indent=2, ensure_ascii=False)

def memory_summary(memory: Dict[str, Any]) -> str:
    p = memory.get("profile", {})
    w = memory.get("work", {})
    return (
        f"👤 Operator: {p.get('name')} | {p.get('background')}\n"
        f"📍 Location: {p.get('location')}\n"
        f"🚧 Active Work: {', '.join(w.get('projects', []))}\n"
        f"🛠️ Rule: {w.get('rules')}"
    )

def memory_set(memory: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur = memory
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
    if cmd.lower() == "/help": return True, HELP_TEXT, memory
    if cmd.lower() == "/memory": return True, memory_pretty(memory), memory
    
    m_rem = REMEMBER_RE.match(cmd)
    if m_rem:
        key, val = m_rem.group(1).strip(), m_rem.group(2).strip()
        memory_set(memory, key, val)
        save_memory(memory)
        return True, f"✅ Updated: {key} is now {val}.", memory

    m_note = NOTE_RE.match(cmd)
    if m_note:
        note_text = m_note.group(1).strip()
        memory.setdefault("notes", []).append({"ts": _now_iso(), "text": note_text})
        save_memory(memory)
        return True, f"📝 Note logged to memory.", memory

    return False, "", memory

def execute_action(memory: Dict[str, Any], action_id: str) -> str:
    pending = memory.get("pending_actions", {})
    if action_id not in pending: return "Action not found."
    del pending[action_id]
    save_memory(memory)
    return "Action approved."