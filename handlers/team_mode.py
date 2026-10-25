"""
Handler Mode Tim — 5 vs 5.
"""
import asyncio
import random

from pyrogram.types import CallbackQuery, Message

import game_state
import stats
from helpers import ikb, format_board_team, render_answers
from models import TeamSession
from questions import get_categories, normalize, find_answer

MAX_PER_TEAM = 5
ANSWER_TIMEOUT = 30  # detik per giliran menjawab


# ─── Lobby ────────────────────────────────────────────────────────────────────

async def start_team(client, callback: CallbackQuery):
    chat_id = callback.message.chat.id

    if game_state.get(chat_id):
        await callback.answer("Sudah ada game aktif!", show_alert=True)
        return

    session = TeamSession(chat_id=chat_id)
    game_state.set(chat_id, session)

    markup = ikb([
        [("🔴 Gabung Tim Merah", "f100:join:red"), ("🔵 Gabung Tim Biru", "f100:join:blue")],
        [("✅ Mulai Game", "f100:team:start"), ("❌ Batal", "f100:cancel")],
    ])

    msg = await callback.message.edit(
        "👥 <b>Mode Tim — Lobby</b>\n\n"
        "🔴 <b>Tim Merah</b>: (kosong)\n"
        "🔵 <b>Tim Biru</b>: (kosong)\n\n"
        "Tekan tombol untuk bergabung ke tim!\n"
        "Maksimal <b>5 pemain</b> per tim. Minimal <b>1 pemain</b> per tim.\n"
        "Jumlah pemain antar tim tidak harus sama.\n\n"
        "Tekan <b>Mulai Game</b> bila sudah siap.",
        reply_markup=markup,
    )
    session.lobby_msg_id = msg.id


async def join_team(client, callback: CallbackQuery, team: str):
    chat_id = callback.message.chat.id
    session: TeamSession = game_state.get(chat_id)

    if not session or session.phase != "lobby":
        await callback.answer("Tidak ada lobby aktif.", show_alert=True)
        return

    user = callback.from_user
    uid = user.id
    name = f"{user.first_name} {user.last_name or ''}".strip()
    uname = user.username or ""
    player = {"user_id": uid, "name": name, "username": uname}

    all_players = session.team_red + session.team_blue
    if any(p["user_id"] == uid for p in all_players):
        await callback.answer("Kamu sudah bergabung ke tim!", show_alert=True)
        return

    if team == "red":
        if len(session.team_red) >= MAX_PER_TEAM:
            await callback.answer("Tim Merah sudah penuh!", show_alert=True)
            return
        session.team_red.append(player)
    else:
        if len(session.team_blue) >= MAX_PER_TEAM:
            await callback.answer("Tim Biru sudah penuh!", show_alert=True)
            return
        session.team_blue.append(player)

    await callback.answer(f"Berhasil bergabung ke Tim {'Merah' if team == 'red' else 'Biru'}!")
    await _update_lobby(client, session)


async def _update_lobby(client, session: TeamSession):
    red_list = "\n".join(
        f"  {i+1}. {p['name']}" + (f" (@{p['username']})" if p.get("username") else "")
        for i, p in enumerate(session.team_red)
    ) or "  (kosong)"
    blue_list = "\n".join(
        f"  {i+1}. {p['name']}" + (f" (@{p['username']})" if p.get("username") else "")
        for i, p in enumerate(session.team_blue)
    ) or "  (kosong)"

    markup = ikb([
        [("🔴 Gabung Tim Merah", "f100:join:red"), ("🔵 Gabung Tim Biru", "f100:join:blue")],
        [("✅ Mulai Game", "f100:team:start"), ("❌ Batal", "f100:cancel")],
    ])

    try:
        await client.edit_message_text(
            session.chat_id,
            session.lobby_msg_id,
            f"👥 <b>Mode Tim — Lobby</b>\n\n"
            f"🔴 <b>Tim Merah</b> ({len(session.team_red)}/{MAX_PER_TEAM}):\n{red_list}\n\n"
            f"🔵 <b>Tim Biru</b> ({len(session.team_blue)}/{MAX_PER_TEAM}):\n{blue_list}\n\n"
            f"Tekan <b>Mulai Game</b> bila sudah siap.",
            reply_markup=markup,
        )
    except Exception:
        pass


# ─── Mulai Game ───────────────────────────────────────────────────────────────

