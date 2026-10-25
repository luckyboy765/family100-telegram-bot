"""
Model data untuk session game Family 100.
"""
from dataclasses import dataclass, field
from typing import Optional


# ─── Mode Solo (siapa cepat) ─────────────────────────────────────────────────

@dataclass
class SoloSession:
    mode: str = "solo"
    chat_id: int = 0
    questions: list = field(default_factory=list)   # list soal yang akan dimainkan
    current_idx: int = 0                             # index soal sekarang
    answered: dict = field(default_factory=dict)    # {key: "nama penjawab"}
    scores: dict = field(default_factory=dict)      # {user_id: {"name": str, "username": str, "points": int}}
    timer_task = None                                # asyncio Task untuk timer 2 menit
    hint_task = None                                 # asyncio Task untuk hint bertahap
    q_start: float = 0.0                             # waktu (monotonic) soal ditampilkan
    hint_level: int = 0                              # 0/1/2 tingkat bantuan soal aktif
    streaks: dict = field(default_factory=dict)      # {user_id: beruntun benar}
    last_scorer: int = 0                             # user_id terakhir yang benar (untuk streak)
    active: bool = True

    @property
    def current_question(self) -> Optional[dict]:
        if self.current_idx < len(self.questions):
            return self.questions[self.current_idx]
        return None

    @property
    def remaining_answers(self) -> list:
        if not self.current_question:
            return []
        return [a for a in self.current_question["answers"]
                if a["key"] not in self.answered]


# ─── Mode Tim ─────────────────────────────────────────────────────────────────

@dataclass
class TeamSession:
    mode: str = "team"
    chat_id: int = 0

    # Anggota tim: list of {"user_id", "name", "username"}
    team_red: list = field(default_factory=list)
    team_blue: list = field(default_factory=list)

    # State lobby
    lobby_open: bool = True
    lobby_msg_id: int = 0

    # Daftar 12 kategori yang tersedia (dipilih dari pool)
    categories: list = field(default_factory=list)   # [{"category": str, "question": dict}]
    # 6 soal yang sudah dipilih
    selected_questions: list = field(default_factory=list)

    # Giliran bermain: "red" | "blue"
    playing_team: str = ""
    # Tim mana yang giliran memilih kategori
    choosing_team: str = ""
    # Index giliran pilih dalam round
    round_pick_idx: int = 0

    # Soal aktif
    current_q_idx: int = 0
    answered: dict = field(default_factory=dict)     # {key: "nama penjawab"}
    wrong_count: int = 0                             # kesalahan tim yang bermain
    steal_chance: bool = False                       # apakah tim lawan punya kesempatan curi

    # Skor tim
    score_red: int = 0
    score_blue: int = 0

    # Index giliran menjawab dalam tim (bergantian sesuai urutan join)
    answer_turn_red: int = 0
    answer_turn_blue: int = 0

    timer_task = None
    active: bool = True
    phase: str = "lobby"   # lobby | pick_team | pick_category | playing | steal | done

    @property
    def current_question(self) -> Optional[dict]:
        if self.current_q_idx < len(self.selected_questions):
            return self.selected_questions[self.current_q_idx]
        return None

    @property
    def remaining_answers(self) -> list:
        if not self.current_question:
            return []
        # selected_questions menyimpan {"category": ..., "question": {...}}
        q = self.current_question.get("question", self.current_question)
        return [a for a in q["answers"] if a["key"] not in self.answered]

    def current_answerer(self) -> Optional[dict]:
        """Pemain yang sekarang giliran menjawab."""
        if self.playing_team == "red":
            if not self.team_red:
                return None
            idx = self.answer_turn_red % len(self.team_red)
            return self.team_red[idx]
        else:
            if not self.team_blue:
                return None
            idx = self.answer_turn_blue % len(self.team_blue)
            return self.team_blue[idx]

    def advance_answerer(self):
        if self.playing_team == "red":
            self.answer_turn_red += 1
        else:
            self.answer_turn_blue += 1
