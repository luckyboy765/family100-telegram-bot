"""
Statistik & leaderboard persisten (SQLite).
Menyimpan poin kumulatif, jumlah jawaban benar, game dimainkan, dan kemenangan.
"""
import os
import sqlite3
from datetime import datetime
from contextlib import closing

_DB_PATH = os.path.join(os.path.dirname(__file__), "family100_stats.db")


def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with closing(_conn()) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                user_id   INTEGER PRIMARY KEY,
                name      TEXT,
                username  TEXT,
                points    INTEGER DEFAULT 0,
                correct   INTEGER DEFAULT 0,
                games     INTEGER DEFAULT 0,
                wins      INTEGER DEFAULT 0,
                updated   TEXT
            );
            CREATE TABLE IF NOT EXISTS weekly (
                week     TEXT,
                user_id  INTEGER,
                name     TEXT,
                username TEXT,
                points   INTEGER DEFAULT 0,
                PRIMARY KEY (week, user_id)
            );
            """
        )
        c.commit()


def _week() -> str:
    return datetime.now().strftime("%G-W%V")


def record_answer(user_id: int, name: str, username: str, points: int):
    """Catat 1 jawaban benar + poinnya."""
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_conn()) as c:
        c.execute(
            """INSERT INTO players (user_id, name, username, points, correct, updated)
               VALUES (?,?,?,?,1,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 points=points+excluded.points, correct=correct+1,
                 name=excluded.name, username=excluded.username, updated=excluded.updated""",
            (user_id, name, username, points, now),
        )
        c.execute(
            """INSERT INTO weekly (week, user_id, name, username, points)
               VALUES (?,?,?,?,?)
               ON CONFLICT(week, user_id) DO UPDATE SET
                 points=points+excluded.points, name=excluded.name, username=excluded.username""",
            (_week(), user_id, name, username, points),
        )
        c.commit()


def record_games(players: list):
    """players: list of {'user_id','name','username'} — tambah 1 game dimainkan."""
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_conn()) as c:
        for p in players:
            c.execute(
                """INSERT INTO players (user_id, name, username, games, updated)
                   VALUES (?,?,?,1,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     games=games+1, name=excluded.name, username=excluded.username, updated=excluded.updated""",
                (p["user_id"], p.get("name", ""), p.get("username", ""), now),
            )
        c.commit()


def record_wins(user_ids: list):
    with closing(_conn()) as c:
        for uid in user_ids:
            c.execute("UPDATE players SET wins=wins+1 WHERE user_id=?", (uid,))
        c.commit()


def top_global(n: int = 10) -> list:
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM players ORDER BY points DESC, correct DESC LIMIT ?", (n,)
        )]


def top_weekly(n: int = 10) -> list:
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM weekly WHERE week=? ORDER BY points DESC LIMIT ?", (_week(), n)
        )]


def user_stats(user_id: int):
    with closing(_conn()) as c:
        r = c.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
        return dict(r) if r else None


def _fmt_rows(rows: list) -> str:
    if not rows:
        return "Belum ada data."
    out = []
    for i, r in enumerate(rows, 1):
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        name = (r.get("name") or "Pemain").replace("<", "&lt;").replace(">", "&gt;")
        uname = f" (@{r['username']})" if r.get("username") else ""
        out.append(f"{medal} {name}{uname} — <b>{r['points']}</b>")
    return "\n".join(out)


def format_leaderboard(kind: str = "global", n: int = 10) -> str:
    if kind == "weekly":
        return "📅 <b>Leaderboard Mingguan</b>\n\n" + _fmt_rows(top_weekly(n))
    return "🏆 <b>Leaderboard Global</b>\n\n" + _fmt_rows(top_global(n))
