import base64
from groq import AsyncGroq
from aiogram import Router, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import GROQ_API_KEY, AI_MODEL, VISION_MODEL
from database import (
    get_user_mode, get_history, add_message, ensure_user,
    can_send_message, increment_daily_usage, spend_extra_message,
    get_daily_usage, get_extra_messages,
    FREE_DAILY_LIMIT
)

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
        "Когда пользователь присылает текст или изображение — создаёшь чёткий структурированный конспект:\n"
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
        "Если пользователь присылает скриншот с кодом или ошибкой — анализируй изображение. "
        "Код всегда оборачивай в блоки с указанием языка. "
        "Если задача неясна — задай уточняющий вопрос."
    ),
    "solve": (
        "Ты репетитор по математике, физике, логике и другим точным наукам. "
        "Всегда отвечаешь на русском языке. "
        "Когда пользователь присылает задачу (текстом или фото) — решаешь её чётко и понятно:\n"
        "1. Анализ: что дано, что найти\n"
        "2. Пошаговое решение с объяснением каждого шага\n"
        "3. Финальный ответ\n"
        "4. При необходимости — краткое объяснение теории\n"
        "Будь терпелив, как хороший учитель. Если задача неясна — уточни."
    ),
}


def build_limit_keyboard(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить сообщения за ⭐", callback_data="goto_buy")],
        [InlineKeyboardButton(text="👥 Пригласить друга (+10 сообщений)", url=ref_link)],
    ])


async def check_and_charge(message: Message, bot: Bot) -> bool:
    """
    Проверяет лимит. Если можно — списывает (дневной или доп.), возвращает True.
    Если нет — отправляет сообщение с предложением купить/пригласить, возвращает False.
    """
    user_id = message.from_user.id
    allowed, reason = await can_send_message(user_id)

    if allowed:
        if reason == "unlimited":
            pass  # безлимит — ничего не списываем
        elif reason == "extra":
            await spend_extra_message(user_id)
        else:
            await increment_daily_usage(user_id)
        return True

    # Лимит исчерпан
    bot_info = await bot.get_me()
    extra = await get_extra_messages(user_id)
    await message.answer(
        f"⛔ <b>Дневной лимит исчерпан!</b>\n\n"
        f"Ты использовал все <b>{FREE_DAILY_LIMIT} бесплатных сообщений</b> на сегодня.\n"
        f"Лимит обновится в <b>00:00</b> по UTC.\n\n"
        f"Чтобы продолжить прямо сейчас:\n"
        f"💳 Купи дополнительные сообщения за Telegram Stars\n"
        f"👥 Или пригласи друга и получи <b>+10 сообщений бесплатно</b>",
        reply_markup=build_limit_keyboard(bot_info.username, user_id),
        parse_mode="HTML"
    )
    return False


async def send_reply(message: Message, reply: str):
    if len(reply) > 4096:
        parts = [reply[i:i+4096] for i in range(0, len(reply), 4096)]
        for part in parts:
            await message.answer(part)
    else:
        await message.answer(reply)


@router.message()
async def handle_message(message: Message, bot: Bot):
    user_id = message.from_user.id
    await ensure_user(user_id)

    # --- Обработка изображений ---
    if message.photo:
        if not await check_and_charge(message, bot):
            return

        await message.bot.send_chat_action(message.chat.id, "typing")

        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        image_data = base64.b64encode(file_bytes.read()).decode("utf-8")

        user_caption = message.caption.strip() if message.caption else "Опиши это изображение подробно."
        mode = await get_user_mode(user_id)

        vision_messages = [
            {"role": "system", "content": SYSTEM_PROMPTS[mode]},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                    {"type": "text", "text": user_caption}
                ]
            }
        ]

        try:
            response = await client.chat.completions.create(
                model=VISION_MODEL,
                messages=vision_messages,
                max_tokens=2048,
                temperature=0.7
            )
            reply = response.choices[0].message.content
            await add_message(user_id, "user", f"[Изображение] {user_caption}")
            await add_message(user_id, "assistant", reply)
            await send_reply(message, reply)
        except Exception as e:
            await message.answer("⚠️ Не удалось обработать изображение. Попробуй ещё раз.")
            print(f"Ошибка vision для user {user_id}: {e}")
        return

    # --- Обработка текста ---
    if not message.text:
        await message.answer(
            "Я понимаю текст и изображения 🖼\n"
            "Отправь мне текстовое сообщение или фото!"
        )
        return

    if not await check_and_charge(message, bot):
        return

    user_text = message.text.strip()
    mode = await get_user_mode(user_id)
    history = await get_history(user_id)

    await message.bot.send_chat_action(message.chat.id, "typing")
    await add_message(user_id, "user", user_text)

    api_messages = (
        [{"role": "system", "content": SYSTEM_PROMPTS[mode]}]
        + history
        + [{"role": "user", "content": user_text}]
    )

    try:
        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=api_messages,
            max_tokens=2048,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        await add_message(user_id, "assistant", reply)
        await send_reply(message, reply)
    except Exception as e:
        await message.answer("⚠️ Что-то пошло не так. Попробуй ещё раз через несколько секунд.")
        print(f"Ошибка для user {user_id}: {e}")
