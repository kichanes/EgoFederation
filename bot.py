import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

DB_PATH = os.getenv("DB_PATH", "bot_data.sqlite3")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))
INITIAL_CASH = 1000
EXP_MIN = 5
EXP_MAX = 15
EXP_COOLDOWN_SECONDS = 300

ROLE_RANGES = [
    (1, 5, "💩 Manusia Antah Berantah"),
    (6, 10, "👩🏿‍🦲 Super Gembel"),
    (11, 15, "👩🏾‍🦲 Gembel"),
    (16, 20, "👩🏽‍🦲 Gembel Elite"),
    (21, 25, "👩🏼‍🦲 Jelata"),
    (26, 30, "🪔 Pengemis Pemula"),
    (31, 40, "🪔 Pengemis Biasa"),
    (41, 45, "🪔 Pengemis Senior"),
    (46, 50, "🪔 Pengemis Profesional"),
    (51, 55, "👨🏾‍🦲 Pemulung Pemula"),
    (56, 60, "👨🏽‍🦲 Pemulung Biasa"),
    (61, 65, "👨🏼‍🦲 Pemulung Senior"),
    (66, 70, "👨🏻‍🦲 Pemulung Profesional"),
    (71, 75, "🧌 Miskin"),
    (76, 80, "👫 Rakyat Biasa"),
    (81, 85, "🎎 Rakyat Menengah Kebawah"),
    (86, 90, "👷🏻 Rakyat Menengah"),
    (91, 95, "🤵🏻‍♀ Orang Kaya"),
    (96, 100, "👩🏻‍🚀 Kaum Elite"),
    (101, 110, "Bangsawan"),
    (111, 120, "🥉 Konglomerat III"),
    (121, 130, "🥈 Konglomerat II"),
    (131, 140, "🥇 Konglomerat I"),
    (141, 149, "🎖 Elite Nasional"),
    (150, 9999, "🐛 Naga"),
]


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    telegram_id: int
    full_name: str
    username: str
    cash: int
    level: int
    exp: int
    custom_role: Optional[str]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL,
                cash INTEGER NOT NULL DEFAULT 1000,
                level INTEGER NOT NULL DEFAULT 1,
                exp INTEGER NOT NULL DEFAULT 0,
                last_exp_time INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        columns = conn.execute("PRAGMA table_info(users)").fetchall()
        col_names = {col["name"] for col in columns}
        if "custom_role" not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN custom_role TEXT")


def exp_needed(level: int) -> int:
    return level * 100


def get_role(level: int) -> str:
    for start, end, role in ROLE_RANGES:
        if start <= level <= end:
            return role
    return "Tanpa Role"


