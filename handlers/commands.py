from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from database import (
    get_user_mode, set_user_mode, clear_history,
    get_daily_usage, get_extra_messages, get_referral_count,
    add_extra_messages, register_referral, ensure_user,
    set_unlimited, get_vip_list, is_unlimited, get_stats,
    FREE_DAILY_LIMIT, BONUS_PER_REFERRAL
)
from config import ADMIN_IDS

router = Router()

MODES = {
    "chat":    ("💬", "Умный чат"),
    "summary": ("📝", "Конспект"),
    "essay":   ("📄", "Реферат"),
    "code":    ("💻", "Программист"),
    "solve":   ("🧮", "Решение задач"),
}

# Пакеты сообщений за Telegram Stars
STAR_PACKAGES = [
    {"stars": 25,  "messages": 50,   "label": "50 сообщений — 25 ⭐"},
    {"stars": 50,  "messages": 120,  "label": "120 сообщений — 50 ⭐"},
    {"stars": 100, "messages": 300,  "label": "300 сообщений — 100 ⭐"},
]


def build_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, (emoji, name) in MODES.items():
        label = f"✅ {emoji} {name}" if key == current_mode else f"{emoji} {name}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"mode:{key}")])
    buttons.append([
        InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_buy_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for i, pkg in enumerate(STAR_PACKAGES):
        buttons.append([
            InlineKeyboardButton(text=pkg["label"], callback_data=f"buy:{i}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    await ensure_user(user_id)

    # Обработка реферальной ссылки: /start ref_12345
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
            if referrer_id != user_id:
                credited = await register_referral(user_id, referrer_id)
                if credited:
                    try:
                        await bot.send_message(
                            referrer_id,
                            f"🎉 По твоей ссылке зарегистрировался новый пользователь!\n"
                            f"Тебе начислено +{BONUS_PER_REFERRAL} сообщений 🎁"
                        )
                    except Exception:
                        pass
        except ValueError:
            pass

    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "Я твой личный ИИ-ассистент. Умею:\n"
        "📝 <b>Конспекты</b> — отправь текст, получи структуру\n"
        "📄 <b>Рефераты</b> — напиши тему, получи реферат\n"
        "💻 <b>Код</b> — пишу, объясняю и исправляю\n"
        "🧮 <b>Задачи</b> — решаю пошагово\n"
        "💬 <b>Чат</b> — отвечаю на любые вопросы\n"
        "🖼 <b>Картинки</b> — анализирую изображения\n\n"
        f"🆓 Каждый день тебе доступно <b>{FREE_DAILY_LIMIT} бесплатных сообщений</b>\n\n"
        "👉 /mode — выбрать режим\n"
        "👉 /profile — твой баланс и реферальная ссылка\n"
        "👉 /buy — купить дополнительные сообщения",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        "<b>Команды:</b>\n"
        "/mode — выбрать режим работы\n"
        "/profile — баланс, статистика, реферальная ссылка\n"
        "/buy — купить дополнительные сообщения за ⭐\n"
        "/clear — очистить историю диалога\n"
        "/help — эта справка\n\n"
        "<b>Режимы:</b>\n"
        "💬 <b>Умный чат</b> — любые вопросы\n"
        "📝 <b>Конспект</b> — отправь текст → получи конспект\n"
        "📄 <b>Реферат</b> — напиши тему → получи реферат\n"
        "💻 <b>Программист</b> — помогу с кодом\n"
        "🧮 <b>Задачи</b> — решу с объяснением\n\n"
        "🖼 Также отправляй <b>картинки</b> — бот их анализирует!\n\n"
        f"🆓 <b>{FREE_DAILY_LIMIT} бесплатных сообщений</b> каждый день\n"
        f"👥 Приглашай друзей — получай <b>+{BONUS_PER_REFERRAL} сообщений</b> за каждого!",
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


@router.message(Command("profile"))
async def cmd_profile(message: Message, bot: Bot):
    user_id = message.from_user.id
    await ensure_user(user_id)

    usage_today = await get_daily_usage(user_id)
    extra = await get_extra_messages(user_id)
    ref_count = await get_referral_count(user_id)

    free_left = max(0, FREE_DAILY_LIMIT - usage_today)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    await message.answer(
        f"👤 <b>Твой профиль</b>\n\n"
        f"📊 <b>Сегодня использовано:</b> {usage_today} / {FREE_DAILY_LIMIT}\n"
        f"🆓 <b>Осталось бесплатных:</b> {free_left}\n"
        f"💎 <b>Дополнительных сообщений:</b> {extra}\n\n"
        f"👥 <b>Приглашено друзей:</b> {ref_count}\n"
        f"🎁 За каждого друга — +{BONUS_PER_REFERRAL} сообщений\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"👆 Нажми чтобы скопировать и поделись с друзьями!\n\n"
        f"💳 /buy — купить дополнительные сообщения за ⭐",
        parse_mode="HTML"
    )


@router.message(Command("buy"))
async def cmd_buy(message: Message):
    await message.answer(
        "💳 <b>Купить дополнительные сообщения</b>\n\n"
        "Выбери пакет — оплата через <b>Telegram Stars ⭐</b>:\n"
        "(Stars можно купить прямо в Telegram)",
        reply_markup=build_buy_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buy:"))
async def on_buy_select(callback: CallbackQuery, bot: Bot):
    idx = int(callback.data.split(":")[1])
    pkg = STAR_PACKAGES[idx]
    await callback.answer()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"📦 {pkg['messages']} сообщений",
        description=f"Пополнение баланса на {pkg['messages']} сообщений для ИИ-ассистента",
        payload=f"messages_{pkg['messages']}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{pkg['messages']} сообщений", amount=pkg["stars"])],
    )


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id
    try:
        amount = int(payload.split("_")[1])
        await add_extra_messages(user_id, amount)
        extra = await get_extra_messages(user_id)
        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Начислено: +{amount} сообщений 🎉\n"
            f"Итого на балансе: {extra} сообщений\n\n"
            f"Продолжай пользоваться ботом!",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка обработки платежа: {e}")
        await message.answer("✅ Оплата прошла! Сообщения зачислены.")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    uid = message.from_user.id
    vip = await is_unlimited(uid)
    admin = is_admin(uid)
    status = ""
    if admin:
        status = " 👑 Администратор"
    elif vip:
        status = " 💎 VIP (безлимит)"
    await message.answer(
        f"🆔 Твой Telegram ID: <code>{uid}</code>\n"
        f"(нажми чтобы скопировать){status}",
        parse_mode="HTML"
    )


@router.message(Command("addvip"))
async def cmd_addvip(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет прав для этой команды.")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        await message.answer(
            "Использование: /addvip <user_id>\n\n"
            "Пример: <code>/addvip 123456789</code>\n\n"
            "Узнать ID можно командой /myid",
            parse_mode="HTML"
        )
        return
    target_id = int(args[1])
    await ensure_user(target_id)
    await set_unlimited(target_id, True)
    await message.answer(
        f"✅ Пользователь <code>{target_id}</code> получил безлимитный доступ 💎",
        parse_mode="HTML"
    )


@router.message(Command("removevip"))
async def cmd_removevip(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет прав для этой команды.")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        await message.answer(
            "Использование: /removevip <user_id>\n\n"
            "Пример: <code>/removevip 123456789</code>",
            parse_mode="HTML"
        )
        return
    target_id = int(args[1])
    await set_unlimited(target_id, False)
    await message.answer(
        f"✅ Безлимитный доступ у <code>{target_id}</code> снят.",
        parse_mode="HTML"
    )


@router.message(Command("viplist"))
async def cmd_viplist(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет прав для этой команды.")
        return
    vips = await get_vip_list()
    if not vips:
        await message.answer("💎 Список VIP пуст.")
        return
    lines = [f"• <code>{uid}</code>" for uid in vips]
    await message.answer(
        f"💎 <b>VIP-пользователи ({len(vips)}):</b>\n\n" + "\n".join(lines),
        parse_mode="HTML"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет прав для этой команды.")
        return
    s = await get_stats()
    await message.answer(
        "📊 <b>Статистика бота</b>\n\n"
        "👥 <b>Пользователи:</b>\n"
        f"  • Всего: <b>{s['total_users']}</b>\n"
        f"  • Новых сегодня: <b>{s['new_today']}</b>\n"
        f"  • Активных сегодня: <b>{s['active_today']}</b>\n"
        f"  • VIP (безлимит): <b>{s['vip_count']}</b>\n"
        f"  • Пришли по рефералке: <b>{s['total_referrals']}</b>\n\n"
        "💬 <b>Сообщения:</b>\n"
        f"  • Сегодня: <b>{s['messages_today']}</b>\n"
        f"  • За всё время: <b>{s['messages_total']}</b>\n\n"
        "🛠 <b>Управление:</b>\n"
        "/addvip &lt;id&gt; — выдать безлимит\n"
        "/removevip &lt;id&gt; — забрать безлимит\n"
        "/viplist — список VIP",
        parse_mode="HTML"
    )


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
