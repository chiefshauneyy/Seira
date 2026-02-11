import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import feedparser
from newsapi import NewsApiClient
import google.generativeai as genai

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agent Metadata
AGENT_NAME = "SEIRA"
VERSION = "2.1.0"
MEMORY_FILE = "memory.json"

# API Setup
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def llm(system_prompt, user_input):
    """The central thinking engine for Seira."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Combine prompts for a single-shot completion
        full_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {user_input}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return "Internal cognition failure. Signal lost."

class IntelEngine:
    def __init__(self):
        self.newsapi = NewsApiClient(api_key=NEWS_API_KEY) if NEWS_API_KEY else None

    def get_global_intel(self, category="warfare"):
        intel_summary = ""
        try:
            feed = feedparser.parse("https://feeds.bbci.co.uk/news/world/rss.xml")
            if feed.entries:
                for entry in feed.entries[:3]:
                    intel_summary += f"- {entry.title}\n"
            
            if self.newsapi:
                query = f'{category} OR geopolitics OR military'
                if category in ["cybersecurity", "quantum computing"]:
                    query = f'"{category}" OR technology'
                
                top_headlines = self.newsapi.get_everything(
                    q=query, 
                    language='en', 
                    sort_by='publishedAt',
                    page_size=3
                )
                for article in top_headlines.get('articles', []):
                    intel_summary += f"- {article['title']} (NewsAPI)\n"
        except Exception as e:
            logger.error(f"Intel Error: {e}")
            intel_summary = "Intelligence feeds scrambled."
        
        return intel_summary if intel_summary else "No active signal detected."

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"user_stats": {}, "lessons_taught": 0, "profile": {}}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)

def get_scheduled_lesson(topic, memory):
    intel = IntelEngine()
    current_intel = intel.get_global_intel(topic)
    return f"Latest intercept for {topic.upper()}:\n{current_intel}"