import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import feedparser
from newsapi import NewsApiClient

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agent Metadata
AGENT_NAME = "SEIRA"
VERSION = "2.1.0"

# Constants
MEMORY_FILE = "memory.json"
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

class IntelEngine:
    def __init__(self):
        self.newsapi = NewsApiClient(api_key=NEWS_API_KEY) if NEWS_API_KEY else None

    def get_global_intel(self, category="warfare"):
        """Bridges RSS feeds and NewsAPI for real-time updates."""
        intel_summary = ""
        try:
            # 1. RSS Fetch (Reuters)
            feed = feedparser.parse("https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best")
            for entry in feed.entries[:3]:
                intel_summary += f"- {entry.title}\n"
            
            # 2. NewsAPI Fetch (if key available)
            if self.newsapi:
                top_headlines = self.newsapi.get_top_headlines(q='military', language='en')
                for article in top_headlines['articles'][:2]:
                    intel_summary += f"- {article['title']} (NewsAPI)\n"
        except Exception as e:
            logger.error(f"Intel Error: {e}")
            intel_summary = "Intelligence feeds currently scrambled."
        
        return intel_summary

def load_memory():
    """Loads long-term memory from JSON."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {"user_stats": {}, "lessons_taught": 0, "last_briefing": None}

def save_memory(memory):
    """Saves updated memory state."""
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)

def get_scheduled_lesson(topic, memory):
    """Generates a lesson based on topic and real-time intel."""
    intel = IntelEngine()
    current_intel = intel.get_global_intel(topic)
    
    memory["lessons_taught"] = memory.get("lessons_taught", 0) + 1
    save_memory(memory)
    
    return f"STRIKE REPORT: {topic.upper()}\n\nGlobal Intelligence:\n{current_intel}\n\nStrategic Insight: Adaptation is the only constant."
