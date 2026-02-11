import os
import json
import re
import io
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.path.join(BASE_DIR, "memory.json")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {"name": "Shaun Constantino", "background": "USMC Scout Sniper", "telegram_chat_id": None},
        "history": {"warfare": [], "astrophysics": [], "lore": []},
        "interests": {"warfare": 0, "astrophysics": 0, "cybersecurity": 0, "lore": 0},
        "preferences": {}
    }

def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PATH): return _default_memory()
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return _default_memory()

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
    avoidance = ", ".join(history[-10:]) if history else "None"
    
    if topic == "warfare":
        sys = f"You are {AGENT_NAME}. Obscure warfare history briefing."
        usr = f"Focus: Tactics/Snipers. Avoid: {avoidance}."
    elif topic == "astrophysics":
        sys = f"You are {AGENT_NAME}. Complex astrophysics briefing."
        usr = f"Precision scale. Avoid: {avoidance}."
    else:
        sys = f"You are {AGENT_NAME}. Dune lore archive."
        usr = f"Strategy focus. Avoid: {avoidance}."

    content = llm(sys, usr, model="gpt-4o")
    gist = llm("3-5 word summary:", content)
    memory.setdefault("history", {}).setdefault(topic, []).append(f"{_now_iso()}: {gist}")
    save_memory(memory)
    return content