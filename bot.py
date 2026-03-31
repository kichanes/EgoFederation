import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import psycopg2
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

DB_PATH = os.getenv("DB_PATH", "/data/bot_data.sqlite3")
DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_POSTGRES = bool(DATABASE_URL)
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))
INITIAL_CASH = 1000
EXP_MIN = 5
EXP_MAX = 15
EXP_COOLDOWN_SECONDS = 300
MAX_HP = 200

ROLE_RANGES = [
    (1, 5, "💩 Manusia Antah Berantah"), (6, 10, "👩🏿‍🦲 Super Gembel"), (11, 15, "👩🏾‍🦲 Gembel"),
    (16, 20, "👩🏽‍🦲 Gembel Elite"), (21, 25, "👩🏼‍🦲 Jelata"), (26, 30, "🪔 Pengemis Pemula"),
    (31, 40, "🪔 Pengemis Biasa"), (41, 45, "🪔 Pengemis Senior"), (46, 50, "🪔 Pengemis Profesional"),
    (51, 55, "👨🏾‍🦲 Pemulung Pemula"), (56, 60, "👨🏽‍🦲 Pemulung Biasa"), (61, 65, "👨🏼‍🦲 Pemulung Senior"),
    (66, 70, "👨🏻‍🦲 Pemulung Profesional"), (71, 75, "🧌 Miskin"), (76, 80, "👫 Rakyat Biasa"),
    (81, 85, "🎎 Rakyat Menengah Kebawah"), (86, 90, "👷🏻 Rakyat Menengah"), (91, 95, "🤵🏻‍♀ Orang Kaya"),
    (96, 100, "👩🏻‍🚀 Kaum Elite"), (101, 110, "Bangsawan"), (111, 120, "🥉 Konglomerat III"),
    (121, 130, "🥈 Konglomerat II"), (131, 140, "🥇 Konglomerat I"), (141, 149, "🎖 Elite Nasional"),
    (150, 9999, "🐛 Naga"),
]

ITEMS = {
    "banana": {"name": "🍌 Kulit Pisang", "price": 200, "desc": "Damage 5-10"},
    "sandal": {"name": "🩴 Sandal Emak", "price": 2500, "desc": "Damage 7-12"},
    "luck_potion": {"name": "🧪 Lucky Potion", "price": 5000, "desc": "Buff luck +5% (pakai /lp)"},
    "shield_3": {"name": "🛡️ Perisai Kelas III", "price": 1000, "desc": "Stack max 3, auto saat kena /dor Kelas III"},
    "pistol_3": {"name": "🔫 Pistol Kelas III", "price": 5000, "desc": "Untuk /dor"},
    "potion_red": {"name": "🩸 Potion Pot HP +10%", "price": 100, "desc": "Tambah HP 10% (pakai /pot)"},
    "armor_item": {"name": "🦺 Armor (Armor+100)", "price": 5000, "desc": "Tambah armor +100 (pakai /armor)"},
}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
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
    register_date: str
    hp: int
    armor: int
    inventory_capacity: int
    luck_buff_until: int


def get_connection() -> sqlite3.Connection:
    if IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _q(query: str) -> str:
    return query.replace("?", "%s") if IS_POSTGRES else query


def db_execute(conn, query: str, params=(), fetch: str = ""):
    cur = conn.cursor()
    cur.execute(_q(query), params)
    if fetch == "one":
        return cur.fetchone()
    if fetch == "all":
        return cur.fetchall()
    return cur.rowcount


