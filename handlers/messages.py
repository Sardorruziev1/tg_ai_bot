import logging
from groq import (
    AsyncGroq, APIError, APIConnectionError, APIStatusError,
    RateLimitError, AuthenticationError,
)
from aiogram import Router
from aiogram.types import Message
from config import GROQ_API_KEY, AI_MODEL, HISTORY_CHAR_BUDGET
from database import get_user_mode, get_history, add_message

router = Router()
client = AsyncGroq(api_key=GROQ_API_KEY, timeout=60.0, max_retries=2)
log = logging.getLogger(__name__)

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


def trim_history(history: list, budget: int) -> list:
    """Оставляем самые свежие сообщения, пока они влезают в бюджет символов."""
    kept, used = [], 0
    for msg in reversed(history):
        content = msg["content"]
        if len(content) > 1500:  # длинный реферат в памяти храним в сокращённом виде
            content = content[:1500] + " …"
        used += len(content)
        if used > budget:
            break
        kept.append({"role": msg["role"], "content": content})
    return list(reversed(kept))


def split_text(text: str, size: int = 4000) -> list[str]:
    """Режем длинный ответ на куски, которые Telegram примет (лимит 4096)."""
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


@router.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer("Пока работаю только с текстом. Отправь текстовое сообщение 📝")
        return

    user_id = message.from_user.id
    user_text = message.text.strip()

    mode = await get_user_mode(user_id)
    history = await get_history(user_id)

    await message.bot.send_chat_action(message.chat.id, "typing")
    await add_message(user_id, "user", user_text)

    # Системный промпт передаётся как первое сообщение с role="system" (так требует Groq)
    api_messages = [{"role": "system", "content": SYSTEM_PROMPTS[mode]}]
    # Чем длиннее новое сообщение, тем меньше старой истории отправляем
    api_messages += trim_history(history, max(0, HISTORY_CHAR_BUDGET - len(user_text)))
    api_messages.append({"role": "user", "content": user_text})

    try:
        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=api_messages,
            max_tokens=2048,
            temperature=0.7,
        )
        reply = (response.choices[0].message.content or "").strip() or "Не получилось сформировать ответ, попробуй ещё раз."

        await add_message(user_id, "assistant", reply)

        for part in split_text(reply):
            await message.answer(part)

    except AuthenticationError:
        log.error("Неверный GROQ_API_KEY")
        await message.answer("❌ Неверный ключ Groq. Проверь GROQ_API_KEY в Secrets.")
    except RateLimitError:
        log.warning("Достигнут лимит бесплатного тарифа Groq")
        await message.answer(
            "⏳ Достигнут лимит запросов. Подожди минуту и попробуй снова.\n"
            "Если не помогает — дневной лимит закончился, он обновится завтра."
        )
    except APIStatusError as e:
        if e.status_code == 413:
            await message.answer(
                "📏 Текст слишком длинный для одного запроса. Раздели его на 2–3 части "
                "и отправь по очереди. Команда /clear тоже освобождает место."
            )
        else:
            log.exception("Ошибка API Groq (%s): %s", e.status_code, e)
            await message.answer(
                "⚠️ Сервис ИИ вернул ошибку. Если это повторяется — проверь AI_MODEL в Secrets "
                "(модель могла быть снята)."
            )
    except APIConnectionError:
        log.exception("Нет связи с Groq")
        await message.answer("🌐 Нет связи с сервисом ИИ. Попробуй через несколько секунд.")
    except APIError as e:
        # Здесь будет причина, если сменилась модель (например, снята с сервиса)
        log.exception("Ошибка API Groq: %s", e)
        await message.answer(
            "⚠️ Сервис ИИ вернул ошибку. Если это повторяется — проверь AI_MODEL в Secrets "
            "(модель могла быть снята)."
        )
    except Exception:
        log.exception("Неизвестная ошибка")
        await message.answer("⚠️ Что-то пошло не так. Попробуй ещё раз.")
