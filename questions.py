"""
Loader soal Family 100 dari JSON + pencocokan jawaban (dengan toleransi typo).
"""
import json
import random
import os
import re
from collections import deque
from difflib import SequenceMatcher

_DATA_PATH = os.path.join(os.path.dirname(__file__), "family100_questions.json")


def _load() -> list:
    with open(_DATA_PATH, encoding="utf-8-sig") as f:
        raw = json.load(f)
    return raw if isinstance(raw, list) else raw.get("questions", [])


QUESTIONS: list = _load()


def reload_questions() -> int:
    """Muat ulang bank soal dari file (dipakai command admin /reload)."""
    global QUESTIONS
    QUESTIONS = _load()
    return len(QUESTIONS)


# ─── Anti soal berulang (per chat) ────────────────────────────────────────────
_RECENT: dict = {}          # chat_id -> deque(id soal yang baru dipakai)
_RECENT_MAX = 300           # jangan ulang soal selama 300 pemakaian terakhir


def _recent(chat_id: int) -> deque:
    dq = _RECENT.get(chat_id)
    if dq is None:
        dq = deque(maxlen=_RECENT_MAX)
        _RECENT[chat_id] = dq
    return dq


def _mark_used(chat_id: int, questions: list):
    dq = _recent(chat_id)
    for q in questions:
        # item bisa berupa soal langsung, atau dibungkus {category, question: {..}}
        inner = q.get("question")
        target = inner if isinstance(inner, dict) else q
        qid = target.get("id")
        if qid is not None:
            dq.append(qid)


def get_random_questions(n: int = 5, chat_id: int = 0) -> list:
    """Ambil n soal acak, hindari yang baru saja dipakai di chat ini."""
    used = set(_recent(chat_id)) if chat_id else set()
    pool = [q for q in QUESTIONS if q.get("id") not in used]
    if len(pool) < n:                       # cadangan bila hampir semua terpakai
        pool = QUESTIONS
    picked = random.sample(pool, min(n, len(pool)))
    if chat_id:
        _mark_used(chat_id, picked)
    return picked


def get_categories(n: int = 12, chat_id: int = 0) -> list:
    """Ambil n kategori unik acak beserta 1 soal (hindari soal yang baru dipakai)."""
    used = set(_recent(chat_id)) if chat_id else set()
    by_cat: dict = {}
    for q in QUESTIONS:
        by_cat.setdefault(q["category"], []).append(q)

    cats = list(by_cat.keys())
    selected_cats = random.sample(cats, min(n, len(cats)))

    result = []
    for cat in selected_cats:
        fresh = [q for q in by_cat[cat] if q.get("id") not in used] or by_cat[cat]
        q = random.choice(fresh)
        result.append({"category": cat, "question": q})
    if chat_id:
        _mark_used(chat_id, result)
    return result


# ─── Normalisasi & pencocokan jawaban ─────────────────────────────────────────
def normalize(text: str) -> str:
    """Normalisasi jawaban: lowercase, buang tanda baca & spasi."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]", "", text)   # hapus spasi, tanda baca, dsb.
    return text


def _fuzzy_threshold(length: int) -> float:
    if length < 5:
        return 1.0          # kata pendek: wajib persis (hindari salah cocok)
    if length <= 6:
        return 0.84
    return 0.80


def match_answer(text: str, answer: dict) -> bool:
    """Cek satu jawaban: cocok persis ATAU mirip (typo) dengan key/alt_keys."""
    n = normalize(text)
    if not n:
        return False
    cands = [answer["key"]] + [normalize(a) for a in answer.get("alt_keys", [])]
    for c in cands:
        if not c:
            continue
        if n == c:
            return True
        thr = _fuzzy_threshold(min(len(n), len(c)))
        if thr < 1.0 and SequenceMatcher(None, n, c).ratio() >= thr:
            return True
    return False


def find_answer(text: str, answers: list, answered_keys):
    """
    Cari jawaban yang cocok dari daftar answers, lewati yang sudah terjawab.
    Prioritas: cocok persis dulu, baru cocok mirip (typo) terbaik.
    """
    n = normalize(text)
    if not n:
        return None
    answered = set(answered_keys)

    # 1) pass cocok persis (key / alt_keys)
    for a in answers:
        if a["key"] in answered:
            continue
        cands = [a["key"]] + [normalize(x) for x in a.get("alt_keys", [])]
        if any(n == c for c in cands if c):
            return a

    # 2) pass cocok mirip (ambil ratio tertinggi di atas ambang)
    best, best_r = None, 0.0
    for a in answers:
        if a["key"] in answered:
            continue
        cands = [a["key"]] + [normalize(x) for x in a.get("alt_keys", [])]
        for c in cands:
            if not c or len(c) < 5 or len(n) < 5:
                continue
            r = SequenceMatcher(None, n, c).ratio()
            if r > best_r and r >= _fuzzy_threshold(min(len(n), len(c))):
                best, best_r = a, r
    return best
