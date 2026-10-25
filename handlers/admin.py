"""
Handler admin: /broadcast, backup harian, /start.
"""
import asyncio
import json
import os
from datetime import datetime
from io import BytesIO

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID, OWNER_IDS, LOG_GROUP
import game_state


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(client: Client, message: Message):
    bot = await client.get_me()
    bot_username = bot.username

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "➕ Tambahkan ke Grup",
            url=f"https://t.me/{bot_username}?startgroup=true"
        )
    ]])

    text = (
        f"👋 Halo <b>{message.from_user.first_name}</b>!\n\n"
        f"🎮 Saya adalah bot <b>Family 100</b>!\n\n"
        f"📖 <b>Cara bermain:</b>\n"
        f"• Tambahkan saya ke grup\n"
        f"• Ketik /new untuk mulai game\n"
        f"• Pilih mode <b>Solo</b> atau <b>Tim</b>\n"
        f"• Jawab pertanyaan sebelum waktu habis!\n\n"
        f"🏆 <b>Mode:</b>\n"
        f"• <b>Solo</b> — siapa cepat dia dapat poin\n"
        f"• <b>Tim</b> — 2 tim berebut jawaban\n\n"
        f"⚙️ <b>Perintah:</b>\n"
        f"• /new — Mulai game baru\n"
        f"• /stop — Hentikan game\n\n"
        f"Tekan tombol di bawah untuk menambahkan ke grup!"
    )

    await message.reply(text, reply_markup=markup)


# ─── /broadcast ───────────────────────────────────────────────────────────────

async def cmd_broadcast(client: Client, message: Message):
    """Hanya owner yang bisa broadcast ke semua chat yang pernah pakai bot."""
    if message.from_user.id not in OWNER_IDS:
        await message.reply("❌ Hanya owner yang bisa broadcast.")
        return

    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply(
            "Gunakan: <code>/broadcast pesan kamu</code>\n"
            "Atau reply ke pesan yang ingin di-broadcast."
        )
        return

    # Ambil teks broadcast
    if message.reply_to_message:
        bc_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    else:
        bc_text = message.text.split(None, 1)[1]

    if not bc_text:
        await message.reply("Pesan broadcast kosong.")
        return

    # Load daftar chat dari file
    chat_ids = _load_chat_ids()
    if not chat_ids:
        await message.reply("Belum ada chat terdaftar.")
        return

    proses = await message.reply(f"📡 Mengirim broadcast ke {len(chat_ids)} chat...")
    success = 0
    failed = 0

    for cid in chat_ids:
        try:
            await client.send_message(cid, bc_text)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # hindari flood

    await proses.edit(
        f"✅ Broadcast selesai!\n"
        f"Berhasil: {success} | Gagal: {failed}"
    )


# ─── Backup harian ────────────────────────────────────────────────────────────

async def do_backup(client: Client):
    """Kirim file JSON soal + state ke LOG_GROUP sebagai backup."""
    if not LOG_GROUP:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Backup file soal
    questions_path = os.path.join(os.path.dirname(__file__), "..", "family100_questions.json")
    if os.path.exists(questions_path):
        try:
            await client.send_document(
                LOG_GROUP,
                questions_path,
                caption=f"📦 <b>Backup Harian</b>\n🕐 {now}\n📄 File: family100_questions.json"
            )
        except Exception as e:
            print(f"[Backup] Gagal kirim soal: {e}")

    # Backup daftar chat
    chat_ids = _load_chat_ids()
    if chat_ids:
        data = json.dumps({"chats": chat_ids, "backup_time": now}, indent=2)
        buf = BytesIO(data.encode())
        buf.name = "chats_backup.json"
        try:
            await client.send_document(
                LOG_GROUP,
                buf,
                caption=f"📦 <b>Backup Chat List</b>\n🕐 {now}\n👥 {len(chat_ids)} chat terdaftar"
            )
        except Exception as e:
            print(f"[Backup] Gagal kirim chat list: {e}")


async def backup_loop(client: Client):
    """Loop backup setiap 24 jam."""
    while True:
        await asyncio.sleep(24 * 60 * 60)  # 24 jam
        await do_backup(client)


# ─── Tracking chat ────────────────────────────────────────────────────────────

_CHAT_FILE = os.path.join(os.path.dirname(__file__), "..", "chats.json")


def _load_chat_ids() -> list:
    if not os.path.exists(_CHAT_FILE):
        return []
    try:
        with open(_CHAT_FILE, encoding="utf-8") as f:
            return json.load(f).get("chats", [])
    except Exception:
        return []


def register_chat(chat_id: int):
    """Simpan chat_id ke file bila belum ada."""
    chats = _load_chat_ids()
    if chat_id not in chats:
        chats.append(chat_id)
        with open(_CHAT_FILE, "w", encoding="utf-8") as f:
            json.dump({"chats": chats}, f)
