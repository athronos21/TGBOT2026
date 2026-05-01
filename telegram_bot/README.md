# 📅 IT Department Schedule Management Bot
**Haramaya University — Information Technology Department**

A Telegram bot that lets the Department Head manage courses, rooms, and automatically generate a conflict-free, fair weekly timetable.

---

## Features

| Feature | Description |
|---|---|
| Add courses | Name, credit hours, lab/classroom, batch, semester |
| Add rooms & labs | Name, type, optional capacity |
| Auto-schedule | Greedy algorithm — labs first, then classrooms |
| Fairness | Morning/afternoon slots balanced per section |
| View schedule | Filtered by batch, section, semester |
| Export to Excel | Colour-coded `.xlsx` timetable |
| Admin-only | Only the Department Head can use the bot |

---

## Quick Start

### 1. Get a Bot Token
Talk to [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token.

### 2. Get your Telegram User ID
Talk to [@userinfobot](https://t.me/userinfobot) → copy your numeric ID.

### 3. Setup

```bash
cd telegram_bot
bash scripts/setup.sh
# Edit .env with your BOT_TOKEN, ADMIN_TELEGRAM_ID, and DB credentials
```

### 4. Start PostgreSQL

```bash
docker-compose up -d db
```

### 5. Run the bot

```bash
source venv/bin/activate
python -m src.main
```

### 6. Initialize time slots (once)

In Telegram, send `/seed_slots` to your bot.

---

## Bot Commands

```
/start              — Show help
/seed_slots         — Initialize Mon–Fri 08:00–17:00 time slots (run once)

/add_course         — Add a course (guided conversation)
/add_room           — Add a classroom
/add_lab            — Add a lab room
/list_courses       — List all courses
/list_rooms         — List all rooms & labs

/generate_schedule  — Run the scheduling algorithm
/view_schedule      — View timetable (filter by batch/section/semester)
/export_schedule    — Download timetable as Excel file
/reset_schedule     — Clear the current timetable

/delete_course      — Remove a course by ID
/delete_room        — Remove a room by ID
/cancel             — Cancel any ongoing conversation
```

---

## Typical Workflow

```
1. /seed_slots          ← do this once
2. /add_lab             ← add all lab rooms
3. /add_room            ← add all classrooms
4. /add_course          ← add all courses (repeat for each)
5. /generate_schedule   ← auto-generate timetable
6. /view_schedule       ← review it
7. /export_schedule     ← download Excel file
```

---

## Scheduling Algorithm

1. **Labs first** — lab rooms are scarce; assigned before classrooms
2. **Batch priority** — 4th year → 3rd year → 2nd year
3. **Sections** — each course is scheduled for Section A and Section B independently
4. **Credit hours** = sessions per week (e.g. 3 credit hours → 3 slots/week)
5. **Fairness** — morning/afternoon slots are balanced per section
6. **Conflict rules** — no room or section is double-booked

---

## Project Structure

```
telegram_bot/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Settings
│   ├── database/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── db.py            # DB session management
│   ├── scheduler/
│   │   ├── engine.py        # Greedy scheduling algorithm
│   │   └── constraints.py   # Conflict & fairness tracking
│   └── bot/
│       ├── handlers.py      # Telegram conversation handlers
│       └── commands.py      # DB query helpers
├── utils/
│   └── export.py            # Excel export
├── scripts/
│   └── setup.sh
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Docker (Full Stack)

```bash
cp .env.example .env
# fill in .env
docker-compose up --build
```

---

## Tech Stack

- **Python 3.11**
- **python-telegram-bot 20.x** (async)
- **PostgreSQL 16**
- **SQLAlchemy 2.x**
- **openpyxl** (Excel export)