async def begin_team_game(client, callback: CallbackQuery):
    chat_id = callback.message.chat.id
    session: TeamSession = game_state.get(chat_id)

    if not session or session.phase != "lobby":
        await callback.answer("Tidak ada lobby aktif.", show_alert=True)
        return

    if len(session.team_red) < 1 or len(session.team_blue) < 1:
        await callback.answer("Setiap tim harus punya minimal 1 pemain!", show_alert=True)
        return

    session.playing_team = random.choice(["red", "blue"])
    session.choosing_team = session.playing_team
    session.phase = "pick_category"

    # Siapkan semua kategori yang tersedia
    session.categories = get_categories(12, chat_id=chat_id)

    first_team = "🔴 Tim Merah" if session.playing_team == "red" else "🔵 Tim Biru"
    await callback.message.edit(
        f"🎮 <b>Game Tim Dimulai!</b>\n\n"
        f"Tim yang bermain pertama: <b>{first_team}</b>\n\n"
        f"{format_board_team(session)}"
    )
    await asyncio.sleep(2)
    await show_category_picker(client, chat_id)


# ─── Pilih Kategori ───────────────────────────────────────────────────────────

async def show_category_picker(client, chat_id: int):
    session: TeamSession = game_state.get(chat_id)
    if not session:
        return

    # Sudah 6 soal dimainkan → selesai
    if session.current_q_idx >= 6:
        await end_team_game(client, chat_id)
        return

    picked_ids = [q["question"]["id"] for q in session.selected_questions]
    available = [c for c in session.categories if c["question"]["id"] not in picked_ids]

    if not available:
        await end_team_game(client, chat_id)
        return

    # Tim yang memilih kategori = tim yang bermain
    choosing = "🔴 Tim Merah" if session.choosing_team == "red" else "🔵 Tim Biru"
    chooser_team = session.team_red if session.choosing_team == "red" else session.team_blue
    chooser = chooser_team[session.round_pick_idx % len(chooser_team)]
    chooser_mention = f"@{chooser['username']}" if chooser.get("username") else chooser["name"]

    cat_buttons = []
    row = []
    for i, cat in enumerate(available[:12]):
        row.append((f"📂 {cat['category']}", f"f100:cat:{i}"))
        if len(row) == 2:
            cat_buttons.append(row)
            row = []
    if row:
        cat_buttons.append(row)

    markup = ikb(cat_buttons)

    await client.send_message(
        chat_id,
        f"📂 <b>Pilih Kategori Soal</b> ({session.current_q_idx + 1}/6)\n\n"
        f"Giliran pilih: <b>{choosing}</b>\n"
        f"Pemilih: {chooser_mention}\n\n"
        f"{format_board_team(session)}",
        reply_markup=markup,
    )


async def pick_category(client, callback: CallbackQuery, cat_idx: int):
    chat_id = callback.message.chat.id
    session: TeamSession = game_state.get(chat_id)

    if not session or session.phase != "pick_category":
        await callback.answer("Bukan waktunya memilih kategori.", show_alert=True)
        return

    if session.choosing_team == "red":
        chooser = session.team_red[session.round_pick_idx % len(session.team_red)]
    else:
        chooser = session.team_blue[session.round_pick_idx % len(session.team_blue)]

    if callback.from_user.id != chooser["user_id"]:
        await callback.answer("Bukan giliranmu memilih!", show_alert=True)
        return

    picked_ids = [q["question"]["id"] for q in session.selected_questions]
    available = [c for c in session.categories if c["question"]["id"] not in picked_ids]

    if cat_idx >= len(available):
        await callback.answer("Pilihan tidak valid.", show_alert=True)
        return

    chosen = available[cat_idx]
    session.selected_questions.append(chosen)
    session.round_pick_idx += 1
    session.phase = "playing"

    await callback.answer(f"Kategori '{chosen['category']}' dipilih!")
    await callback.message.delete()
    await show_team_question(client, chat_id)


# ─── Babak Bermain ────────────────────────────────────────────────────────────

async def start_team_round(client, chat_id: int):
    """Tidak dipakai lagi."""
    pass


async def round_play(client, callback):
    """Tidak dipakai lagi."""
    pass


async def round_throw(client, callback):
    """Tidak dipakai lagi."""
    pass


