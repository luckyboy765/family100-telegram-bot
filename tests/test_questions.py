"""
Unit test pencocokan jawaban + validasi bank soal.
Jalankan: python tests/test_questions.py   (atau: pytest)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import questions as Q  # noqa: E402
from tools.validate_questions import validate  # noqa: E402


def _ans(key, alts=None, label=None, points=30):
    return {"rank": 1, "key": key, "label": label or key.title(),
            "points": points, "alt_keys": alts or []}


def test_normalize():
    assert Q.normalize("Nasi Goreng!") == "nasigoreng"
    assert Q.normalize("  APEL. ") == "apel"


def test_exact_and_alt():
    a = _ans("apel", ["apple"])
    assert Q.match_answer("apel", a)
    assert Q.match_answer("APPLE", a)
    assert Q.match_answer("apple!", a)
    assert not Q.match_answer("mangga", a)


def test_fuzzy_typo():
    a = _ans("jerapah")
    assert Q.match_answer("jerapa", a)      # 1 huruf hilang
    assert Q.match_answer("jerafah", a)     # 1 huruf beda
    b = _ans("stroberi")
    assert Q.match_answer("stroberri", b)


def test_short_word_strict():
    a = _ans("tuna")                        # 4 huruf -> wajib persis
    assert Q.match_answer("tuna", a)
    assert not Q.match_answer("tunu", a)


def test_find_answer_skips_answered():
    answers = [_ans("apel", ["apple"]), _ans("jeruk", ["orange"], points=25)]
    m = Q.find_answer("apel", answers, answered_keys={"apel"})
    assert m is None                        # sudah terjawab
    m = Q.find_answer("jerukk", answers, answered_keys={"apel"})
    assert m and m["key"] == "jeruk"


def test_bank_valid():
    errs = validate()
    assert errs == [], f"{len(errs)} soal bermasalah: {errs[:5]}"


def test_bank_size():
    assert len(Q.QUESTIONS) >= 3000


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} lulus.")
    sys.exit(1 if failed else 0)
