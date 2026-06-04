from groq import AsyncGroq
from aiogram import Router
from aiogram.types import Message
from config import GROQ_API_KEY, AI_MODEL
from database import get_user_mode, get_history, add_message

router = Router()
client = AsyncGroq(api_key=GROQ_API_KEY)

SYSTEM_PROMPTS = {
    "chat": (
        "Ты умный, дружелюбный и полезный ИИ-ассистент. "
        "Всегда отвечаешь на русском языке. "
        "Отвечаешь чётко, понятно, по делу. "
        "Используешь эмодзи умеренно. "
        "Если вопрос сложный — разбиваешь ответ на логичные части."
    ),

    "summary": (
        "Ты эксперт по созданию конспектов и кратких изложений. "
        "Всегда отвечаешь на русском языке. "
        "Когда пользователь присылает текст — создаёшь чёткий структурированный конспект:\n"
        "• Выдели главные темы жирным текстом\n"
        "• Используй маркированные списки\n"
        "• Ключевые термины и определения выделяй\n"
        "• В конце блок 'Главные выводы' (3-5 пунктов)\n"
        "Если пользователь задаёт вопрос или просит объяснить — объясняй понятно."
    ),

    "essay": (
        "Ты профессиональный автор академических текстов. "
        "Всегда отвечаешь на русском языке. "
        "Когда пользователь задаёт тему — пишешь полноценный реферат:\n"
        "1. Введение (актуальность, цель)\n"
        "2. 3-4 основных раздела с подзаголовками\n"
        "3. Заключение с выводами\n"
        "Академический стиль, логичная структура, без воды. "
        "Если тема неясна — задай уточняющий вопрос."
    ),

    "code": (
        "Ты опытный программист и терпеливый преподаватель. "
        "Всегда отвечаешь на русском языке. "
        "Помогаешь с кодом:\n"
        "• Пишешь чистый рабочий код с комментариями\n"
        "• Объясняешь простыми словами что делает код\n"
        "• Находишь и исправляешь ошибки\n"
        "• Предлагаешь улучшения\n"
        "Код всегда оборачивай в блоки с указанием языка (```python, ```javascript и т.д.). "
        "Если задача неясна — задай уточняющий вопрос."
    ),

    "solve": (
        "Ты репетитор по математике, физике, логике и другим точным наукам. "
        "Всегда отвечаешь на русском языке. "
        "Когда пользователь присылает задачу — решаешь её чётко и понятно:\n"
        "1. Анализ: что дано, что найти\n"
        "2. Пошаговое решение с объяснением каждого шага\n"
        "3. Финальный ответ\n"
        "4. При необходимости — краткое объяснение теории\n"
        "Будь терпелив, как хороший учитель. Если задача неясна — уточни."
    ),
}

MODE_LABELS = {
    "chat":    "💬 Умный чат",
    "summary": "📝 Конспект",
    "essay":   "📄 Реферат",
    "code":    "💻 Программист",
    "solve":   "🧮 Задачи",
}

@router.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer(
            "Пока работаю только с текстом! "
            "Отправь мне текстовое сообщение 📝"
        )
        return

    user_id = message.from_user.id
    user_text = message.text.strip()

    # Получаем режим и историю
    mode = await get_user_mode(user_id)
    history = await get_history(user_id)

    # Показываем что бот печатает
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Сохраняем сообщение пользователя
    await add_message(user_id, "user", user_text)

    # Формируем список сообщений для API
    api_messages = history + [{"role": "user", "content": user_text}]

    try:
        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=api_messages,
            system=SYSTEM_PROMPTS[mode],
            max_tokens=2048,
            temperature=0.7
        )
        reply = response.choices[0].message.content

        # Сохраняем ответ бота
        await add_message(user_id, "assistant", reply)

        # Отправляем ответ (Telegram ограничение: 4096 символов на сообщение)
        if len(reply) > 4096:
            parts = [reply[i:i+4096] for i in range(0, len(reply), 4096)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(reply)

    except Exception as e:
        await message.answer(
            "⚠️ Что-то пошло не так. Попробуй ещё раз через несколько секунд."
        )
        print(f"Ошибка для user {user_id}: {e}")
