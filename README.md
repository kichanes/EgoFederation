# Telegram Level + Currency Bot

Bot Telegram ini punya fitur:
- Lihat profil user: nama, username, ID, cash, level, progress exp, role.
- Sistem exp otomatis saat user chat di grup (cooldown 5 menit, exp random 5-15).
- Level up dengan kebutuhan exp bertingkat (`level * 100`).
- Role otomatis berdasarkan range level.
- Owner bot bisa tambah cash user lain: `/addcoin <id_user> <jumlah>`.
- Owner bot bisa custom role user: `/setrole <id_user> <role_custom>`.
- Owner bot bisa hapus custom role user: `/clearrole <id_user>`.
- Transfer cash antar user: `/transfer <id_tujuan> <jumlah>`.
- User baru otomatis dapat 1.000 cash.

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

## Command

- `/start` -> registrasi/update data user.
- `/profile` -> tampilkan profil user.
- `/addcoin <id_user> <jumlah>` -> owner only.
- `/setrole <id_user> <role_custom>` -> owner only (set role manual).
- `/clearrole <id_user>` -> owner only (kembali ke role otomatis dari level).
- `/transfer <id_tujuan> <jumlah>` -> transfer cash.

## Format Profil

```text
Nama :
Username :
ID :
Cash :
Level : 15 (exp_saat_ini/exp_diperlukan)
Role :
```