def init_db() -> None:
    with get_connection() as conn:
        db_execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL,
                cash INTEGER NOT NULL DEFAULT 1000,
                level INTEGER NOT NULL DEFAULT 1,
                exp INTEGER NOT NULL DEFAULT 0,
                last_exp_time INTEGER NOT NULL DEFAULT 0,
                custom_role TEXT,
                custom_level INTEGER,
                register_date TEXT,
                hp INTEGER NOT NULL DEFAULT 200,
                armor INTEGER NOT NULL DEFAULT 0,
                inventory_capacity INTEGER NOT NULL DEFAULT 5,
                last_daily INTEGER NOT NULL DEFAULT 0,
                last_weekly INTEGER NOT NULL DEFAULT 0,
                luck_buff_until INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        db_execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS user_items (
                telegram_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                qty INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (telegram_id, item_key)
            )
            """,
        )
        if IS_POSTGRES:
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_role TEXT")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_level INTEGER")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS register_date TEXT")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS hp INTEGER NOT NULL DEFAULT 200")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS armor INTEGER NOT NULL DEFAULT 0")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS inventory_capacity INTEGER NOT NULL DEFAULT 5")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily BIGINT NOT NULL DEFAULT 0")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_weekly BIGINT NOT NULL DEFAULT 0")
            db_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS luck_buff_until BIGINT NOT NULL DEFAULT 0")
        else:
            columns = {c["name"] for c in db_execute(conn, "PRAGMA table_info(users)", fetch="all")}
            migrations = {
                "custom_role": "TEXT",
                "custom_level": "INTEGER",
                "register_date": "TEXT",
                "hp": "INTEGER NOT NULL DEFAULT 200",
                "armor": "INTEGER NOT NULL DEFAULT 0",
                "inventory_capacity": "INTEGER NOT NULL DEFAULT 5",
                "last_daily": "INTEGER NOT NULL DEFAULT 0",
                "last_weekly": "INTEGER NOT NULL DEFAULT 0",
                "luck_buff_until": "INTEGER NOT NULL DEFAULT 0",
            }
            for col, sql_type in migrations.items():
                if col not in columns:
                    db_execute(conn, f"ALTER TABLE users ADD COLUMN {col} {sql_type}")


def now_wib() -> datetime:
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def format_number(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def exp_needed(level: int) -> int:
    return level * 100


def get_role(level: int) -> str:
    for s, e, r in ROLE_RANGES:
        if s <= level <= e:
            return r
    return "Tanpa Role"


def is_owner(uid: int) -> bool:
    return BOT_OWNER_ID != 0 and uid == BOT_OWNER_ID


def upsert_user(telegram_id: int, full_name: str, username: str) -> None:
    with get_connection() as conn:
        db_execute(
            conn,
            """
            INSERT INTO users (telegram_id, full_name, username, cash, level, exp, last_exp_time, register_date)
            VALUES (?, ?, ?, ?, 1, 0, 0, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name=excluded.full_name,
                username=excluded.username
            """,
            (telegram_id, full_name, username, INITIAL_CASH, now_wib().strftime("%Y-%m-%d")),
        )


def row_to_user(r: sqlite3.Row) -> UserProfile:
    return UserProfile(
        telegram_id=r["telegram_id"], full_name=r["full_name"], username=r["username"], cash=r["cash"],
        level=r["level"], exp=r["exp"], custom_role=r["custom_role"], custom_level=r["custom_level"],
        register_date=r["register_date"] or "-", hp=r["hp"], armor=r["armor"], inventory_capacity=r["inventory_capacity"],
        luck_buff_until=r["luck_buff_until"],
    )


def get_user(telegram_id: int) -> Optional[UserProfile]:
    with get_connection() as conn:
        row = db_execute(conn, "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,), fetch="one")
    return row_to_user(row) if row else None


def get_user_by_username(username: str) -> Optional[UserProfile]:
    un = username.lstrip("@").strip()
    with get_connection() as conn:
        row = db_execute(conn, "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (un,), fetch="one")
    return row_to_user(row) if row else None


def resolve_user_reference(ref: str) -> Optional[UserProfile]:
    if ref.lstrip("-").isdigit():
        return get_user(int(ref))
    return get_user_by_username(ref)


def set_custom_role(uid: int, role: str) -> bool:
    with get_connection() as conn:
        res = db_execute(conn, "UPDATE users SET custom_role=? WHERE telegram_id=?", (role, uid))
    return res > 0


def clear_custom_role(uid: int) -> bool:
    with get_connection() as conn:
        res = db_execute(conn, "UPDATE users SET custom_role=NULL WHERE telegram_id=?", (uid,))
    return res > 0


def set_custom_level(uid: int, level: int) -> bool:
    with get_connection() as conn:
        res = db_execute(conn, "UPDATE users SET custom_level=? WHERE telegram_id=?", (level, uid))
    return res > 0


def clear_custom_level(uid: int) -> bool:
    with get_connection() as conn:
        res = db_execute(conn, "UPDATE users SET custom_level=NULL WHERE telegram_id=?", (uid,))
    return res > 0


def update_cash(uid: int, delta: int) -> bool:
    with get_connection() as conn:
        row = db_execute(conn, "SELECT cash FROM users WHERE telegram_id=?", (uid,), fetch="one")
        if not row:
            return False
        new_cash = row["cash"] + delta
        if new_cash < 0:
            return False
        db_execute(conn, "UPDATE users SET cash=? WHERE telegram_id=?", (new_cash, uid))
    return True


def update_hp_armor(uid: int, hp_delta: int = 0, armor_delta: int = 0) -> None:
    with get_connection() as conn:
        row = db_execute(conn, "SELECT hp, armor FROM users WHERE telegram_id=?", (uid,), fetch="one")
        if not row:
            return
        hp = max(0, min(MAX_HP, row["hp"] + hp_delta))
        armor = max(0, row["armor"] + armor_delta)
        db_execute(conn, "UPDATE users SET hp=?, armor=? WHERE telegram_id=?", (hp, armor, uid))


def grant_exp_if_ready(uid: int) -> None:
    now = int(time.time())
    with get_connection() as conn:
        row = db_execute(conn, "SELECT level, exp, last_exp_time FROM users WHERE telegram_id=?", (uid,), fetch="one")
        if not row or now - row["last_exp_time"] < EXP_COOLDOWN_SECONDS:
            return
        gained = random.randint(EXP_MIN, EXP_MAX)
        lvl = row["level"]
        exp = row["exp"] + gained
        while exp >= exp_needed(lvl):
            exp -= exp_needed(lvl)
            lvl += 1
        db_execute(
            conn,
            "UPDATE users SET exp=?, level=?, custom_level=NULL, last_exp_time=? WHERE telegram_id=?",
            (exp, lvl, now, uid),
        )


def get_inventory(uid: int) -> dict[str, int]:
    with get_connection() as conn:
        rows = db_execute(conn, "SELECT item_key, qty FROM user_items WHERE telegram_id=? AND qty>0", (uid,), fetch="all")
    return {r["item_key"]: r["qty"] for r in rows}


def used_inventory_slots(uid: int) -> int:
    with get_connection() as conn:
        row = db_execute(conn, "SELECT COUNT(*) AS c FROM user_items WHERE telegram_id=? AND qty>0", (uid,), fetch="one")
    return row["c"]


def add_item(uid: int, key: str, qty: int = 1, stack_max: Optional[int] = None) -> tuple[bool, str]:
    user = get_user(uid)
    if not user:
        return False, "User tidak ditemukan."
    inv = get_inventory(uid)
    curr = inv.get(key, 0)
    if curr == 0 and used_inventory_slots(uid) >= user.inventory_capacity:
        return False, f"Inventory penuh ({user.inventory_capacity} slot)."
    if stack_max is not None and curr + qty > stack_max:
        return False, f"Item ini maksimal stack {stack_max}."
    with get_connection() as conn:
        db_execute(
            conn,
            """
            INSERT INTO user_items (telegram_id, item_key, qty)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, item_key) DO UPDATE SET qty = qty + excluded.qty
            """,
            (uid, key, qty),
        )
    return True, "OK"


def remove_item(uid: int, key: str, qty: int = 1) -> bool:
    with get_connection() as conn:
        row = db_execute(
            conn,
            "SELECT qty FROM user_items WHERE telegram_id=? AND item_key=?", (uid, key)
            , fetch="one")
        if not row or row["qty"] < qty:
            return False
        new_qty = row["qty"] - qty
        if new_qty == 0:
            db_execute(conn, "DELETE FROM user_items WHERE telegram_id=? AND item_key=?", (uid, key))
        else:
            db_execute(conn, "UPDATE user_items SET qty=? WHERE telegram_id=? AND item_key=?", (new_qty, uid, key))
    return True


def luck_active(user: UserProfile) -> bool:
    return user.luck_buff_until > int(time.time())


def choose_pistol(inv: dict[str, int]) -> Optional[tuple[str, int]]:
    # prioritas dari kelas III -> II -> I
    for key, cls in [("pistol_3", 3), ("pistol_2", 2), ("pistol_1", 1)]:
        if inv.get(key, 0) > 0:
            return key, cls
    return None


def available_shield(inv: dict[str, int]) -> Optional[tuple[str, int]]:
    for key, cls in [("shield_1", 1), ("shield_2", 2), ("shield_3", 3)]:
        if inv.get(key, 0) > 0:
            return key, cls
    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    upsert_user(user.id, user.full_name, user.username or "-")
    await update.message.reply_text("Halo! Kamu sudah terdaftar. Gunakan /p atau /profile untuk melihat profil.")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    upsert_user(user.id, user.full_name, user.username or "-")

    target: Optional[UserProfile]
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        ru = update.message.reply_to_message.from_user
        upsert_user(ru.id, ru.full_name, ru.username or "-")
        target = get_user(ru.id)
    elif context.args:
        target = resolve_user_reference(context.args[0])
    else:
        target = get_user(user.id)

    if not target:
        await update.message.reply_text("Data user tidak ditemukan.")
        return

    level_show = target.level
    role = target.custom_role or get_role(level_show)
    t = now_wib()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("❓ Help", callback_data="menu_help"),
        InlineKeyboardButton("📢 Ego Federation", url="https://t.me/EgoFederation"),
    ]])
    text = (
        f"Nama : {target.full_name}\n"
        f"Username : @{target.username if target.username != '-' else '-'}\n"
        f"ID : {target.telegram_id}\n"
        f"Cash : {format_number(target.cash)}\n"
        f"Level : {level_show} ({target.exp}/{exp_needed(level_show)})\n"
        f"Role : {role}\n"
        f"Register Date : <i>{target.register_date}</i>\n"
        f"Time : <i>{t.strftime('%H:%M:%S WIB')}</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Daftar command:\n"
        "/start, /p (/profile), /status, /inv, /shop, /buy <kode>, /pot, /armor, /lp, /dor, /transfer (/tf), /help\n"
        "/daily, /weekly"
    )


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    q = update.callback_query
    await q.answer()
    if q.data == "menu_help":
        await q.message.reply_text(
            "Command pengguna:\n"
            "/start\n/p atau /profile\n/status\n/inv\n/shop\n/buy <kode>\n/pot\n/armor\n/lp\n/dor\n/transfer atau /tf\n/daily\n/weekly\n/help"
        )


async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    u = get_user(update.effective_user.id)
    if not u:
        return
    inv = get_inventory(u.telegram_id)
    lines = [f"Inventory ({used_inventory_slots(u.telegram_id)}/{u.inventory_capacity}):"]
    if not inv:
        lines.append("(kosong)")
    for k, q in inv.items():
        lines.append(f"- {ITEMS.get(k, {'name': k})['name']} x{q}")
    token_qty = inv.get("token", 0)
    if token_qty:
        lines.append(f"- 🪙 Token x{token_qty}")
    await update.message.reply_text("\n".join(lines))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    u = get_user(update.effective_user.id)
    if not u:
        return
    now = int(time.time())
    buffs: list[str] = []
    debuffs: list[str] = []

    if u.luck_buff_until > now:
        remain = u.luck_buff_until - now
        buffs.append(f"🧪 Lucky +5% ({remain // 60} menit)")

    buff_text = ", ".join(buffs) if buffs else "Tidak ada"
    debuff_text = ", ".join(debuffs) if debuffs else "Tidak ada"
    alert = "\n⚠️ ALERT! HP di bawah 20%, beli Potion di /shop lalu pakai /pot" if u.hp < int(MAX_HP * 0.2) else ""
    await update.message.reply_text(
        f"HP : {u.hp}/{MAX_HP}\n"
        f"Armor : {u.armor}\n"
        f"Buff : {buff_text}\n"
        f"Debuff : {debuff_text}"
        f"{alert}"
    )


def can_afford(uid: int, price: int) -> bool:
    u = get_user(uid)
    return bool(u and u.cash >= price)


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    u = get_user(update.effective_user.id)
    if not u:
        return
    kb = [[InlineKeyboardButton(f"Beli {v['name']}", callback_data=f"buy:{k}")] for k, v in ITEMS.items()]
    kb.append([InlineKeyboardButton("🕵️ Secret Shop", callback_data="secret_shop")])
    text_lines = [
        "🛒 Shop:",
        f"- 🍌 Kulit Pisang | Harga {format_number(200)}",
        f"- 🩴 Sandal Emak | Harga {format_number(2500)}",
        f"- 🧪 Lucky Potion | Harga {format_number(5000)}",
        f"- 🛡️ Perisai Kelas III | Harga {format_number(1000)}",
        f"- 🔫 Pistol Kelas III | Harga {format_number(5000)}",
        f"- 🩸 Potion Pot HP +10% | Harga {format_number(100)}",
        f"- 🦺 Armor (Armor+100) | Harga {format_number(5000)}",
        "",
        "Beli item via bubble atau command /buy <kode_item>.",
    ]
    await update.message.reply_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(kb))


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Format: /buy <kode_item>")
        return
    await process_buy(update.effective_user.id, context.args[0], update.message.reply_text)


async def process_buy(uid: int, key: str, reply_fn) -> None:
    if key not in ITEMS:
        await reply_fn("Item tidak ditemukan.")
        return
    item = ITEMS[key]
    if not can_afford(uid, item["price"]):
        await reply_fn("Cash tidak cukup.")
        return
    stack_max = 3 if key == "shield_3" else None
    ok, msg = add_item(uid, key, 1, stack_max=stack_max)
    if not ok:
        await reply_fn(msg)
        return
    update_cash(uid, -item["price"])
    await reply_fn(f"Berhasil beli {item['name']} seharga {format_number(item['price'])}.")


async def shop_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user:
        return
    q = update.callback_query
    await q.answer()
    if q.data and q.data.startswith("buy:"):
        await process_buy(update.effective_user.id, q.data.split(":", 1)[1], q.message.reply_text)
    elif q.data == "secret_shop":
        u = get_user(update.effective_user.id)
        if not u:
            return
        lvl = u.level
        if lvl < 5:
            await q.message.reply_text("Secret Shop terbuka di level 5.")
        else:
            await q.message.reply_text("🕵️ Secret Shop terbuka! (saat ini belum ada barang)")


async def potion_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    if not remove_item(uid, "potion_red", 1):
        await update.message.reply_text("Potion Merah tidak ada di inventory.")
        return
    heal = int(MAX_HP * 0.1)
    update_hp_armor(uid, hp_delta=heal)
    await update.message.reply_text(f"Kamu menggunakan Potion Merah. HP +{heal}.")


async def armor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    if not remove_item(uid, "armor_item", 1):
        await update.message.reply_text("Armor item tidak ada di inventory.")
        return
    update_hp_armor(uid, armor_delta=100)
    await update.message.reply_text("Armor digunakan. Armor +100.")


async def lp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    if not remove_item(uid, "luck_potion", 1):
        await update.message.reply_text("Lucky Potion tidak ada di inventory.")
        return
    until = int(time.time()) + 60 * 60
    with get_connection() as conn:
        db_execute(conn, "UPDATE users SET luck_buff_until=? WHERE telegram_id=?", (until, uid))
    await update.message.reply_text("Lucky Potion aktif 60 menit. Buff luck +5%.")


def resolve_target_from_update(update: Update, args: list[str]) -> Optional[UserProfile]:
    if update.message and update.message.reply_to_message and update.message.reply_to_message.from_user:
        r = update.message.reply_to_message.from_user
        upsert_user(r.id, r.full_name, r.username or "-")
        return get_user(r.id)
    if args:
        return resolve_user_reference(args[0])
    return None


async def dor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    attacker = get_user(update.effective_user.id)
    if not attacker:
        return
    target = resolve_target_from_update(update, context.args)
    if not target or target.telegram_id == attacker.telegram_id:
        await update.message.reply_text("Target tidak valid. Gunakan reply atau /dor <id/@username>.")
        return

    inv_att = get_inventory(attacker.telegram_id)
    pistol = choose_pistol(inv_att)
    if not pistol:
        await update.message.reply_text("Kamu tidak punya pistol di inventory.")
        return

    pistol_key, pistol_class = pistol
    remove_item(attacker.telegram_id, pistol_key, 1)

    base_steal = random.randint(1, 50)
    if luck_active(attacker):
        base_steal = int(base_steal * 1.05)
    base_damage = {1: 25, 2: 20, 3: 15}[pistol_class]

    inv_target = get_inventory(target.telegram_id)
    shield = available_shield(inv_target)
    note = ""
    steal = base_steal
    damage = base_damage

    if shield:
        shield_key, shield_class = shield
        class_diff = shield_class - pistol_class
        if class_diff == 0:
            remove_item(target.telegram_id, shield_key, 1)
            note = "🛡️ Target memiliki perisai kelas sama. Serangan ditahan."
            if random.random() <= 0.025:
                steal = max(1, int(steal * 0.8))
                damage = 0
                note += " Chance 2.5% aktif, kamu tetap mencuri kecil."
            else:
                steal = 0
                damage = 0
        elif class_diff == 1:
            remove_item(target.telegram_id, shield_key, 1)
            damage = int(damage * 0.85)
            steal = int(steal * 0.85)
            note = "🛡️ Perisai target hancur, damage/cash tereduksi 15%."
        elif class_diff <= -1:
            # pistol lebih tinggi >=1 tingkat
            remove_item(target.telegram_id, shield_key, 1)
            red = random.randint(5, 10) if class_diff <= -2 else 15
            damage = int(damage * (100 - red) / 100)
            steal = int(steal * (100 - red) / 100)
            note = f"🛡️ Perisai target hancur, reduksi {red}% karena beda kelas."

    target_cash = target.cash
    steal = min(steal, target_cash)
    if steal > 0:
        update_cash(target.telegram_id, -steal)
        update_cash(attacker.telegram_id, steal)

    if damage > 0:
        # armor menyerap dulu
        remaining = damage
        if target.armor > 0:
            absorbed = min(target.armor, remaining)
            update_hp_armor(target.telegram_id, armor_delta=-absorbed)
            remaining -= absorbed
        if remaining > 0:
            update_hp_armor(target.telegram_id, hp_delta=-remaining)

    await update.message.reply_text(
        f"/dor berhasil ke {target.full_name} dengan Pistol Kelas {pistol_class}.\n"
        f"Cash dicuri: {format_number(steal)}\nDamage: {damage}\n{note}"
    )


async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    sender = update.effective_user
    upsert_user(sender.id, sender.full_name, sender.username or "-")
    if len(context.args) != 2:
        await update.message.reply_text("Format: /transfer <id_tujuan> <jumlah>")
        return
    try:
        tid = int(context.args[0]); amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("ID/jumlah harus angka.")
        return
    if amount <= 0 or tid == sender.id:
        await update.message.reply_text("Nominal/target tidak valid.")
        return
    target = get_user(tid)
    if not target:
        await update.message.reply_text("Target belum terdaftar.")
        return
    if not update_cash(sender.id, -amount):
        await update.message.reply_text("Cash tidak cukup.")
        return
    update_cash(tid, amount)
    nw = now_wib()
    await update.message.reply_text(
        f"<i>Transfer berhasil: {format_number(amount)} cash ke ID {tid}.</i>\n"
        f"<i>Tanggal: {nw.strftime('%Y-%m-%d')}</i>\n"
        f"<i>Jam: {nw.strftime('%H:%M:%S WIB')}</i>",
        parse_mode=ParseMode.HTML,
    )


async def addcoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Format: /addcoin <id> <jumlah>")
        return
    try:
        tid = int(context.args[0]); amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("ID/jumlah harus angka.")
        return
    if amount <= 0 or not update_cash(tid, amount):
        await update.message.reply_text("Gagal menambah cash.")
        return
    await update.message.reply_text(f"Berhasil menambah {format_number(amount)} cash ke {tid}.")


async def setrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Format: /setrole <id/@username> <role>")
        return
    tgt = resolve_user_reference(context.args[0])
    if not tgt:
        await update.message.reply_text("User tidak ditemukan.")
        return
    role_text = " ".join(context.args[1:]).strip()
    if not role_text:
        await update.message.reply_text("Role tidak boleh kosong.")
        return
    if not set_custom_role(tgt.telegram_id, role_text):
        await update.message.reply_text("Gagal mengatur role.")
        return
    await update.message.reply_text(f"Custom role user {tgt.full_name} berhasil diatur: {role_text}")


async def clearrole_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Format: /clearrole <id/@username>")
        return
    tgt = resolve_user_reference(context.args[0])
    if not tgt:
        await update.message.reply_text("User tidak ditemukan.")
        return
    clear_custom_role(tgt.telegram_id)
    await update.message.reply_text("Custom role dihapus.")


async def setlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Format: /setlevel <id/@username> <level>")
        return
    tgt = resolve_user_reference(context.args[0])
    if not tgt:
        await update.message.reply_text("User tidak ditemukan.")
        return
    try:
        level = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Level harus angka.")
        return
    target_level = max(1, level)
    with get_connection() as conn:
        db_execute(
            conn,
            "UPDATE users SET level=?, exp=0, custom_level=NULL WHERE telegram_id=?",
            (target_level, tgt.telegram_id),
        )
    await update.message.reply_text(
        f"Level asli user diatur ke {target_level} dengan EXP 0 (bukan level ilusi)."
    )


async def defaultlevel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Format: /defaultlevel <id/@username>")
        return
    tgt = resolve_user_reference(context.args[0])
    if not tgt:
        await update.message.reply_text("User tidak ditemukan.")
        return
    clear_custom_level(tgt.telegram_id)
    await update.message.reply_text("Custom level dihapus.")


def add_exp_to_user(uid: int, exp_gain: int) -> bool:
    with get_connection() as conn:
        row = db_execute(conn, "SELECT level, exp FROM users WHERE telegram_id=?", (uid,), fetch="one")
        if not row:
            return False
        level = row["level"]
        exp = row["exp"] + exp_gain
        while exp >= exp_needed(level):
            exp -= exp_needed(level)
            level += 1
        db_execute(conn, "UPDATE users SET level=?, exp=?, custom_level=NULL WHERE telegram_id=?", (level, exp, uid))
    return True


async def addexp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Format: /addexp <id/@username> <jumlah_exp>")
        return
    tgt = resolve_user_reference(context.args[0])
    if not tgt:
        await update.message.reply_text("User tidak ditemukan.")
        return
    try:
        exp_gain = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Jumlah exp harus angka.")
        return
    if exp_gain <= 0:
        await update.message.reply_text("Jumlah exp harus lebih dari 0.")
        return
    if not add_exp_to_user(tgt.telegram_id, exp_gain):
        await update.message.reply_text("Gagal menambah exp.")
        return
    updated = get_user(tgt.telegram_id)
    await update.message.reply_text(
        f"Berhasil tambah {format_number(exp_gain)} EXP ke {tgt.full_name}. "
        f"Level: {updated.level} ({updated.exp}/{exp_needed(updated.level)})"
    )


async def claim_command(update: Update, context: ContextTypes.DEFAULT_TYPE, weekly: bool = False) -> None:
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    now = int(time.time())
    col = "last_weekly" if weekly else "last_daily"
    cd = 7 * 24 * 3600 if weekly else 24 * 3600
    reward = 3 if weekly else 1
    with get_connection() as conn:
        row = db_execute(conn, f"SELECT {col} FROM users WHERE telegram_id=?", (uid,), fetch="one")
        if not row:
            return
        if now - row[col] < cd:
            remain = cd - (now - row[col])
            await update.message.reply_text(f"Belum bisa claim. Tunggu {remain//3600} jam lagi.")
            return
        db_execute(conn, f"UPDATE users SET {col}=? WHERE telegram_id=?", (now, uid))
    add_item(uid, "token", reward)
    await update.message.reply_text(f"Berhasil claim {'weekly' if weekly else 'daily'}: +{reward} token.")


async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await claim_command(update, context, weekly=False)


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await claim_command(update, context, weekly=True)


async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_chat:
        return
    if update.effective_chat.type not in {"group", "supergroup"}:
        return
    u = update.effective_user
    upsert_user(u.id, u.full_name, u.username or "-")
    grant_exp_if_ready(u.id)


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN belum diset")
    init_db()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler(["profile", "p"], profile_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("inv", inventory_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("pot", potion_command))
    app.add_handler(CommandHandler("armor", armor_command))
    app.add_handler(CommandHandler("lp", lp_command))
    app.add_handler(CommandHandler("dor", dor_command))
    app.add_handler(CommandHandler(["transfer", "tf"], transfer_command))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("weekly", weekly_command))

    app.add_handler(CommandHandler(["addcoin", "ac"], addcoin_command))
    app.add_handler(CommandHandler(["setrole", "sr"], setrole_command))
    app.add_handler(CommandHandler(["clearrole", "cr"], clearrole_command))
    app.add_handler(CommandHandler(["setlevel", "sl"], setlevel_command))
    app.add_handler(CommandHandler(["defaultlevel", "dl"], defaultlevel_command))
    app.add_handler(CommandHandler(["addexp", "ae"], addexp_command))

    app.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^menu_help$"))
    app.add_handler(CallbackQueryHandler(shop_callback_handler, pattern="^(buy:|secret_shop)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group_message_handler))

    logger.info("Bot berjalan...")
    app.run_polling()


if __name__ == "__main__":
    main()
