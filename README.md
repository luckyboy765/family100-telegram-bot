# Family 100 Telegram Bot

A quiz game bot for Telegram groups, based on the TV game show format:
"We surveyed 100 people..." Players guess the most popular answers.

Built with **Python and Pyrogram**.

## Features

- **3,776 questions in 42 categories** (`family100_questions.json`)
- **Solo mode, fastest wins**: anyone in the group can answer, 2 minutes per
  question, hints at 60s (word length) and 90s (first letter), speed and
  streak bonuses
- **Team mode, 5 vs 5**: lobby with join buttons, category picker,
  play-or-pass rounds, turn-based answering between teams
- Fuzzy answer matching with alternative answers per item
- Leaderboards and personal stats
- Games survive a restart: active games are saved and cleaned up on boot
- Admin tools: broadcast to all groups, daily backup to a log group, reload
  questions without restarting

## Commands

| Command | Action |
|---|---|
| `/new` | Start a game, choose Solo or Team |
| `/stop` | Stop the current game |
| `/leaderboard` | Top players (`/lb`, `/peringkat`) |
| `/stats` | Personal stats |
| `/help` | How to play |
| `/broadcast`, `/backup`, `/reload` | Owner only |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # fill API_ID, API_HASH, BOT_TOKEN, OWNER_ID
python main.py
```

## Question data

Each question looks like this:

```json
{"id": 1, "category": "...", "question": "...", "answers": [...]}
```

`tools/validate_questions.py` checks the file for duplicates and broken
entries, and `tests/test_questions.py` runs the same checks as tests.

## Project structure

```
main.py              entry point and routing
handlers/new_game.py mode picker
handlers/solo_mode.py solo game flow, hints, timers, bonuses
handlers/team_mode.py lobby, categories, rounds, team answers
handlers/admin.py    /start, broadcast, backups
game_state.py        active games, persisted across restarts
questions.py         loading and answer matching
stats.py             scores and leaderboards
```
