import os
import json
import re
import io
import logging
import feedparser
from newsapi import NewsApiClient
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, List
from dotenv import load_dotenv

# Absolute pathing for launchd stability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.path.join(BASE_DIR, os.getenv("MEMORY_PATH", "memory.json"))
NEWS_KEY = os.getenv("NEWS_API_KEY")

# --- INTEL ENGINE ---

class IntelEngine:
    def __init__(self):
        self.api = NewsApiClient(api_key=NEWS_KEY) if NEWS_KEY else None

    def get_global_briefing(self, query: str = "geopolitics OR military technology") -> str:
        """Fetches real-time news and formats it as a tactical briefing."""
        if not self.api:
            return "⚠️ Intel Link Offline: Missing NewsAPI Key."
        
        try:
            # Fetch latest headlines
            top_headlines = self.api.get_everything(q=query, language='en', sort_by='publishedAt', page_size=3)
            articles = top_headlines.get('articles', [])
            
            if not articles:
                return "📡 Scanning... No immediate threats or developments detected in current sectors."

            intel_report = "📰 **CURRENT INTEL FEED**\n\n"
            for art in articles:
                source = art['source']['name']
                title = art['title']
                url = art['url']
                intel_report += f"🔹 **{source}**: {title}\n🔗 [Source]({url})\n\n"
            
            return intel_report
        except Exception as e:
            return f"❌ Intel acquisition failed: {str(e)}"

intel_center = IntelEngine()

# --- MODIFIED LESSON ENGINE (Now with News Integration) ---

def get_scheduled_lesson(topic: str, memory: Dict[str, Any]) -> str:
    history = memory.get("history", {}).get(topic, [])
    interest_level = memory.get("interests", {}).get(topic, 0)
    avoidance_str = ", ".join(history[-10:]) if history else "None yet."
    
    # NEW: Fetch real-world context for the 8 AM Warfare briefing
    news_context = ""
    if topic == "warfare":
        news_context = intel_center.get_global_briefing("Ukraine OR Middle East OR Taiwan Strait")

    depth = "introductory" if interest_level < 5 else "highly technical/obscure"
    
    if topic == "warfare":
        system = f"You are {AGENT_NAME}. Provide a {depth} briefing on warfare history, but try to bridge it with current world events."
        user = (f"Operator Background: {memory['profile']['background']}. "
                f"Current News Context: {news_context}. Avoid these: {avoidance_str}. Focus on snipers/tactics.")
    else:
        system = f"You are {AGENT_NAME}. Provide a {depth} briefing on a complex astrophysics concept."
        user = f"Interest Score: {interest_level}. Avoid these: {avoidance_str}. Professional precision."

    content = llm(system, user)
    gist = llm("Summarize this in 3-5 words:", content)
    
    memory["history"].setdefault(topic, []).append(f"{_now_iso()}: {gist}")
    save_memory(memory)
    
    return f"🚀 {topic.upper()} BRIEFING:\n\n{content}\n\n{news_context}"

# --- COMMAND HANDLERS ---

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip()
    
    # Auto-track interest whenever a message is processed
    track_engagement(cmd, memory)
    
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