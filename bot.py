import logging
import os
import random
import sqlite3
import time
from io import BytesIO
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from PIL import Image, ImageDraw, ImageOps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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
    custom_level: Optional[int]


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
        if "custom_level" not in col_names:
            conn.execute("ALTER TABLE users ADD COLUMN custom_level INTEGER")


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
            "SELECT telegram_id, full_name, username, cash, level, exp, custom_role, custom_level FROM users WHERE telegram_id = ?",
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
        custom_level=row["custom_level"],
    )


def get_user_by_username(username: str) -> Optional[UserProfile]:
    normalized = username.lstrip("@").strip()
    if not normalized:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT telegram_id, full_name, username, cash, level, exp, custom_role, custom_level
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (normalized,),
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
        custom_level=row["custom_level"],
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


def set_custom_level(telegram_id: int, custom_level: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            return False
        conn.execute("UPDATE users SET custom_level = ? WHERE telegram_id = ?", (custom_level, telegram_id))
    return True


def clear_custom_level(telegram_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if row is None:
            return False
        conn.execute("UPDATE users SET custom_level = NULL WHERE telegram_id = ?", (telegram_id,))
    return True


def resolve_user_reference(user_ref: str) -> Optional[UserProfile]:
    cleaned = user_ref.strip()
    if not cleaned:
        return None
    if cleaned.lstrip("-").isdigit():
        return get_user(int(cleaned))
    return get_user_by_username(cleaned)


def is_owner(user_id: int) -> bool:
    return BOT_OWNER_ID != 0 and user_id == BOT_OWNER_ID


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def grant_exp_if_ready(telegram_id: int) -> Optional[tuple[int, int, int]]:
    now = int(time.time())

    with get_connection() as conn:
        row = conn.execute(
            "SELECT level, exp, custom_level, last_exp_time FROM users WHERE telegram_id = ?",
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
            "UPDATE users SET exp = ?, level = ?, custom_level = NULL, last_exp_time = ? WHERE telegram_id = ?",
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


async def create_round_avatar_bytes(context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> Optional[bytes]:
    photos = await context.bot.get_user_profile_photos(user_id=telegram_id, limit=1)
    if photos.total_count == 0:
        return None

    biggest_photo = photos.photos[0][-1]
    avatar_file = await context.bot.get_file(biggest_photo.file_id)
    avatar_data = await avatar_file.download_as_bytearray()

    with Image.open(BytesIO(avatar_data)).convert("RGB") as img:
        size = min(img.width, img.height)
        left = (img.width - size) // 2
        top = (img.height - size) // 2
        square = img.crop((left, top, left + size, top + size))
        square = ImageOps.fit(square, (256, 256), method=Image.Resampling.LANCZOS)

        mask = Image.new("L", (256, 256), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 255, 255), fill=255)

        rounded = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
        rounded.paste(square, (0, 0), mask)

        output = BytesIO()
        rounded.save(output, format="PNG")
        output.seek(0)
        return output.read()


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
    target_profile: Optional[UserProfile] = None

    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        reply_user = update.message.reply_to_message.from_user
        reply_username = reply_user.username or "-"
        upsert_user(reply_user.id, reply_user.full_name, reply_username)
        target_profile = get_user(reply_user.id)
    elif context.args:
        target_profile = resolve_user_reference(context.args[0])
    else:
        target_profile = get_user(user.id)

    if target_profile is None:
        await update.message.reply_text("Data user tidak ditemukan.")
        return

    shown_level = target_profile.custom_level if target_profile.custom_level else target_profile.level
    shown_needed = exp_needed(shown_level)
    role = target_profile.custom_role if target_profile.custom_role else get_role(shown_level)
    now_wib = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M:%S WIB")
    date_part, time_part = now_wib.split(" ", 1)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Help", callback_data="menu_help"),
                InlineKeyboardButton("Transfer", callback_data="menu_transfer"),
            ],
            [
                InlineKeyboardButton("Language", callback_data="menu_language"),
                InlineKeyboardButton("Ego Federation", url="https://t.me/EgoFederation"),
            ],
        ]
    )
    response = (
        f"Nama : {target_profile.full_name}\n"
        f"Username : @{target_profile.username if target_profile.username != '-' else '-'}\n"
        f"ID : {target_profile.telegram_id}\n"
        f"Cash : {format_number(target_profile.cash)}\n"
        f"Level : {shown_level} ({target_profile.exp}/{shown_needed})\n"
        f"Role : {role}\n"
        f"Date : <i>{date_part}</i>\n"
        f"Time : <i>{time_part}</i>"
    )
    avatar_bytes = await create_round_avatar_bytes(context, target_profile.telegram_id)
    if avatar_bytes:
        await update.message.reply_photo(
            photo=avatar_bytes,
            caption=response,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def addcoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not is_owner(update.effective_user.id):
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

    await update.message.reply_text(f"Berhasil menambah {format_number(amount)} cash ke user ID {target_id}.")


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
    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
    transfer_date = now_wib.strftime("%Y-%m-%d")
    transfer_time = now_wib.strftime("%H:%M:%S WIB")
    await update.message.reply_text(
        (
            f"<i>Transfer berhasil: {format_number(amount)} cash ke ID {target_id}.</i>\n"
            f"<i>Tanggal: {transfer_date}</i>\n"
            f"<i>Jam: {transfer_time}</i>"
        ),
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    text = (
        "Daftar command:\n"
        "/start - daftar/update akun\n"
        "/profile [id/@username] - lihat profil sendiri/target\n"
        "Balas pesan orang lalu /profile untuk lihat profil dia\n"
        "/transfer <id_tujuan> <jumlah>\n"
        "/tf <id_tujuan> <jumlah>\n"
        "/help - bantuan command"
    )
    await update.message.reply_text(text)


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is None:
        return

    query = update.callback_query
    await query.answer()

    if query.data == "menu_help":
        await query.message.reply_text(
            "Gunakan /help untuk melihat daftar command pengguna."
        )
    elif query.data == "menu_transfer":
        await query.message.reply_text(
            "Gunakan /transfer <id_tujuan> <jumlah> atau /tf <id_tujuan> <jumlah>."
        )
    elif query.data == "menu_language":
        await query.message.reply_text(
            "Language tersedia: Indonesia 🇮🇩 (default)."
        )


async def setrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Format: /setrole <id_user> <role_custom>")
        return

    target_profile = resolve_user_reference(context.args[0])
    if target_profile is None:
        await update.message.reply_text("User tidak ditemukan. Gunakan ID atau @username yang sudah terdaftar.")
        return

    custom_role = " ".join(context.args[1:]).strip()
    if not custom_role:
        await update.message.reply_text("Role custom tidak boleh kosong.")
        return

    set_custom_role(target_profile.telegram_id, custom_role)

    await update.message.reply_text(
        f"Role user {target_profile.full_name} (ID {target_profile.telegram_id}) berhasil diubah ke: {custom_role}"
    )


async def clearrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Format: /clearrole <id_user>")
        return

    target_profile = resolve_user_reference(context.args[0])
    if target_profile is None:
        await update.message.reply_text("User tidak ditemukan. Gunakan ID atau @username yang sudah terdaftar.")
        return

    clear_custom_role(target_profile.telegram_id)

    await update.message.reply_text(
        f"Role custom user {target_profile.full_name} (ID {target_profile.telegram_id}) berhasil dihapus."
    )


async def setlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Format: /setlevel <id_user/@username> <level_custom>")
        return

    target_profile = resolve_user_reference(context.args[0])
    if target_profile is None:
        await update.message.reply_text("User tidak ditemukan. Gunakan ID atau @username yang sudah terdaftar.")
        return

    try:
        custom_level = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Level custom harus berupa angka.")
        return

    if custom_level < 1:
        await update.message.reply_text("Level custom minimal 1.")
        return

    set_custom_level(target_profile.telegram_id, custom_level)
    await update.message.reply_text(
        f"Level custom user {target_profile.full_name} (ID {target_profile.telegram_id}) diubah ke {custom_level}."
    )


async def defaultlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk owner bot.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Format: /defaultlevel <id_user/@username>")
        return

    target_profile = resolve_user_reference(context.args[0])
    if target_profile is None:
        await update.message.reply_text("User tidak ditemukan. Gunakan ID atau @username yang sudah terdaftar.")
        return

    clear_custom_level(target_profile.telegram_id)
    await update.message.reply_text(
        f"Level user {target_profile.full_name} (ID {target_profile.telegram_id}) dikembalikan ke level asli."
    )


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
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("addcoin", addcoin_command))
    application.add_handler(CommandHandler("transfer", transfer_command))
    application.add_handler(CommandHandler("tf", transfer_command))
    application.add_handler(CommandHandler("setrole", setrole_command))
    application.add_handler(CommandHandler("clearrole", clearrole_command))
    application.add_handler(CommandHandler("setlevel", setlevel_command))
    application.add_handler(CommandHandler("defaultlevel", defaultlevel_command))
    application.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^menu_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group_message_handler))

    logger.info("Bot berjalan...")
    application.run_polling()


if __name__ == "__main__":
    main()
