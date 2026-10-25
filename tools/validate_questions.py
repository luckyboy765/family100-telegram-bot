"""
Validator bank soal Family 100. Jalankan sebelum deploy:
    python tools/validate_questions.py
Exit code != 0 bila ada masalah.
"""
import json
import os
import sys

PATH = os.path.join(os.path.dirname(__file__), "..", "family100_questions.json")


def validate(path: str = PATH) -> list:
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)

    errors = []
    seen_q = set()
    for i, q in enumerate(data):
        qid = q.get("id", f"#{i}")
        if not q.get("question"):
            errors.append(f"{qid}: pertanyaan kosong")
        if not q.get("category"):
            errors.append(f"{qid}: kategori kosong")
        ql = (q.get("question") or "").strip().lower()
        if ql in seen_q:
            errors.append(f"{qid}: pertanyaan duplikat")
        seen_q.add(ql)

        answers = q.get("answers") or []
        if len(answers) < 5:
            errors.append(f"{qid}: hanya {len(answers)} jawaban (min 5)")

        keys, labels, prev = set(), set(), None
        for a in answers:
            if not a.get("label", "").strip():
                errors.append(f"{qid}: ada label kosong")
            k = a.get("key", "")
            if not k:
                errors.append(f"{qid}: ada key kosong")
            if k in keys:
                errors.append(f"{qid}: key duplikat '{k}'")
            keys.add(k)
            lab = a.get("label", "").strip().lower()
            if lab in labels:
                errors.append(f"{qid}: label duplikat '{lab}'")
            labels.add(lab)
            pts = a.get("points")
            if not isinstance(pts, int) or pts <= 0:
                errors.append(f"{qid}: poin tidak valid ({pts})")
            elif prev is not None and pts > prev:
                errors.append(f"{qid}: poin tidak menurun ({prev} -> {pts})")
            prev = pts
            # alt_key tidak boleh sama dengan key
            for alt in a.get("alt_keys", []) or []:
                if alt.lower().replace(" ", "") == k:
                    errors.append(f"{qid}: alt_key sama dengan key '{k}'")
    return errors


if __name__ == "__main__":
    errs = validate()
    if errs:
        print(f"[FAIL] {len(errs)} masalah ditemukan:")
        for e in errs[:50]:
            print("  -", e)
        sys.exit(1)
    print("[OK] Semua soal valid.")
