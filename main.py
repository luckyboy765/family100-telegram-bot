"""
Bot Family 100 — Entry point.
"""
import asyncio
import shutil
import os
import logging

logging.basicConfig(level=logging.INFO)

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ChatType

from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, OWNER_IDS
import game_state
import stats
from questions import reload_questions, QUESTIONS
from handlers.new_game import cmd_new
from handlers.solo_mode import start_solo, handle_solo_answer
from handlers.team_mode import (
    start_team, join_team, begin_team_game,
    show_category_picker, pick_category,
    round_play, round_throw, handle_team_answer,
    end_team_game,
)
from handlers.admin import cmd_start, cmd_broadcast, do_backup, backup_loop, register_chat

# Salin JSON soal ke folder bot bila belum ada
_SRC = os.path.join(os.path.dirname(__file__), "family100_questions.json")
if not os.path.exists(_SRC):
    _parent = os.path.join(os.path.dirname(__file__), "..", "family100_questions.json")
    if os.path.exists(_parent):
        shutil.copy(_parent, _SRC)

app = Client(
    "family100_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ─── Commands ────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def on_start(client: Client, message: Message):
    register_chat(message.chat.id)
    await cmd_start(client, message)


@app.on_message(filters.command("new") & (filters.group | filters.private))
async def on_new(client: Client, message: Message):
    register_chat(message.chat.id)
    await cmd_new(client, message)


@app.on_message(filters.command("stop") & (filters.group | filters.private))
async def on_stop(client: Client, message: Message):
    chat_id = message.chat.id
    session = game_state.get(chat_id)
    if not session:
        await message.reply("Tidak ada game aktif.")
        return
    if hasattr(session, "timer_task") and session.timer_task and not session.timer_task.done():
        session.timer_task.cancel()
    session.active = False
    game_state.remove(chat_id)
    await message.reply("🛑 Game dihentikan.")


@app.on_message(filters.command("broadcast"))
async def on_broadcast(client: Client, message: Message):
    await cmd_broadcast(client, message)


@app.on_message(filters.command(["leaderboard", "lb", "peringkat"]))
async def on_leaderboard(client: Client, message: Message):
    arg = (message.command[1].lower() if len(message.command) > 1 else "")
    kind = "weekly" if arg in ("mingguan", "minggu", "weekly", "week") else "global"
    await message.reply(stats.format_leaderboard(kind, 10))


@app.on_message(filters.command(["stats", "statistik", "profil"]))
async def on_stats(client: Client, message: Message):
    u = message.from_user
    s = stats.user_stats(u.id)
    if not s:
        await message.reply("📊 Kamu belum punya statistik. Main dulu lewat /new!")
        return
    await message.reply(
        f"📊 <b>Statistik {u.first_name}</b>\n\n"
        f"🏅 Total poin: <b>{s['points']}</b>\n"
        f"✅ Jawaban benar: <b>{s['correct']}</b>\n"
        f"🎮 Game dimainkan: <b>{s['games']}</b>\n"
        f"🏆 Menang: <b>{s['wins']}</b>"
    )


@app.on_message(filters.command("reload") & filters.user(list(OWNER_IDS)))
async def on_reload(client: Client, message: Message):
    try:
        n = reload_questions()
        await message.reply(f"🔄 Bank soal dimuat ulang: <b>{n}</b> soal.")
    except Exception as e:
        await message.reply(f"❌ Gagal reload: {e}")


@app.on_message(filters.command("help") & (filters.group | filters.private))
async def on_help(client: Client, message: Message):
    await message.reply(
        "📖 <b>Perintah Family 100</b>\n\n"
        "• /new — mulai game (Solo / Tim)\n"
        "• /stop — hentikan game\n"
        "• /leaderboard — peringkat global (tambah <code>mingguan</code> untuk mingguan)\n"
        "• /stats — statistik pribadi\n"
        "• /help — bantuan ini\n\n"
        "💡 Jawaban toleran typo. Jawab cepat & beruntun dapat bonus poin!"
    )


@app.on_message(filters.command("backup") & filters.user(list(OWNER_IDS)))
async def on_backup(client: Client, message: Message):
    await message.reply("📦 Mengirim backup...")
    await do_backup(client)
    await message.reply("✅ Backup selesai.")


# ─── Callback Handler ─────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^f100:"))
async def on_callback(client: Client, callback: CallbackQuery):
    data = callback.data
    parts = data.split(":")

    if parts[1] == "cancel":
        chat_id = callback.message.chat.id
        session = game_state.get(chat_id)
        if session:
            if hasattr(session, "timer_task") and session.timer_task and not session.timer_task.done():
                session.timer_task.cancel()
            game_state.remove(chat_id)
        await callback.message.edit("❌ Game dibatalkan.")
        return

    if parts[1] == "mode":
        mode = parts[2]
        if mode == "solo":
            await start_solo(client, callback)
        elif mode == "team":
            await start_team(client, callback)

    elif parts[1] == "join":
        team = parts[2]
        await join_team(client, callback, team)

    elif parts[1] == "team":
        action = parts[2]
        if action == "start":
            await begin_team_game(client, callback)

    elif parts[1] == "cat":
        idx = int(parts[2])
        await pick_category(client, callback, idx)

    elif parts[1] == "round":
        action = parts[2]
        if action == "play":
            await round_play(client, callback)
        elif action == "throw":
            await round_throw(client, callback)


# ─── Answer Handler ───────────────────────────────────────────────────────────

@app.on_message(filters.text & (filters.group | filters.private) & ~filters.command([]))
async def on_text(client: Client, message: Message):
    if (message.text or "").startswith("/"):
        return
    chat_id = message.chat.id
    session = game_state.get(chat_id)
    if not session or not session.active:
        return

    if session.mode == "solo":
        await handle_solo_answer(client, message)
    elif session.mode == "team":
        await handle_team_answer(client, message)


# ─── Startup ─────────────────────────────────────────────────────────────────

async def _notify_restart(client: Client):
    """Beri tahu chat yang game-nya terputus karena bot restart."""
    for cid in game_state.pop_stale_actives():
        try:
            await client.send_message(
                cid,
                "⚠️ Bot baru saja diperbarui/di-restart, jadi game yang sedang "
                "berjalan direset. Ketik /new untuk main lagi. 🙏"
            )
        except Exception:
            pass


async def main():
    stats.init_db()
    await app.start()
    print(f"✅ Family 100 Bot started! ({len(QUESTIONS)} soal)")
    await _notify_restart(app)
    asyncio.create_task(backup_loop(app))
    await asyncio.Event().wait()  # keep running


if __name__ == "__main__":
    app.run(main())
