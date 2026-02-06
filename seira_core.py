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
        # Ensure deep merge of default keys if missing
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
    cmd = text.strip().lower()
    
    if cmd == "/today":
        # Get fitness data
        checkins = memory.get("checkins", [])
        last = checkins[-1] if checkins else {"sleep": 7, "stress": 5}
        r = compute_readiness(last) # Uses the logic we defined earlier
        
        # Get Work/Identity Context
        p = memory.get("profile", {})
        w = memory.get("work", {})
        
        brief = [
            f"⚔️ **Operator Brief: {datetime.now().strftime('%Y-%m-%d')}**",
            f"Status: {r['label']} ({r['score']}/100)",
            f"\n**Physical:**",
            f"- Recommendation: {r['recommendation']}",
            f"- Goal: {memory['fitness']['program']}",
            f"\n**Operations:**",
            f"- Project Alpha: {w['projects'][0]} (CCTAT)",
            f"- Project Beta: {w['projects'][1]} (n8n Automation)",
            f"\n**Rule of Engagement:** {w['rules']}"
        ]
        return True, "\n".join(brief), memory

def execute_action(memory: Dict[str, Any], action_id: str) -> str:
    pending = memory.get("pending_actions", {})
    if action_id not in pending: return "Action not found."
    del pending[action_id]
    save_memory(memory)
    return "Action approved and executed."