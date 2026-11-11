import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в файле .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY не задан в файле .env")

# Список Telegram ID администраторов через запятую, например: 123456789,987654321
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = set()
for _id in _admin_ids_raw.split(","):
    _id = _id.strip()
    if _id.isdigit():
        ADMIN_IDS.add(int(_id))

MAX_HISTORY = 20
AI_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.8-27b"
