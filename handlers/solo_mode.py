"""
Handler Mode Solo — Siapa Cepat.
"""
import asyncio
import time

from pyrogram.types import CallbackQuery, Message

import game_state
import stats
from helpers import ikb, format_scoreboard_solo, render_answers
from models import SoloSession
from questions import get_random_questions, find_answer

SOLO_TIMEOUT = 120          # 2 menit per soal
HINT1_AT = 60               # detik: buka jumlah huruf
HINT2_AT = 90               # detik: buka huruf pertama


async def start_solo(client, callback: CallbackQuery):
    chat_id = callback.message.chat.id

    if game_state.get(chat_id):
        await callback.answer("Sudah ada game aktif!", show_alert=True)
        return

    questions = get_random_questions(5, chat_id=chat_id)
    session = SoloSession(chat_id=chat_id, questions=questions)
    game_state.set(chat_id, session)

    await callback.message.edit(
        "⚡ <b>Mode Solo dimulai!</b>\nSemua pemain boleh menjawab. Siapa cepat dia dapat poin!\n\n"
        "Soal berganti tiap <b>2 menit</b> atau bila semua terjawab.\n"
        "💨 Jawab cepat = <b>bonus poin</b>, benar beruntun = <b>bonus streak</b>!",
    )
    await asyncio.sleep(1)
    await show_solo_question(client, chat_id)


async def show_solo_question(client, chat_id: int):
    session: SoloSession = game_state.get(chat_id)
    if not session or not session.active:
        return

    q = session.current_question
    if not q:
        await end_solo(client, chat_id)
        return

    session.answered = {}
    session.hint_level = 0
    session.q_start = time.monotonic()
    board = render_answers(q, session.answered)

    await client.send_message(
        chat_id,
        f"❓ <b>Soal {session.current_idx + 1}/5</b>\n"
        f"📂 Kategori: <b>{q['category']}</b>\n\n"
        f"<b>{q['question']}</b>\n\n"
        f"{board}\n\n"
        f"⏳ <b>Waktu: 2 menit</b> | Ketik jawaban di chat!",
    )

    for t in (session.timer_task, session.hint_task):
        if t and not t.done():
            t.cancel()
    session.timer_task = asyncio.create_task(_solo_timeout(client, chat_id, session.current_idx))
    session.hint_task = asyncio.create_task(_solo_hints(client, chat_id, session.current_idx))


async def _solo_hints(client, chat_id: int, q_idx: int):
    """Buka bantuan bertahap bila belum semua terjawab."""
    try:
        await asyncio.sleep(HINT1_AT)
        s: SoloSession = game_state.get(chat_id)
        if not s or not s.active or s.current_idx != q_idx or not s.remaining_answers:
            return
        s.hint_level = 1
        await client.send_message(
            chat_id, "💡 <b>Bantuan — jumlah huruf:</b>\n\n"
            + render_answers(s.current_question, s.answered, hint=1))

        await asyncio.sleep(HINT2_AT - HINT1_AT)
        s = game_state.get(chat_id)
        if not s or not s.active or s.current_idx != q_idx or not s.remaining_answers:
            return
        s.hint_level = 2
        await client.send_message(
            chat_id, "💡 <b>Bantuan — huruf pertama:</b>\n\n"
            + render_answers(s.current_question, s.answered, hint=2))
    except asyncio.CancelledError:
        pass


async def _solo_timeout(client, chat_id: int, q_idx: int):
    await asyncio.sleep(SOLO_TIMEOUT)
    session: SoloSession = game_state.get(chat_id)
    if not session or not session.active or session.current_idx != q_idx:
        return

    q = session.current_question
    board = render_answers(q, session.answered)
    try:
        await client.send_message(
            chat_id,
            f"⏰ <b>Waktu habis!</b>\n\n"
            f"Jawaban lengkap soal <b>{q['question']}</b>:\n{board}"
        )
    except Exception as e:
        print(f"[timeout] Gagal kirim: {e}")

    await next_solo_question(client, chat_id)


