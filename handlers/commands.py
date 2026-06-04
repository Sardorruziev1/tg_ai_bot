from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_mode, set_user_mode, clear_history

router = Router()

MODES = {
    "chat":    ("💬", "Умный чат"),
    "summary": ("📝", "Конспект"),
    "essay":   ("📄", "Реферат"),
    "code":    ("💻", "Программист"),
    "solve":   ("🧮", "Решение задач"),
}

def build_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, (emoji, name) in MODES.items():
        label = f"✅ {emoji} {name}" if key == current_mode else f"{emoji} {name}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"mode:{key}")])
    buttons.append([
        InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("start"))
async def cmd_start(message: Message):
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "Я твой личный ИИ-ассистент на базе Claude.\n\n"
        "Что я умею:\n"
        "📝 <b>Конспекты</b> — отправь текст, получи структурированный конспект\n"
        "📄 <b>Рефераты</b> — напиши тему, получи готовый реферат\n"
        "💻 <b>Код</b> — пишу, объясняю и исправляю программы\n"
        "🧮 <b>Задачи</b> — решаю пошагово с объяснением\n"
        "💬 <b>Чат</b> — отвечаю на любые вопросы\n\n"
        "👉 Используй /mode чтобы выбрать режим\n"
        "Или просто напиши что тебе нужно!",
        parse_mode="HTML"
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "<b>Команды:</b>\n"
        "/mode — выбрать режим работы\n"
        "/clear — очистить историю диалога\n"
        "/help — эта справка\n\n"
        "<b>Режимы:</b>\n"
        "💬 <b>Умный чат</b> — любые вопросы и темы\n"
        "📝 <b>Конспект</b> — отправь текст → получи конспект\n"
        "📄 <b>Реферат</b> — напиши тему → получи реферат\n"
        "💻 <b>Программист</b> — помогу с любым кодом\n"
        "🧮 <b>Задачи</b> — решу задачу с объяснением каждого шага\n\n"
        "💡 <i>Бот помнит историю диалога — можно вести беседу!</i>",
        parse_mode="HTML"
    )

@router.message(Command("mode"))
async def cmd_mode(message: Message):
    current = await get_user_mode(message.from_user.id)
    emoji, name = MODES[current]
    await message.answer(
        f"Текущий режим: {emoji} <b>{name}</b>\n\nВыбери режим:",
        reply_markup=build_mode_keyboard(current),
        parse_mode="HTML"
    )

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    await clear_history(message.from_user.id)
    await message.answer("🗑 История диалога очищена! Начинаем с чистого листа.")

@router.callback_query(F.data.startswith("mode:"))
async def on_mode_select(callback: CallbackQuery):
    mode = callback.data.split(":")[1]
    await set_user_mode(callback.from_user.id, mode)
    emoji, name = MODES[mode]
    await callback.message.edit_text(
        f"Текущий режим: {emoji} <b>{name}</b>\n\nВыбери режим:",
        reply_markup=build_mode_keyboard(mode),
        parse_mode="HTML"
    )
    await callback.answer(f"Режим: {emoji} {name}")

@router.callback_query(F.data == "clear")
async def on_clear(callback: CallbackQuery):
    await clear_history(callback.from_user.id)
    await callback.answer("🗑 История очищена!")
