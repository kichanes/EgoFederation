# Telegram Level + Currency Bot

Bot Telegram ini memiliki fitur:
- Profil user (`/profile` atau `/p`) berisi nama, username, id, cash, level, role, register date, dan time.
- Sistem EXP otomatis di grup (5-15 EXP, cooldown 5 menit).
- Currency + transfer (`/transfer` atau `/tf`).
- Inventory (`/inv`) dengan kapasitas default 5 slot.
- HP/Armor status (`/status`) + daftar buff/debuff + alert otomatis jika HP < 20%.
- Shop (`/shop`) dengan format daftar item rapi + bubble item dan pembelian via bubble atau `/buy <kode_item>`.
- Item pakai command:
  - `/pot` (Potion Merah, +10% HP)
  - `/armor` (pakai Armor item, +100 armor)
  - `/lp` (Lucky Potion, buff luck +5% selama 60 menit)
- Item lempar:
  - `/kp` (pakai 🍌 Kulit Pisang ke target, damage 5-10)
  - `/semak` (pakai 🩴 Sandal Emak ke target, damage 7-12)
- Combat `/dor` (reply atau target ID/@username) dengan logika pistol/perisai.
- Token dari `/daily` dan `/weekly`.
- Secret shop terbuka saat level >= 5.
- Premium user punya privilage: Double EXP, hadiah claim daily/weekly double, dan diskon shop 30%.

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
- `/kp <id/@username>` atau reply lalu `/kp`
- `/semak <id/@username>` atau reply lalu `/semak`
- `/transfer <id_tujuan> <jumlah>`
- `/tf <id_tujuan> <jumlah>`
- `/daily`
- `/weekly`
- `/cd` (cek cooldown claim daily/weekly)
- Daily reward: `+150 cash` dan `+50 exp`
- Weekly reward: `+500 cash`, `+250 exp`, `+1 token`, dan `1 chest random`
- `/help`

## Command Owner

Catatan: command owner-only **hanya didokumentasikan di README ini** dan tidak ditampilkan di `/help` maupun bubble help bot.

- `/addcoin` atau `/ac` `<id_user> <jumlah>`
- `/premiumuser` atau `/pu` `<id/@username>`
- `/setrole` atau `/sr` `<id/@username> <role>`
- `/clearrole` atau `/cr` `<id/@username>`
- `/setlevel` atau `/sl` `<id/@username> <level>` (mengatur level asli + reset EXP ke 0)
- `/defaultlevel` atau `/dl` `<id/@username>`
- `/addexp` atau `/ae` `<id/@username> <jumlah_exp>`
