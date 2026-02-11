import os
import json
import re
import io
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List
from dotenv import load_dotenv
from openai import OpenAI

# Absolute pathing for launchd stability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.path.join(BASE_DIR, os.getenv("MEMORY_PATH", "memory.json"))

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Regex for command parsing
REMEMBER_RE = re.compile(r"^/remember\s+([^=\s]+)\s*=\s*(.+)\s*$", re.IGNORECASE)
NOTE_RE = re.compile(r"^/note\s+(.+)\s*$", re.IGNORECASE)

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {
            "name": "Shaun Constantino",
            "background": "USMC Scout Sniper / PMC / Cloud Architecture",
            "telegram_chat_id": None
        },
        "history": {"warfare": [], "astrophysics": [], "lore": []},
        "interests": {"warfare": 0, "astrophysics": 0, "cybersecurity": 0, "lore": 0},
        "notes": [],
        "preferences": {}
    }

def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PATH): return _default_memory()
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Integrity checks
            if "interests" not in data: data["interests"] = _default_memory()["interests"]
            if "history" not in data: data["history"] = _default_memory()["history"]
            return data
    except Exception: return _default_memory()

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def llm(system: str, user: str, model="gpt-4o-mini") -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    return resp.choices[0].message.content.strip()

def get_scheduled_lesson(topic: str, memory: Dict[str, Any]) -> str:
    history = memory.get("history", {}).get(topic, [])
    interest_level = memory.get("interests", {}).get(topic, 0)
    avoidance_str = ", ".join(history[-10:]) if history else "None yet."
    depth = "introductory" if interest_level < 5 else "highly technical/obscure"
    
    if topic == "warfare":
        system = f"You are {AGENT_NAME}. Provide a {depth} briefing on an obscure moment in warfare history."
        user = f"Operator Background: {memory['profile']['background']}. Avoid: {avoidance_str}. Focus on tactics/snipers."
    elif topic == "astrophysics":
        system = f"You are {AGENT_NAME}. Provide a {depth} briefing on a complex astrophysics concept."
        user = f"Avoid: {avoidance_str}. Explain with professional precision."
    else: # Lore
        system = f"You are {AGENT_NAME}. Provide a briefing on Dune universe lore. Focus on strategy/history."
        user = f"Avoid: {avoidance_str}. Maintain cold academic tone."

    content = llm(system, user, model="gpt-4o")
    gist = llm("Summarize this lesson in 3-5 words for a log:", content)
    memory["history"].setdefault(topic, []).append(f"{_now_iso()}: {gist}")
    save_memory(memory)
    return content

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip()
    # Track interest
    for topic in memory["interests"].keys():
        if topic in cmd.lower(): memory["interests"][topic] += 1
    save_memory(memory)

    if cmd.lower() == "/memory": return True, json.dumps(memory, indent=2), memory
    m_rem = REMEMBER_RE.match(cmd)
    if m_rem:
        key, val = m_rem.group(1).strip(), m_rem.group(2).strip()
        memory["preferences"][key] = val
        save_memory(memory); return True, f"✅ Updated {key}.", memory
    return False, "", memory