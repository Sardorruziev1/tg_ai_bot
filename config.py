import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в файле .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY не задан в файле .env")

MAX_HISTORY = 20   # максимум сообщений в памяти на пользователя
AI_MODEL = "mixtral-8x7b-32768"  # бесплатная модель от Groq (очень быстрая)
