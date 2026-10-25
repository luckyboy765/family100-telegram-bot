"""
Handler /new — tampilkan pilihan mode game.
"""
from pyrogram import Client, filters
from pyrogram.types import Message

import game_state
from helpers import ikb


async def cmd_new(client: Client, message: Message):
    chat_id = message.chat.id

    # Cegah double game
    if game_state.get(chat_id):
        await message.reply("⚠️ Sudah ada game yang sedang berjalan di grup ini!\nKetik /stop untuk menghentikannya.")
        return

    text = (
        "🎮 <b>Family 100 — Pilih Mode Permainan</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>Mode Solo — Siapa Cepat</b>\n"
        "• 5 soal acak, setiap soal berdurasi <b>2 menit</b>\n"
        "• Siapa yang paling cepat menjawab mendapat poin\n"
        "• Total poin dihitung di akhir permainan\n\n"
        "👥 <b>Mode Tim — 5 vs 5</b>\n"
        "• Dibagi 2 tim: 🔴 Merah & 🔵 Biru (maks 5 orang/tim, min 1 orang/tim)\n"
        "• Jumlah pemain antar tim tidak harus sama (bisa 1v2, 2v3, dll)\n"
        "• 12 kategori tersedia, pilih 6 soal untuk dimainkan\n"
        "• Menjawab bergantian sesuai urutan bergabung\n"
        "• Salah 3x → tim lawan berhak <b>mencuri</b> poin!\n"
        "• Tim dengan poin terbanyak menang\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    markup = ikb([
        [("⚡ Mode Solo", "f100:mode:solo"), ("👥 Mode Tim", "f100:mode:team")],
        [("❌ Batal", "f100:cancel")],
    ])

    await message.reply(text, reply_markup=markup)
