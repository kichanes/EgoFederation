# Telegram Level + Currency Bot

Bot Telegram ini memiliki fitur:
- Profil user (`/profile` atau `/p`) berisi nama, username, id, cash, level, role, register date, dan time.
- Sistem EXP otomatis di grup (5-15 EXP, cooldown 5 menit).
- Currency + transfer (`/transfer` atau `/tf`).
- Inventory (`/inv`) dengan kapasitas default 5 slot.
- HP/Armor status (`/status`) + daftar buff/debuff + alert otomatis jika HP < 20%.
- Shop (`/shop`) dengan format daftar item rapi + bubble item dan pembelian via bubble atau `/buy <kode_item>`.
- Upgrade Tas di shop (setiap jenis hanya bisa dibeli 1x/user) untuk menambah kapasitas inventory:
  - Tas Kecil `+3`
  - Tas Tenun `+5`
  - Tas Samping `+7`
  - Tas Sekolah `+10`
  - Tas Gunung `+15`
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
- Saat Railway memberikan kredensial baru, cukup update value `DATABASE_URL` di environment service bot.
- Jika koneksi PostgreSQL gagal saat runtime, bot akan fallback ke SQLite (`DB_URI`) agar bot tetap jalan.
- Alternatif: gunakan Railway Volume + `DB_URI=/data/bot_data.sqlite3`.
- Jangan pakai path lokal sementara seperti `./bot_data.sqlite3` di Railway jika ingin data tetap ada setelah redeploy.


### Konfigurasi Database Node.js

Data layer JavaScript sekarang memakai file `config/db.config.js`.

Prioritas konfigurasi:
1. `DATABASE_URL` (langsung dipakai jika tersedia)
2. Fallback per variable: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL`

Contoh cepat:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=egofederation
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_SSL=false
```


### Wajib Panggil `upsertUser` Saat Ada Message

Agar data user otomatis tersimpan/update, panggil `upsertUser` di handler message.

```js
const { ensureUserOnMessage } = require('./js/botMiddleware');

bot.on('message', ensureUserOnMessage);
```

Atau langsung:

```js
const { upsertUser } = require('./js/userService');

bot.on('message', async (ctx) => {
  await upsertUser({
    telegramId: ctx.from.id,
    fullName: ctx.from.first_name,
    username: ctx.from.username
  });
});
```


### Schema PostgreSQL (Game-Ready)

Schema siap pakai ada di `db/schema.sql` (users, items, user_items, shop + index leaderboard/lookup).

Jalankan inisialisasi schema:

```bash
npm run db:init
```

`users` sekarang sudah mencakup field economy/cooldown penting: `bank`, `last_daily`, `last_work`, dan `last_exp_time`.

Selain itu, `updateCash` di service sudah memakai 1 query atomik + `RETURNING cash` untuk menghindari race condition saat update saldo bersamaan.

Contoh query dasar:

```sql
-- Ambil profile user
SELECT * FROM users WHERE telegram_id = $1;

-- Ambil inventory user + nama item
SELECT i.name, ui.quantity
FROM user_items ui
JOIN items i ON ui.item_id = i.id
WHERE ui.telegram_id = $1 AND ui.quantity > 0;

-- Tambah item ke inventory (stack)
INSERT INTO user_items (telegram_id, item_id, quantity)
VALUES ($1, $2, 1)
ON CONFLICT (telegram_id, item_id)
DO UPDATE SET quantity = user_items.quantity + 1;
```

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
- `/lb` (leaderboard lokal berdasarkan level)
- `/lbglobal` (leaderboard global berdasarkan level)
- `/lb 100` atau `/lbglobal 100` untuk top 100 (hasil dikirim ke chat pribadi bot)
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