async def show_team_question(client, chat_id: int):
    session: TeamSession = game_state.get(chat_id)
    if not session or not session.active:
        return

    q_data = session.selected_questions[-1]
    q = q_data["question"]
    session.answered = {}
    session.wrong_count = 0
    session.steal_chance = False

    playing = "🔴 Tim Merah" if session.playing_team == "red" else "🔵 Tim Biru"
    answerer = session.current_answerer()
    answerer_mention = (
        f"@{answerer['username']}" if answerer and answerer.get("username")
        else (answerer["name"] if answerer else "?")
    )

    board = render_answers(q, session.answered)
    total_pts = sum(a["points"] for a in q["answers"])

    await client.send_message(
        chat_id,
        f"🎮 <b>Soal {session.current_q_idx + 1}/6</b>\n"
        f"📂 Kategori: <b>{q_data['category']}</b>\n\n"
        f"<b>{q['question']}</b>\n\n"
        f"{board}\n\n"
        f"💰 Total nilai: <b>{total_pts} poin</b>\n"
        f"Giliran: <b>{playing}</b>\n"
        f"Penjawab: {answerer_mention}\n\n"
        f"<i>Ketik jawaban di chat!</i>",
    )


async def handle_team_answer(client, message: Message):
    """Dipanggil dari message handler saat ada pesan di grup dengan game tim aktif."""
    chat_id = message.chat.id
    session: TeamSession = game_state.get(chat_id)

    if not session or session.mode != "team" or not session.active:
        return
    if session.phase not in ("playing", "steal"):
        return

    user = message.from_user
    if not user:
        return

    text = normalize(message.text or "")
    if not text:
        return

    q_data = session.selected_questions[-1]
    q = q_data["question"]

    # Cek siapa yang boleh menjawab
    if session.phase == "steal":
        steal_team = "blue" if session.playing_team == "red" else "red"
        steal_players = session.team_blue if steal_team == "blue" else session.team_red
        answerer_idx = (
            session.answer_turn_blue if steal_team == "blue" else session.answer_turn_red
        ) % len(steal_players)
        answerer = steal_players[answerer_idx]
        if user.id != answerer["user_id"]:
            return
    else:
        answerer = session.current_answerer()
        if not answerer or user.id != answerer["user_id"]:
            return

    # Cek jawaban (dengan toleransi typo)
    matched = find_answer(message.text or "", q["answers"], session.answered)

    mention = f"@{user.username}" if user.username else user.first_name
    who = f"{user.first_name}" + (f" @{user.username}" if user.username else "")

    if matched:
        session.answered[matched["key"]] = who
        try:
            stats.record_answer(user.id, user.first_name, user.username or "", matched["points"])
        except Exception as e:
            print(f"[team stats] {e}")
        board = render_answers(q, session.answered)

        if session.phase == "steal":
            # Curi berhasil!
            steal_team = "blue" if session.playing_team == "red" else "red"
            pts = sum(a["points"] for a in q["answers"] if a["key"] in session.answered)
            if steal_team == "red":
                session.score_red += pts
            else:
                session.score_blue += pts

            await message.reply(
                f"✅ <b>{matched['label']}</b> — {matched['points']} poin\n"
                f"🎉 <b>CURI BERHASIL!</b> {mention}\n\n"
                f"{board}\n\n"
                f"{format_board_team(session)}"
            )
            await _next_team_question(client, chat_id)
            return

        # Jawaban benar mode normal — cek dulu apakah semua sudah terjawab
        all_answered = not session.remaining_answers
        session.advance_answerer()

        if all_answered:
            # Semua terjawab, poin ke tim bermain
            pts = sum(a["points"] for a in q["answers"])
            if session.playing_team == "red":
                session.score_red += pts
            else:
                session.score_blue += pts

            playing = "🔴 Tim Merah" if session.playing_team == "red" else "🔵 Tim Biru"
            await message.reply(
                f"✅ <b>{matched['label']}</b> — {matched['points']} poin\n"
                f"👤 {mention}\n\n{board}"
            )
            await client.send_message(
                chat_id,
                f"🎉 <b>{playing} menjawab semua!</b>\n"
                f"+{pts} poin\n\n{format_board_team(session)}"
            )
            await _next_team_question(client, chat_id)
        else:
            answerer_next = session.current_answerer()
            next_mention = (
                f"@{answerer_next['username']}" if answerer_next and answerer_next.get("username")
                else (answerer_next["name"] if answerer_next else "?")
            )
            await message.reply(
                f"✅ <b>{matched['label']}</b> — {matched['points']} poin\n"
                f"👤 {mention}\n\n"
                f"{board}\n\n"
                f"➡️ Giliran: {next_mention}"
            )

    else:
        # Jawaban salah
        if session.phase == "steal":
            # Gagal curi — poin tetap ke tim yang bermain
            pts = sum(a["points"] for a in q["answers"] if a["key"] in session.answered)
            if session.playing_team == "red":
                session.score_red += pts
            else:
                session.score_blue += pts

            playing = "🔴 Tim Merah" if session.playing_team == "red" else "🔵 Tim Biru"
            board = render_answers(q, session.answered)
            await message.reply(
                f"❌ Jawaban salah! Gagal mencuri.\n"
                f"Poin tetap ke <b>{playing}</b>: +{pts}\n\n"
                f"{board}\n\n{format_board_team(session)}"
            )
            await _next_team_question(client, chat_id)
            return

        session.wrong_count += 1
        session.advance_answerer()
        await message.reply(f"❌ Salah! ({session.wrong_count}/3)")

        if session.wrong_count >= 3:
            session.phase = "steal"
            steal_team = "blue" if session.playing_team == "red" else "red"
            steal_players = session.team_blue if steal_team == "blue" else session.team_red
            answerer_idx = (
                session.answer_turn_blue if steal_team == "blue" else session.answer_turn_red
            ) % len(steal_players)
            steal_answerer = steal_players[answerer_idx]
            steal_mention = (
                f"@{steal_answerer['username']}" if steal_answerer.get("username")
                else steal_answerer["name"]
            )
            steal_label = "🔵 Tim Biru" if steal_team == "blue" else "🔴 Tim Merah"

            board = render_answers(q, session.answered)
            await client.send_message(
                chat_id,
                f"💥 <b>3 kali salah!</b>\n\n"
                f"<b>{steal_label}</b> berhak mencuri!\n"
                f"Penjawab: {steal_mention}\n\n"
                f"{board}\n\n"
                f"<i>1 kesempatan menjawab!</i>"
            )
        else:
            answerer = session.current_answerer()
            answerer_mention = (
                f"@{answerer['username']}" if answerer and answerer.get("username")
                else answerer["name"]
            )
            await client.send_message(
                chat_id,
                f"Giliran: {answerer_mention}\n❌ Kesalahan: {session.wrong_count}/3"
            )