def upsert_user(telegram_id: int, full_name: str, username: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, full_name, username, cash, level, exp, last_exp_time)
            VALUES (?, ?, ?, ?, 1, 0, 0)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name=excluded.full_name,
                username=excluded.username
            """,
            (telegram_id, full_name, username, INITIAL_CASH),
        )


def get_user(telegram_id: int) -> Optional[UserProfile]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT telegram_id, full_name, username, cash, level, exp, custom_role FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()

    if row is None:
        return None

    return UserProfile(
        telegram_id=row["telegram_id"],
        full_name=row["full_name"],
        username=row["username"],
        cash=row["cash"],
        level=row["level"],
        exp=row["exp"],
        custom_role=row["custom_role"],
    )


def set_custom_role(telegram_id: int, custom_role: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            return False
        conn.execute("UPDATE users SET custom_role = ? WHERE telegram_id = ?", (custom_role, telegram_id))
    return True


def clear_custom_role(telegram_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            return False
        conn.execute("UPDATE users SET custom_role = NULL WHERE telegram_id = ?", (telegram_id,))
    return True


def grant_exp_if_ready(telegram_id: int) -> Optional[tuple[int, int, int]]:
    now = int(time.time())

    with get_connection() as conn:
        row = conn.execute(
            "SELECT level, exp, last_exp_time FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()

        if row is None:
            return None

        if now - row["last_exp_time"] < EXP_COOLDOWN_SECONDS:
            return None

        gained_exp = random.randint(EXP_MIN, EXP_MAX)
        level = row["level"]
        exp = row["exp"] + gained_exp

        while exp >= exp_needed(level):
            exp -= exp_needed(level)
            level += 1

        conn.execute(
            "UPDATE users SET exp = ?, level = ?, last_exp_time = ? WHERE telegram_id = ?",
            (exp, level, now, telegram_id),
        )

    return gained_exp, level, exp


def update_cash(telegram_id: int, delta: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT cash FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            return False

        new_cash = row["cash"] + delta
        if new_cash < 0:
            return False

        conn.execute("UPDATE users SET cash = ? WHERE telegram_id = ?", (new_cash, telegram_id))
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    user = update.effective_user
    username = user.username or "-"
    upsert_user(user.id, user.full_name, username)

    await update.message.reply_text(
        "Halo! Data kamu sudah didaftarkan. Gunakan /profile untuk lihat status kamu."
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    user = update.effective_user
    username = user.username or "-"
    upsert_user(user.id, user.full_name, username)
    profile = get_user(user.id)

    if profile is None:
        await update.message.reply_text("Data user tidak ditemukan.")
        return

    needed = exp_needed(profile.level)
    role = profile.custom_role if profile.custom_role else get_role(profile.level)
    response = (
        f"Nama : {profile.full_name}\n"
        f"Username : @{profile.username if profile.username != '-' else '-'}\n"
        f"ID : {profile.telegram_id}\n"
        f"Cash : {profile.cash}\n"
        f"Level : {profile.level} ({profile.exp}/{needed})\n"
        f"Role : {role}"
    )
    await update.message.reply_text(response)


async def addcoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) != 2:
        await update.message.reply_text('Format: /addcoin <id_user> <jumlah>')
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("ID dan jumlah harus berupa angka.")
        return

    if amount <= 0:
        await update.message.reply_text("Jumlah coin harus lebih dari 0.")
        return

    if not update_cash(target_id, amount):
        await update.message.reply_text("Gagal menambah cash. Pastikan user sudah terdaftar lewat /start.")
        return

    await update.message.reply_text(f"Berhasil menambah {amount} cash ke user ID {target_id}.")


async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    sender = update.effective_user
    username = sender.username or "-"
    upsert_user(sender.id, sender.full_name, username)

    if len(context.args) != 2:
        await update.message.reply_text("Format: /transfer <id_tujuan> <jumlah>")
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("ID tujuan dan jumlah harus angka.")
        return

    if amount <= 0:
        await update.message.reply_text("Jumlah transfer harus lebih dari 0.")
        return

    if target_id == sender.id:
        await update.message.reply_text("Tidak bisa transfer ke diri sendiri.")
        return

    target = get_user(target_id)
    if target is None:
        await update.message.reply_text("User tujuan belum terdaftar. Minta user tujuan /start dulu.")
        return

    if not update_cash(sender.id, -amount):
        await update.message.reply_text("Cash kamu tidak cukup.")
        return

    update_cash(target_id, amount)
    await update.message.reply_text(
        f"Transfer berhasil: {amount} cash ke ID {target_id}."
    )


async def setrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Format: /setrole <id_user> <role_custom>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID user harus berupa angka.")
        return

    custom_role = " ".join(context.args[1:]).strip()
    if not custom_role:
        await update.message.reply_text("Role custom tidak boleh kosong.")
        return

    if not set_custom_role(target_id, custom_role):
        await update.message.reply_text("User belum terdaftar. Minta user /start dulu.")
        return

    await update.message.reply_text(f"Role user ID {target_id} berhasil diubah ke: {custom_role}")


async def clearrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Format: /clearrole <id_user>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID user harus berupa angka.")
        return

    if not clear_custom_role(target_id):
        await update.message.reply_text("User belum terdaftar. Minta user /start dulu.")
        return

    await update.message.reply_text(f"Role custom user ID {target_id} berhasil dihapus.")


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return

    chat = update.effective_chat
    if chat is None:
        return

    if chat.type not in {"group", "supergroup"}:
        return

    user = update.effective_user
    username = user.username or "-"
    upsert_user(user.id, user.full_name, username)
    grant_exp_if_ready(user.id)


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN belum diset di environment.")

    init_db()

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("addcoin", addcoin_command))
    application.add_handler(CommandHandler("transfer", transfer_command))
    application.add_handler(CommandHandler("setrole", setrole_command))
    application.add_handler(CommandHandler("clearrole", clearrole_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group_message_handler))

    logger.info("Bot berjalan...")
    application.run_polling()


if __name__ == "__main__":
    main()
