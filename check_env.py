import os
from dotenv import load_dotenv

load_dotenv()

print("--- ENV CHECK ---")
print(f"Token Found: {bool(os.getenv('TELEGRAM_BOT_TOKEN'))}")
print(f"User ID: {os.getenv('TELEGRAM_ALLOWED_USER_ID')}")
print(f"OpenAI Key Found: {bool(os.getenv('OPENAI_API_KEY'))}")
print("-----------------")