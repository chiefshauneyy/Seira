import os
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.getenv("MEMORY_PATH", "memory.json")

REMEMBER_RE = re.compile(r"^/remember\s+([^=\s]+)\s*=\s*(.+)\s*$", re.IGNORECASE)
FORGET_RE = re.compile(r"^/forget\s+([^\s]+)\s*$", re.IGNORECASE)
NOTE_RE = re.compile(r"^/note\s+(.+)\s*$", re.IGNORECASE)
CHECKIN_RE = re.compile(r"^/checkin\s+(.+)\s*$", re.IGNORECASE)
HISTORY_RE = re.compile(r"^/history(?:\s+(\d+))?\s*$", re.IGNORECASE)

HELP_TEXT = f"""
{AGENT_NAME} commands:
  /help                Show this help
  /memory              Print current memory
  /remember <k>=<v>    Save memory
  /forget <key>        Delete memory key
  /note <text>         Append a note
  /checkin k=v ...     Log readiness metrics
  /today               Readiness score
  /history [n]         Last n check-ins

Telegram quick actions:
  note: <text>
  checkin: sleep=...
  remind: in 30m <text>
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
    """Returns a readable summary for Telegram."""
    notes_count = len(memory.get("notes", []))
    checkins_count = len(memory.get("checkins", []))
    reminders = [r for r in memory.get("reminders", []) if not r.get("sent")]
    return f"🧠 {AGENT_NAME} Memory Status\n📝 Notes: {notes_count}\n📊 Check-ins: {checkins_count}\n⏰ Reminders: {len(reminders)}"

def memory_set(memory: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur = memory
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def memory_delete(memory: Dict[str, Any], dotted_key: str) -> bool:
    parts = dotted_key.split(".")
    cur = memory
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    if isinstance(cur, dict) and parts[-1] in cur:
        del cur[parts[-1]]
        return True
    return False

# -------------------------
# Fitness & LLM Logic
# -------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def compute_readiness(checkin: Dict[str, Any], prev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sleep = float(checkin.get("sleep", 7))
    score = clamp(sleep * 10, 0, 100) # Simplified for now
    return {"score": int(score), "label": "READY", "reasons": [], "recommendation": "Maintain consistency."}

def llm(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    return resp.choices[0].message.content.strip()

# -------------------------
# Parsers & Handlers
# -------------------------

def parse_kv_pairs(s: str) -> Dict[str, Any]:
    out = {}
    for t in s.strip().split():
        if "=" in t:
            k, v = t.split("=", 1)
            try: out[k.lower()] = float(v) if "." in v else int(v)
            except: out[k.lower()] = v
    return out

def parse_remind_spec(spec: str) -> Tuple[Optional[datetime], str]:
    m = re.match(r"^in\s+(\d+)\s*([mhd])\s+(.+)$", spec, re.IGNORECASE)
    if m:
        n, unit, text = int(m.group(1)), m.group(2).lower(), m.group(3)
        delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
        return datetime.now() + delta, text
    return None, ""

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip().lower()
    if cmd == "/memory":
        return True, memory_pretty(memory), memory
    if cmd == "/help":
        return True, HELP_TEXT, memory
    return False, "", memory

def save_pending_action(memory: Dict[str, Any], action: Dict[str, Any]) -> str:
    action_id = f"act_{int(datetime.now().timestamp())}"
    memory.setdefault("pending_actions", {})
    memory["pending_actions"][action_id] = {"ts": _now_iso(), **action}
    save_memory(memory)
    return action_id

def execute_action(memory: Dict[str, Any], action_id: str) -> str:
    pending = memory.get("pending_actions", {})
    if action_id not in pending: return "Action not found."
    action = pending[action_id].get("action", {})
    # Minimal logic for now
    del pending[action_id]
    save_memory(memory)
    return f"Executed: {action.get('type')}"