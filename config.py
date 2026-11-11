import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в Secrets/.env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY не задан в Secrets/.env")

MAX_HISTORY = 10          # сколько последних сообщений помнит бот
HISTORY_CHAR_BUDGET = 5000  # общий объём истории в символах (бесплатный тариф Groq: ~8000 токенов в минуту)

# Модель можно поменять в Secrets (ключ AI_MODEL), без правки кода.
# Актуальный список моделей: https://console.groq.com/docs/models
AI_MODEL = os.getenv("AI_MODEL", "openai/gpt-oss-120b").strip()
