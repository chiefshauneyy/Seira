import os
import json
import re
import logging
from datetime import datetime
from typing import Any, Dict, Tuple
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.path.join(BASE_DIR, "memory.json")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PATH):
        return {"profile": {"telegram_chat_id": None}, "history": {}, "interests": {}}
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def llm(system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}]
    )
    return resp.choices[0].message.content.strip()

def get_scheduled_lesson(topic: str, memory: Dict[str, Any]) -> str:
    history = memory.get("history", {}).get(topic, [])
    avoidance = ", ".join(history[-10:]) if history else "None"
    
    system = f"You are {AGENT_NAME}. Provide a deep-dive tactical briefing on {topic}."
    user = f"Avoid these previous topics: {avoidance}. Focus on technical precision."
    
    content = llm(system, user)
    gist = llm("Summarize in 3 words:", content)
    memory.setdefault("history", {}).setdefault(topic, []).append(f"{_now_iso()}: {gist}")
    save_memory(memory)
    return content

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str]:
    if text.lower() == "/memory":
        return True, json.dumps(memory, indent=2)
    return False, ""