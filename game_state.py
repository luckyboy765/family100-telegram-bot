"""
Manajemen state semua game Family 100 yang sedang berjalan.
Key = chat_id (int). Daftar chat aktif dipersist ke disk supaya bila bot
restart di tengah game, chat terkait bisa diberi tahu (game tak mati diam-diam).
"""
import os
import json

games: dict = {}  # chat_id -> GameSession

_ACTIVE_FILE = os.path.join(os.path.dirname(__file__), "active_games.json")


def _save_active():
    try:
        with open(_ACTIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(games.keys()), f)
    except Exception as e:
        print(f"[game_state] gagal simpan active: {e}")


def get(chat_id: int):
    return games.get(chat_id)


def set(chat_id: int, session):
    games[chat_id] = session
    _save_active()


def remove(chat_id: int):
    games.pop(chat_id, None)
    _save_active()


def pop_stale_actives() -> list:
    """Ambil daftar chat yang tercatat aktif dari sesi sebelumnya, lalu bersihkan.
    Dipanggil sekali saat startup untuk memberi tahu game yang terputus."""
    if not os.path.exists(_ACTIVE_FILE):
        return []
    try:
        with open(_ACTIVE_FILE, encoding="utf-8") as f:
            ids = json.load(f)
    except Exception:
        ids = []
    try:
        os.remove(_ACTIVE_FILE)
    except OSError:
        pass
    return [int(x) for x in ids]
