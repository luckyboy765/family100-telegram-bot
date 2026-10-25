"""
Helper fungsi untuk format pesan dan keyboard.
"""
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def ikb(rows: list) -> InlineKeyboardMarkup:
    """Buat InlineKeyboardMarkup dari list of list of (text, callback_data)."""
    buttons = []
    for row in rows:
        btn_row = []
        for item in row:
            if len(item) == 2:
                btn_row.append(InlineKeyboardButton(item[0], callback_data=item[1]))
            elif len(item) == 3 and item[2] == "url":
                btn_row.append(InlineKeyboardButton(item[0], url=item[1]))
        buttons.append(btn_row)
    return InlineKeyboardMarkup(buttons)


def format_scoreboard_solo(scores: dict) -> str:
    """Format papan skor mode solo."""
    if not scores:
        return "🏆 <b>Papan Skor Akhir</b>\n\nTidak ada poin — belum ada yang menjawab benar."
    sorted_players = sorted(scores.items(), key=lambda x: x[1]["points"], reverse=True)
    lines = ["🏆 <b>Papan Skor Akhir</b>\n"]
    for i, (uid, data) in enumerate(sorted_players, 1):
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        uname = f"@{data['username']}" if data.get("username") else ""
        name = data['name'].replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"{medal} {name} {uname} — <b>{data['points']} poin</b>")
    return "\n".join(lines)

def format_board_team(session) -> str:
    """Format papan skor mode tim."""
    red_names = ", ".join(
        f"{p['name']}" + (f" (@{p['username']})" if p.get("username") else "")
        for p in session.team_red
    ) or "Kosong"
    blue_names = ", ".join(
        f"{p['name']}" + (f" (@{p['username']})" if p.get("username") else "")
        for p in session.team_blue
    ) or "Kosong"

    return (
        f"🔴 <b>Tim Merah</b> — {session.score_red} poin\n"
        f"   {red_names}\n\n"
        f"🔵 <b>Tim Biru</b> — {session.score_blue} poin\n"
        f"   {blue_names}"
    )


def _mask(label: str, reveal_first: bool) -> str:
    """Bikin pola hint: jumlah huruf (+ huruf pertama bila reveal_first)."""
    out = []
    first = True
    for ch in label:
        if ch == " ":
            out.append("  ")
            first = True
            continue
        if reveal_first and first:
            out.append(ch.upper())
        else:
            out.append("_")
        first = False
    return " ".join(out)


def render_answers(question: dict, answered: dict, hint: int = 0) -> str:
    """Tampilkan slot jawaban (terbuka/tertutup). answered = {key: "nama penjawab"}
    hint: 0 = tanpa bantuan, 1 = tampilkan jumlah huruf, 2 = + huruf pertama."""
    lines = []
    for a in question["answers"]:
        if a["key"] in answered:
            who = answered[a["key"]].replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"✅ {a['rank']}. {a['label']} — <b>{a['points']} poin</b> <i>({who})</i>")
        elif hint >= 1:
            pattern = _mask(a["label"], reveal_first=(hint >= 2))
            lines.append(f"❓ {a['rank']}. <code>{pattern}</code> ({a['points']})")
        else:
            lines.append(f"❓ {a['rank']}. ___________")
    return "\n".join(lines)
