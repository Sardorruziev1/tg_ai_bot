import aiosqlite
from datetime import date

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                mode TEXT DEFAULT 'chat',
                referred_by INTEGER DEFAULT NULL,
                extra_messages INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                user_id INTEGER NOT NULL,
                usage_date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, usage_date)
            )
        """)
        # Миграция: добавляем колонки если их нет (для существующих БД)
        for col_sql in [
            "ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL",
            "ALTER TABLE users ADD COLUMN extra_messages INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_unlimited INTEGER DEFAULT 0",
        ]:
            try:
                await db.execute(col_sql)
            except Exception:
                pass
        await db.commit()

async def ensure_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def get_user_mode(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT mode FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return "chat"

async def set_user_mode(user_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, mode) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET mode = excluded.mode
        """, (user_id, mode))
        await db.commit()

async def get_history(user_id: int, limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role, content FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

async def add_message(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )
        await db.execute("""
            DELETE FROM history WHERE user_id = ? AND id NOT IN (
                SELECT id FROM history WHERE user_id = ?
                ORDER BY created_at DESC LIMIT 40
            )
        """, (user_id, user_id))
        await db.commit()

async def clear_history(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
        await db.commit()

# --- Лимиты ---

FREE_DAILY_LIMIT = 10
BONUS_PER_REFERRAL = 10  # сообщений за каждого приглашённого

async def get_daily_usage(user_id: int) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_usage WHERE user_id = ? AND usage_date = ?",
            (user_id, today)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def increment_daily_usage(user_id: int):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO daily_usage (user_id, usage_date, count) VALUES (?, ?, 1)
            ON CONFLICT(user_id, usage_date) DO UPDATE SET count = count + 1
        """, (user_id, today))
        await db.commit()

async def get_extra_messages(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT extra_messages FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def add_extra_messages(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET extra_messages = extra_messages + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def spend_extra_message(user_id: int) -> bool:
    """Списывает 1 доп. сообщение. Возвращает True если успешно."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT extra_messages FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0] > 0:
                await db.execute(
                    "UPDATE users SET extra_messages = extra_messages - 1 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                return True
    return False

async def is_unlimited(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT is_unlimited FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])

async def set_unlimited(user_id: int, value: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, is_unlimited) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET is_unlimited = excluded.is_unlimited",
            (user_id, 1 if value else 0)
        )
        await db.commit()

async def get_vip_list() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE is_unlimited = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def can_send_message(user_id: int) -> tuple[bool, str]:
    """
    Проверяет может ли пользователь отправить сообщение.
    Возвращает (можно, причина_если_нет)
    """
    if await is_unlimited(user_id):
        return True, "unlimited"
    usage = await get_daily_usage(user_id)
    if usage < FREE_DAILY_LIMIT:
        return True, ""
    extra = await get_extra_messages(user_id)
    if extra > 0:
        return True, "extra"
    return False, "limit"

# --- Рефералы ---

async def register_referral(new_user_id: int, referrer_id: int) -> bool:
    """Регистрирует реферала. Возвращает True если реферал засчитан впервые."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT referred_by FROM users WHERE user_id = ?", (new_user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row and row[0] is not None:
            return False  # уже был реферал
        if row is None:
            await db.execute(
                "INSERT INTO users (user_id, referred_by) VALUES (?, ?)",
                (new_user_id, referrer_id)
            )
        else:
            await db.execute(
                "UPDATE users SET referred_by = ? WHERE user_id = ?",
                (referrer_id, new_user_id)
            )
        # Начисляем бонус пригласившему
        await db.execute(
            "UPDATE users SET extra_messages = extra_messages + ? WHERE user_id = ?",
            (BONUS_PER_REFERRAL, referrer_id)
        )
        await db.commit()
        return True

async def get_referral_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# --- Статистика ---

async def get_stats() -> dict:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Всего пользователей
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]

        # Новых пользователей сегодня
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?", (today,)
        ) as cur:
            new_today = (await cur.fetchone())[0]

        # Сообщений отправлено сегодня
        async with db.execute(
            "SELECT COALESCE(SUM(count), 0) FROM daily_usage WHERE usage_date = ?", (today,)
        ) as cur:
            messages_today = (await cur.fetchone())[0]

        # Всего сообщений за всё время
        async with db.execute(
            "SELECT COALESCE(SUM(count), 0) FROM daily_usage"
        ) as cur:
            messages_total = (await cur.fetchone())[0]

        # VIP пользователей
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE is_unlimited = 1"
        ) as cur:
            vip_count = (await cur.fetchone())[0]

        # Активных пользователей сегодня (кто хоть раз написал)
        async with db.execute(
            "SELECT COUNT(*) FROM daily_usage WHERE usage_date = ? AND count > 0", (today,)
        ) as cur:
            active_today = (await cur.fetchone())[0]

        # Всего реферальных регистраций
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL"
        ) as cur:
            total_referrals = (await cur.fetchone())[0]

    return {
        "total_users": total_users,
        "new_today": new_today,
        "active_today": active_today,
        "messages_today": messages_today,
        "messages_total": messages_total,
        "vip_count": vip_count,
        "total_referrals": total_referrals,
    }
