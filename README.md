# Telegram Level + Currency Bot

Bot Telegram ini punya fitur:
- Lihat profil user: nama, username, ID, cash, level, progress exp, role.
- Sistem exp otomatis saat user chat di grup (cooldown 5 menit, exp random 5-15).
- Level up dengan kebutuhan exp bertingkat (`level * 100`).
- Role otomatis berdasarkan range level.
- Owner bot bisa tambah cash user lain: `/addcoin <id_user> <jumlah>`.
- Owner bot bisa custom role user via ID/username: `/setrole <id_user/@username> <role_custom>`.
- Owner bot bisa hapus custom role user via ID/username: `/clearrole <id_user/@username>`.
- Transfer cash antar user: `/transfer <id_tujuan> <jumlah>` atau `/tf <id_tujuan> <jumlah>`.
- Command bantuan: `/help`.
- User baru otomatis dapat 1.000 cash.
- Datetime otomatis tampil saat menggunakan `/profile` dengan timezone WIB.
- Saat `/profile` dikirim, bot menampilkan 2 bubble ber-emoji: `❓ Help` dan link CH komunitas `📢 Ego Federation` (`t.me/EgoFederation`).
- Saat `/profile` dikirim, bot menampilkan foto profil user berbentuk bulat (ukuran kecil) jika tersedia.

## Instalasi

1. Buat bot di BotFather dan ambil token.
2. Install dependency:

```bash
pip install -r requirements.txt
```

3. Salin `.env.example` jadi `.env`, lalu isi:

```env
BOT_TOKEN=...
BOT_OWNER_ID=...
DB_PATH=bot_data.sqlite3
```

4. Jalankan bot (contoh dengan export env):

```bash
export $(cat .env | xargs)
python bot.py
```

## Opsi PostgreSQL (JavaScript Data Layer)

Jika ingin data permanen di PostgreSQL, gunakan file JavaScript berikut:
- `js/db.js` -> koneksi + inisialisasi tabel users.
- `js/userService.js` -> function user (upsert, cash, exp, custom role/level, dll).

Install dependency JS:

```bash
npm install
```

Variable PostgreSQL yang digunakan:
- `PGHOST`
- `PGPORT`
- `PGUSER`
- `PGPASSWORD`
- `PGDATABASE`
- `PGSSL` (`true/false`)

## Command

- `/start` -> registrasi/update data user.
- `/profile` -> tampilkan profil sendiri.
- `/profile <id/@username>` -> tampilkan profil user lain.
- Reply pesan user lalu ketik `/profile` -> tampilkan profil user yang direply.
- `/addcoin <id_user> <jumlah>` -> owner only.
- `/setrole <id_user/@username> <role_custom>` -> owner only (set role manual).
- `/clearrole <id_user/@username>` -> owner only (kembali ke role otomatis dari level).
- `/setlevel <id_user/@username> <level_custom>` -> owner only (set level manual).
- `/defaultlevel <id_user/@username>` -> owner only (kembalikan ke level asli dari EXP).
- `/transfer <id_tujuan> <jumlah>` -> transfer cash.
- `/tf <id_tujuan> <jumlah>` -> alias singkat transfer.
- Setelah transfer berhasil, bot akan menampilkan konfirmasi italic + tanggal & jam pengiriman (WIB).
- `/help` -> tampilkan daftar command.

## Format Profil

```text
Nama :
Username :
ID :
Cash :
Level : 15 (exp_saat_ini/exp_diperlukan)
Role :
Date :
Time :
```
