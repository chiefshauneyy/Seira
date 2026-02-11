import os
import json
import logging
from dotenv import load_dotenv
import feedparser
from newsapi import NewsApiClient
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_NAME = "SEIRA"
MEMORY_FILE = "memory.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def llm(system_prompt, user_input):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return "Internal cognition failure. Signal lost."

class IntelEngine:
    def __init__(self):
        self.newsapi = NewsApiClient(api_key=NEWS_API_KEY) if NEWS_API_KEY else None

    def get_global_intel(self, topic="warfare"):
        intel_summary = ""
        try:
            feed = feedparser.parse("https://feeds.bbci.co.uk/news/world/rss.xml")
            if feed.entries:
                for entry in feed.entries[:3]:
                    intel_summary += f"- {entry.title}\n"
            if self.newsapi:
                query = f'{topic} OR military OR geopolitics'
                top = self.newsapi.get_everything(q=query, language='en', sort_by='publishedAt', page_size=3)
                for article in top.get('articles', []):
                    intel_summary += f"- {article['title']}\n"
        except Exception as e:
            logger.error(f"Intel Error: {e}")
        return intel_summary if intel_summary else "No active signal."

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f: return json.load(f)
    return {"lessons_taught": 0, "profile": {}}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f: json.dump(memory, f, indent=4)

def get_scheduled_lesson(topic, memory):
    intel = IntelEngine()
    current_intel = intel.get_global_intel(topic)
    return f"Latest intercept for {topic.upper()}:\n{current_intel}"