async def next_solo_question(client, chat_id: int):
    session: SoloSession = game_state.get(chat_id)
    if not session or not session.active:
        return

    session.current_idx += 1
    if session.current_idx >= len(session.questions):
        await end_solo(client, chat_id)
    else:
        await asyncio.sleep(2)
        try:
            await show_solo_question(client, chat_id)
        except Exception as e:
            print(f"[next_solo_question] Error: {e}")


def _bonus(elapsed: float, streak: int):
    """Hitung bonus kecepatan & streak."""
    if elapsed <= 15:
        speed = 5
    elif elapsed <= 30:
        speed = 3
    elif elapsed <= 60:
        speed = 1
    else:
        speed = 0
    streak_b = min(max(streak - 1, 0), 5) * 2   # +2 per beruntun, maks +10
    return speed, streak_b


async def handle_solo_answer(client, message: Message):
    chat_id = message.chat.id
    session: SoloSession = game_state.get(chat_id)

    if not session or session.mode != "solo" or not session.active:
        return

    q = session.current_question
    if not q:
        return

    user = message.from_user
    if not user:
        return

    matched = find_answer(message.text or "", q["answers"], session.answered)
    if not matched:
        return

    # Streak & bonus
    uid = user.id
    if session.last_scorer == uid:
        session.streaks[uid] = session.streaks.get(uid, 1) + 1
    else:
        session.streaks[uid] = 1
    session.last_scorer = uid
    streak = session.streaks[uid]

    elapsed = time.monotonic() - session.q_start
    speed_b, streak_b = _bonus(elapsed, streak)
    gained = matched["points"] + speed_b + streak_b

    session.answered[matched["key"]] = f"{user.first_name}" + (f" @{user.username}" if user.username else "")
    uname = user.username or ""
    name = f"{user.first_name} {user.last_name or ''}".strip()

    if uid not in session.scores:
        session.scores[uid] = {"name": name, "username": uname, "points": 0}
    session.scores[uid]["points"] += gained
    stats.record_answer(uid, name, uname, gained)

    board = render_answers(q, session.answered, hint=session.hint_level)
    mention = f"@{uname}" if uname else name
    extra = []
    if speed_b:
        extra.append(f"💨 +{speed_b} cepat")
    if streak_b:
        extra.append(f"🔥 +{streak_b} streak x{streak}")
    extra_txt = ("  (" + ", ".join(extra) + ")") if extra else ""

    await message.reply(
        f"✅ <b>{matched['label']}</b> — <b>+{gained}</b> poin{extra_txt}\n"
        f"👤 {mention}\n\n"
        f"{board}"
    )

    if not session.remaining_answers:
        for t in (session.timer_task, session.hint_task):
            if t and not t.done():
                t.cancel()
        await asyncio.sleep(1)
        await next_solo_question(client, chat_id)


async def end_solo(client, chat_id: int):
    session: SoloSession = game_state.get(chat_id)
    if not session:
        return

    session.active = False
    for t in (session.timer_task, session.hint_task):
        if t and not t.done():
            t.cancel()

    scoreboard = format_scoreboard_solo(session.scores)

    # Catat statistik: game dimainkan + kemenangan (skor tertinggi)
    try:
        players = [{"user_id": uid, "name": d["name"], "username": d["username"]}
                   for uid, d in session.scores.items()]
        if players:
            stats.record_games(players)
            top = max(session.scores.items(), key=lambda x: x[1]["points"])
            if top[1]["points"] > 0:
                stats.record_wins([top[0]])
    except Exception as e:
        print(f"[end_solo] stats: {e}")

    try:
        await client.send_message(
            chat_id,
            f"🎉 <b>Game Solo Selesai!</b>\n\n{scoreboard}\n\n"
            f"📊 Ketik /leaderboard untuk peringkat global."
        )
    except Exception as e:
        print(f"[end_solo] Gagal kirim scoreboard: {e}")
    finally:
        game_state.remove(chat_id)