async def _next_team_question(client, chat_id: int):
    session: TeamSession = game_state.get(chat_id)
    if not session:
        return

    session.current_q_idx += 1
    session.answered = {}
    session.wrong_count = 0
    session.steal_chance = False
    session.phase = "pick_category"

    # Ganti tim yang memilih kategori berikutnya
    session.choosing_team = "blue" if session.playing_team == "red" else "red"
    session.playing_team = session.choosing_team

    await asyncio.sleep(2)

    if session.current_q_idx >= 6:
        await end_team_game(client, chat_id)
    else:
        await show_category_picker(client, chat_id)


async def end_team_game(client, chat_id: int):
    session: TeamSession = game_state.get(chat_id)
    if not session:
        return

    session.active = False
    board = format_board_team(session)

    if session.score_red > session.score_blue:
        winner = "🔴 Tim Merah"
        winner_players = session.team_red
    elif session.score_blue > session.score_red:
        winner = "🔵 Tim Biru"
        winner_players = session.team_blue
    else:
        winner = "Seri"
        winner_players = []

    winner_list = ""
    if winner_players:
        winner_list = "\n".join(
            f"  {i+1}. {p['name']}" + (f" (@{p['username']})" if p.get("username") else "")
            for i, p in enumerate(winner_players)
        )

    # Statistik: game dimainkan (semua) + kemenangan (tim pemenang)
    try:
        stats.record_games(session.team_red + session.team_blue)
        if winner_players:
            stats.record_wins([p["user_id"] for p in winner_players])
    except Exception as e:
        print(f"[end_team_game] stats: {e}")

    try:
        await client.send_message(
            chat_id,
            f"🏆 <b>Game Tim Selesai!</b>\n\n"
            f"{board}\n\n"
            f"{'🎉 Pemenang: <b>' + winner + '</b>' if winner != 'Seri' else '🤝 <b>Hasil Seri!</b>'}\n"
            + (f"\n{winner_list}" if winner_list else "")
        )
    except Exception as e:
        print(f"[end_team_game] Gagal kirim hasil: {e}")
    finally:
        game_state.remove(chat_id)
