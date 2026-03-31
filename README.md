# Telegram Level + Currency Bot

Bot Telegram ini memiliki fitur:
- Profil user (`/profile` atau `/p`) berisi nama, username, id, cash, level, role, register date, dan time.
- Sistem EXP otomatis di grup (5-15 EXP, cooldown 5 menit).
- Currency + transfer (`/transfer` atau `/tf`).
- Inventory (`/inv`) dengan kapasitas default 5 slot.
- HP/Armor status (`/status`) + daftar buff/debuff + alert otomatis jika HP < 20%.
- Shop (`/shop`) dengan bubble item dan pembelian via bubble atau `/buy <kode_item>`.
- Item pakai command:
  - `/pot` (Potion Merah, +10% HP)
  - `/armor` (pakai Armor item, +100 armor)
  - `/lp` (Lucky Potion, buff luck +5% selama 60 menit)
- Combat `/dor` (reply atau target ID/@username) dengan logika pistol/perisai.
- Token dari `/daily` dan `/weekly`.
- Secret shop terbuka saat level >= 5.

## Instalasi

```bash
pip install -r requirements.txt
cp .env.example .env
# isi BOT_TOKEN dan BOT_OWNER_ID
python bot.py
```

## Menjalankan 24 Jam Tanpa Railway/Heroku (1 Repo)

Gunakan Docker Compose:

```bash
docker compose up -d --build
docker compose logs -f telegram-bot
```

`docker-compose.yml` sudah menggunakan `restart: unless-stopped` + service PostgreSQL (`pg_data` volume) agar data tetap aman saat restart/crash.

## Railway (Agar Data Tidak Hilang Saat Redeploy)

- **Paling direkomendasikan:** pakai `DATABASE_URL` PostgreSQL Railway (persistent).
- Jika `DATABASE_URL` diisi, bot otomatis memakai PostgreSQL (bukan SQLite lokal).
- Alternatif: gunakan Railway Volume + `DB_PATH=/data/bot_data.sqlite3`.
- Jangan pakai path lokal sementara seperti `./bot_data.sqlite3` di Railway jika ingin data tetap ada setelah redeploy.

## Command User

- `/start`
- `/p` atau `/profile`
- `/status`
- `/inv`
- `/shop`
- `/buy <kode_item>`
- `/pot`
- `/armor`
- `/lp`
- `/dor <id/@username>` atau reply lalu `/dor`
- `/transfer <id_tujuan> <jumlah>`
- `/tf <id_tujuan> <jumlah>`
- `/daily`
- `/weekly`
- `/help`

## Command Owner

- `/addcoin <id_user> <jumlah>`
- `/setrole <id/@username> <role>`
- `/clearrole <id/@username>`
- `/setlevel <id/@username> <level>` (mengatur level asli + reset EXP ke 0)
- `/defaultlevel <id/@username>`
