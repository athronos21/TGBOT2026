"""
Telegram conversation handlers for the IT Schedule Management Bot.
All multi-step conversations use ConversationHandler with states.

Design principle: the Department Head selects everything via buttons.
Only course name and instructor name require free-text typing.
"""
import logging
from functools import wraps
from typing import List

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from src.config import ADMIN_TELEGRAM_ID, BATCHES, SEMESTERS, DEPARTMENTS
from src.database.db import get_session
from src.database import init_db
from src.bot.commands import (
    add_course,
    list_courses,
    delete_course,
    update_instructor,
    add_room,
    list_rooms,
    list_labs,
    delete_room,
    assign_lab_to_batch,
    remove_lab_assignment,
    get_lab_batch_assignments,
    seed_time_slots,
    clear_schedule,
    get_schedule,
    format_schedule_text,
    get_curriculum_semesters,
    get_curriculum_courses,
    search_curriculum,
    format_curriculum_text,
    get_admin_profile,
    set_admin_department,
)
from src.scheduler.engine import generate_schedule
import os

logger = logging.getLogger(__name__)

# ── Keyboard helpers ──────────────────────────────────────────────────────────

def _kb(buttons: List[List[str]], one_time: bool = True) -> ReplyKeyboardMarkup:
    """Shortcut: build a resize+one-time ReplyKeyboardMarkup from a 2-D list."""
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=one_time, resize_keyboard=True)


CREDIT_KB   = _kb([["1", "2"], ["3", "4"]])
TYPE_KB     = _kb([["📚 Class", "🔬 Lab"]])
BATCH_KB    = _kb([["2nd", "3rd", "4th"]])
SEMESTER_KB = _kb([["Semester 1", "Semester 2"]])
YESNO_KB    = _kb([["✅ Yes, add another", "🏁 Done, save all"]])
CONFIRM_KB  = _kb([["✅ Confirm & Save", "🔄 Start over"]])
SKIP_KB     = _kb([["⏭ Skip (TBA)"]])

# ── Conversation states ───────────────────────────────────────────────────────

# /add_course  &  /add_courses  (shared per-course steps)
(
    MC_NAME,        # type course name
    MC_CREDITS,     # select credit hours  1-4
    MC_INSTRUCTOR,  # type instructor name (or skip)
    MC_TYPE,        # select Class / Lab
    MC_BATCH,       # select 2nd / 3rd / 4th
    MC_SEMESTER,    # select Semester 1 / 2
    MC_ANOTHER,     # add another? Yes / Done
    MC_CONFIRM,     # review summary → Confirm or Start over
) = range(8)

# /add_room  /add_lab  — states defined inside the handler section below

# /view_schedule
VS_BATCH    = 10
VS_SECTION  = 11
VS_SEMESTER = 12

# /delete_course
DC_PICK = 13

# /delete_room
DR_PICK = 14

# /assign_instructor  (pick course via button, then type name)
AI_PICK = 15
AI_NAME = 16

# /assign_lab  (pick lab → toggle batches → confirm)
AL_PICK    = 19
AL_BATCHES = 20
AL_CONFIRM = 21

# /curriculum  (browse by year)
CUR_YEAR     = 22
CUR_SEMESTER = 23

# /search_course  (free-text search)
SC_QUERY = 24

# /start department selection
DEPT_PICK    = 25
DEPT_CONFIRM = 26

# /switch_department
SW_PICK    = 27
SW_CONFIRM = 28

MAX_COURSES = 10   # maximum subjects per session


# ── Auth decorator ────────────────────────────────────────────────────────────

def admin_only(func):
    """Restrict handler to the configured admin Telegram user."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if ADMIN_TELEGRAM_ID and user_id != ADMIN_TELEGRAM_ID:
            await update.message.reply_text(
                "⛔ Access denied. This bot is for the Department Head only."
            )
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def department_required(func):
    """
    Ensure the admin has selected a department before using any command.
    If not set, prompt them to run /start first.
    Must be applied AFTER @admin_only.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        with get_session() as session:
            profile = get_admin_profile(session, user_id)
            # Read the value while session is still open
            department = profile.department if profile else None
        if not department:
            await update.message.reply_text(
                "⚠️ You haven't selected your department yet.\n\n"
                "Please use /start to choose your department first.",
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END
        # Inject department into context for handlers that need it
        context.user_data["department"] = department
        return await func(update, context, *args, **kwargs)
    return wrapper


# ── /start ────────────────────────────────────────────────────────────────────

# ── Department keyboard ───────────────────────────────────────────────────────

def _dept_kb() -> ReplyKeyboardMarkup:
    """Build a keyboard from the DEPARTMENTS list (2 per row)."""
    rows = [DEPARTMENTS[i:i+2] for i in range(0, len(DEPARTMENTS), 2)]
    return _kb(rows)


# ── /start — department selection flow ───────────────────────────────────────
#
# Flow:
#   1. Check if department already set → show main menu
#      Otherwise → ask to pick department
#   2. Confirm selection
#   3. Save → show main menu
#

@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    with get_session() as session:
        profile = get_admin_profile(session, user.id)
        department = profile.department if profile else None

    if department:
        await _send_main_menu(update, department, user.first_name)
        return ConversationHandler.END

    # First time — must pick department
    await update.message.reply_text(
        f"👋 Welcome, *{user.first_name}*!\n\n"
        "Before you begin, please select your *department*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_dept_kb(),
    )
    return DEPT_PICK


async def dept_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in DEPARTMENTS:
        await update.message.reply_text(
            "Please tap one of the department buttons:",
            reply_markup=_dept_kb(),
        )
        return DEPT_PICK

    context.user_data["selected_dept"] = text
    await update.message.reply_text(
        f"You selected:\n\n🏛 *{text}*\n\nIs this correct?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([["✅ Yes, confirm", "🔄 Choose again"]]),
    )
    return DEPT_CONFIRM


async def dept_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "🔄 Choose again":
        await update.message.reply_text(
            "Select your department:",
            reply_markup=_dept_kb(),
        )
        return DEPT_PICK

    if text != "✅ Yes, confirm":
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=_kb([["✅ Yes, confirm", "🔄 Choose again"]]),
        )
        return DEPT_CONFIRM

    user = update.effective_user
    dept = context.user_data["selected_dept"]

    with get_session() as session:
        set_admin_department(session, user.id, dept, full_name=user.full_name)

    context.user_data.clear()
    await _send_main_menu(update, dept, user.first_name)
    return ConversationHandler.END


async def _send_main_menu(update: Update, department: str, first_name: str) -> None:
    """Send the main command menu, showing the active department."""
    await update.message.reply_text(
        f"👋 *Welcome, {first_name}!*\n"
        f"🏛 Department: *{department}*\n\n"
        "*Commands:*\n"
        "📚 `/add_courses` — Add up to 10 courses\n"
        "🏫 `/add_room` — Add a classroom\n"
        "🔬 `/add_lab` — Add a lab room\n"
        "📋 `/list_courses` — List all courses\n"
        "🏢 `/list_rooms` — List all rooms & labs\n"
        "👤 `/assign_instructor` — Assign instructor to a course\n"
        "🔬 `/assign_lab` — Assign a lab to a batch\n"
        "📊 `/list_lab_assignments` — View lab → batch assignments\n"
        "⚙️ `/generate_schedule` — Generate the timetable\n"
        "📅 `/view_schedule` — View the timetable\n"
        "📊 `/export_schedule` — Download schedule as Excel\n"
        "🗑️ `/reset_schedule` — Clear the timetable\n"
        "❌ `/delete_course` — Remove a course\n"
        "❌ `/delete_room` — Remove a room\n"
        "🕐 `/seed_slots` — Initialize time slots _(run once)_\n\n"
        "📖 *Curriculum:*\n"
        "📗 `/curriculum` — Browse curriculum by year/semester\n"
        "🔍 `/search_course` — Search curriculum by name or code\n\n"
        "🔄 `/switch_department` — Change your department\n\n"
        "ℹ️ Credit hours: *1 – 4*  |  Instructor defaults to *TBA*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )


# ── /switch_department ────────────────────────────────────────────────────────

@admin_only
async def sw_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    with get_session() as session:
        profile = get_admin_profile(session, user.id)
        current = profile.department if profile else "None"

    await update.message.reply_text(
        f"🔄 *Switch Department*\n\nCurrent: *{current}*\n\nSelect your new department:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_dept_kb(),
    )
    return SW_PICK


async def sw_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in DEPARTMENTS:
        await update.message.reply_text(
            "Please tap one of the department buttons:",
            reply_markup=_dept_kb(),
        )
        return SW_PICK

    context.user_data["selected_dept"] = text
    await update.message.reply_text(
        f"Switch to:\n\n🏛 *{text}*\n\nConfirm?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([["✅ Yes, switch", "❌ Cancel"]]),
    )
    return SW_CONFIRM


async def sw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text(
            "Cancelled. Department unchanged.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if text != "✅ Yes, switch":
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=_kb([["✅ Yes, switch", "❌ Cancel"]]),
        )
        return SW_CONFIRM

    user = update.effective_user
    dept = context.user_data["selected_dept"]

    with get_session() as session:
        set_admin_department(session, user.id, dept, full_name=user.full_name)

    context.user_data.clear()
    await update.message.reply_text(
        f"✅ Department updated to *{dept}*.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── /seed_slots ───────────────────────────────────────────────────────────────

@admin_only
@department_required
async def cmd_seed_slots(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        added = seed_time_slots(session)
    if added:
        await update.message.reply_text(f"✅ Added {added} time slots (Mon–Fri, 08:00–17:00).")
    else:
        await update.message.reply_text("ℹ️ Time slots already exist.")


# ── /add_courses  (button-driven, 1–10 courses per session) ──────────────────
#
# Flow per course:
#   1. Type course name
#   2. Select credit hours  [1][2][3][4]
#   3. Type instructor name  (or tap ⏭ Skip → TBA)
#   4. Select type           [📚 Class][🔬 Lab]
#   5. Select batch          [2nd][3rd][4th]
#   6. Select semester       [Semester 1][Semester 2]
#   7. Add another?          [✅ Yes, add another][🏁 Done, save all]
#      → if Yes and count < 10: loop back to step 1
#      → if Done or count == 10: show summary → [✅ Confirm & Save][🔄 Start over]
#   8. Confirm → save all to DB and show results
#

def _course_progress(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return a short progress header like  📝 Course 2 / 10"""
    done = len(context.user_data.get("mc_courses", []))
    return f"📝 *Course {done + 1}* of up to {MAX_COURSES}"


def _summary_text(courses: list) -> str:
    """Build a readable summary of all staged courses."""
    if not courses:
        return "_No courses staged yet._"
    lines = [f"*{len(courses)} course(s) ready to save:*\n"]
    for i, c in enumerate(courses, 1):
        kind = "🔬 Lab" if c["is_lab"] else "📚 Class"
        lines.append(
            f"  *{i}.* {c['name']}\n"
            f"       {c['credit_hours']}cr | {kind} | "
            f"{c['batch']} yr | Sem {c['semester']} | 👤 {c['instructor']}"
        )
    return "\n".join(lines)


@admin_only
@department_required
async def mc_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point — reset state and ask for first course name."""
    context.user_data.clear()
    context.user_data["mc_courses"] = []
    await update.message.reply_text(
        "📚 *Add Courses* _(up to 10)_\n\n"
        f"{_course_progress(context)}\n\n"
        "✏️ Type the *course name*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return MC_NAME


async def mc_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Course name cannot be empty. Please type it:")
        return MC_NAME
    context.user_data["mc_current"] = {"name": name}
    await update.message.reply_text(
        f"*{name}*\n\nSelect *credit hours*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=CREDIT_KB,
    )
    return MC_CREDITS


async def mc_credits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in ("1", "2", "3", "4"):
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=CREDIT_KB,
        )
        return MC_CREDITS
    context.user_data["mc_current"]["credit_hours"] = int(text)
    name = context.user_data["mc_current"]["name"]
    await update.message.reply_text(
        f"*{name}*\n\n"
        "👤 Type the *instructor's name*, or tap ⏭ Skip to set as TBA:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=SKIP_KB,
    )
    return MC_INSTRUCTOR


async def mc_instructor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    instructor = "TBA" if text in ("⏭ Skip (TBA)", "skip", "tba", "") else text
    context.user_data["mc_current"]["instructor"] = instructor
    name = context.user_data["mc_current"]["name"]
    await update.message.reply_text(
        f"*{name}*\n\nSelect *course type*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=TYPE_KB,
    )
    return MC_TYPE


async def mc_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in ("📚 Class", "🔬 Lab"):
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=TYPE_KB)
        return MC_TYPE
    context.user_data["mc_current"]["is_lab"] = (text == "🔬 Lab")
    name = context.user_data["mc_current"]["name"]
    await update.message.reply_text(
        f"*{name}*\n\nSelect *batch* (year group):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=BATCH_KB,
    )
    return MC_BATCH


async def mc_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in BATCHES:
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=BATCH_KB)
        return MC_BATCH
    context.user_data["mc_current"]["batch"] = text
    name = context.user_data["mc_current"]["name"]
    await update.message.reply_text(
        f"*{name}*\n\nSelect *semester*:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=SEMESTER_KB,
    )
    return MC_SEMESTER


async def mc_semester(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in ("Semester 1", "Semester 2"):
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=SEMESTER_KB)
        return MC_SEMESTER

    sem = 1 if text == "Semester 1" else 2
    context.user_data["mc_current"]["semester"] = sem

    # Stage the completed course
    course = context.user_data["mc_current"]
    context.user_data["mc_courses"].append(course)
    context.user_data["mc_current"] = {}

    count = len(context.user_data["mc_courses"])
    kind  = "🔬 Lab" if course["is_lab"] else "📚 Class"

    # Show what was just staged
    staged_msg = (
        f"✅ *Staged #{count}:* {course['name']}\n"
        f"   {course['credit_hours']}cr | {kind} | "
        f"{course['batch']} yr | Sem {sem} | 👤 {course['instructor']}"
    )

    if count >= MAX_COURSES:
        # Reached the limit — go straight to confirm
        summary = _summary_text(context.user_data["mc_courses"])
        await update.message.reply_text(
            f"{staged_msg}\n\n"
            f"⚠️ Maximum of {MAX_COURSES} courses reached.\n\n"
            f"{summary}\n\n"
            "Tap *✅ Confirm & Save* to save all, or *🔄 Start over* to discard.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KB,
        )
        return MC_CONFIRM

    # Ask whether to add another
    await update.message.reply_text(
        f"{staged_msg}\n\n"
        f"Would you like to add another course? _{MAX_COURSES - count} slot(s) remaining_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=YESNO_KB,
    )
    return MC_ANOTHER


async def mc_another(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "✅ Yes, add another":
        await update.message.reply_text(
            f"{_course_progress(context)}\n\n✏️ Type the *course name*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return MC_NAME

    if text == "🏁 Done, save all":
        summary = _summary_text(context.user_data["mc_courses"])
        await update.message.reply_text(
            f"📋 *Review before saving:*\n\n{summary}\n\n"
            "Tap *✅ Confirm & Save* to save all, or *🔄 Start over* to discard.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=CONFIRM_KB,
        )
        return MC_CONFIRM

    await update.message.reply_text("Please tap one of the buttons:", reply_markup=YESNO_KB)
    return MC_ANOTHER


async def mc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "🔄 Start over":
        context.user_data.clear()
        await update.message.reply_text(
            "🔄 Discarded. Use /add_courses to start again.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if text != "✅ Confirm & Save":
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=CONFIRM_KB)
        return MC_CONFIRM

    # Save all staged courses
    courses = context.user_data.get("mc_courses", [])
    saved, failed = [], []

    with get_session() as session:
        for row in courses:
            try:
                c = add_course(session, **row)
                saved.append((c.id, row))
            except Exception as exc:
                failed.append(f"❌ *{row['name']}*: {exc}")

    lines = []
    if saved:
        lines.append(f"✅ *{len(saved)} course(s) saved successfully:*\n")
        for cid, row in saved:
            kind = "🔬 Lab" if row["is_lab"] else "📚 Class"
            lines.append(
                f"  `[{cid:>3}]` *{row['name']}*\n"
                f"         {row['credit_hours']}cr | {kind} | "
                f"{row['batch']} yr | Sem {row['semester']} | 👤 {row['instructor']}"
            )
    if failed:
        lines.append(f"\n❌ *{len(failed)} course(s) failed:*")
        lines.extend(failed)

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── /add_room and /add_lab conversations ─────────────────────────────────────
#
# Flow:
#   1. Type room name  (free text — names are invented by the head)
#   2. Select capacity  [20][30][40][50][60][80][100][⏭ Skip]
#   3. Add another?     [✅ Yes, add another][🏁 Done, save all]
#   4. Confirm & Save   [✅ Confirm & Save][🔄 Start over]
#

CAPACITY_KB = _kb([["20", "30", "40"], ["50", "60", "80"], ["100", "⏭ Skip (no capacity)"]])
ROOM_YESNO_KB = _kb([["✅ Yes, add another", "🏁 Done, save all"]])
ROOM_CONFIRM_KB = _kb([["✅ Confirm & Save", "🔄 Start over"]])

# Room conversation states (reused for both /add_room and /add_lab)
AR_NAME     = 8
AR_CAPACITY = 9
AR_ANOTHER  = 17   # new state
AR_CONFIRM  = 18   # new state

MAX_ROOMS = 10


def _room_summary(rooms: list) -> str:
    if not rooms:
        return "_No rooms staged yet._"
    lines = [f"*{len(rooms)} room(s) ready to save:*\n"]
    for i, r in enumerate(rooms, 1):
        cap = f" | {r['capacity']} seats" if r["capacity"] else ""
        icon = "🔬" if r["room_type"] == "lab" else "🏫"
        lines.append(f"  {icon} *{i}.* {r['name']}{cap}")
    return "\n".join(lines)


def _make_room_start(room_type: str):
    @admin_only
    @department_required
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        context.user_data["room_type"] = room_type
        context.user_data["ar_rooms"] = []
        label = "Lab" if room_type == "lab" else "Classroom"
        count = len(context.user_data["ar_rooms"])
        await update.message.reply_text(
            f"🏫 *Add {label}s* _(up to {MAX_ROOMS})_\n\n"
            f"📝 *Room {count + 1}*\n\n"
            "✏️ Type the *room name* (e.g. Lab-1, Room-101):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return AR_NAME
    return handler


async def ar_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Room name cannot be empty. Please type it:")
        return AR_NAME
    context.user_data["ar_current"] = {"name": name, "room_type": context.user_data["room_type"]}
    await update.message.reply_text(
        f"*{name}*\n\nSelect *capacity* (seats), or tap ⏭ Skip:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=CAPACITY_KB,
    )
    return AR_CAPACITY


async def ar_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    capacity = None

    if text != "⏭ Skip (no capacity)":
        if not text.isdigit():
            await update.message.reply_text(
                "Please tap one of the buttons:",
                reply_markup=CAPACITY_KB,
            )
            return AR_CAPACITY
        capacity = int(text)

    current = context.user_data["ar_current"]
    current["capacity"] = capacity
    context.user_data["ar_rooms"].append(current)
    context.user_data["ar_current"] = {}

    count = len(context.user_data["ar_rooms"])
    label = "Lab" if current["room_type"] == "lab" else "Classroom"
    cap_str = f" | {capacity} seats" if capacity else ""
    staged_msg = f"✅ *Staged #{count}:* {current['name']}{cap_str}"

    if count >= MAX_ROOMS:
        summary = _room_summary(context.user_data["ar_rooms"])
        await update.message.reply_text(
            f"{staged_msg}\n\n"
            f"⚠️ Maximum of {MAX_ROOMS} rooms reached.\n\n"
            f"{summary}\n\n"
            "Tap *✅ Confirm & Save* to save all, or *🔄 Start over* to discard.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ROOM_CONFIRM_KB,
        )
        return AR_CONFIRM

    await update.message.reply_text(
        f"{staged_msg}\n\n"
        f"Add another {label}? _{MAX_ROOMS - count} slot(s) remaining_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ROOM_YESNO_KB,
    )
    return AR_ANOTHER


async def ar_another(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    room_type = context.user_data.get("room_type", "classroom")
    label = "Lab" if room_type == "lab" else "Classroom"
    count = len(context.user_data.get("ar_rooms", []))

    if text == "✅ Yes, add another":
        await update.message.reply_text(
            f"📝 *Room {count + 1}*\n\n✏️ Type the *room name*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
        return AR_NAME

    if text == "🏁 Done, save all":
        summary = _room_summary(context.user_data["ar_rooms"])
        await update.message.reply_text(
            f"📋 *Review before saving:*\n\n{summary}\n\n"
            "Tap *✅ Confirm & Save* to save all, or *🔄 Start over* to discard.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ROOM_CONFIRM_KB,
        )
        return AR_CONFIRM

    await update.message.reply_text("Please tap one of the buttons:", reply_markup=ROOM_YESNO_KB)
    return AR_ANOTHER


async def ar_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "🔄 Start over":
        context.user_data.clear()
        await update.message.reply_text(
            "🔄 Discarded. Use /add_room or /add_lab to start again.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if text != "✅ Confirm & Save":
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=ROOM_CONFIRM_KB)
        return AR_CONFIRM

    rooms = context.user_data.get("ar_rooms", [])
    saved, failed = [], []

    with get_session() as session:
        for r in rooms:
            try:
                room = add_room(session, name=r["name"], room_type=r["room_type"], capacity=r["capacity"])
                saved.append((room.id, r))
            except Exception as exc:
                failed.append(f"❌ *{r['name']}*: {exc}")

    lines = []
    if saved:
        lines.append(f"✅ *{len(saved)} room(s) saved successfully:*\n")
        for rid, r in saved:
            icon = "🔬" if r["room_type"] == "lab" else "🏫"
            cap = f" | {r['capacity']} seats" if r["capacity"] else ""
            lines.append(f"  {icon} `[{rid:>3}]` *{r['name']}*{cap}")
    if failed:
        lines.append(f"\n❌ *{len(failed)} room(s) failed:*")
        lines.extend(failed)

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ── /list_courses ─────────────────────────────────────────────────────────────

@admin_only
@department_required
async def cmd_list_courses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        courses = list_courses(session)
    if not courses:
        await update.message.reply_text("No courses added yet. Use /add_course.")
        return

    lines = ["📋 *All Courses*\n"]
    current_batch = None
    for c in courses:
        if c.batch != current_batch:
            current_batch = c.batch
            lines.append(f"\n*{c.batch} Year*")
        kind = "🔬 Lab" if c.is_lab else "📚 Class"
        instructor_str = c.instructor if c.instructor else "TBA"
        lines.append(
            f"  `[{c.id:>3}]` *{c.name}*\n"
            f"         {c.credit_hours}cr | {kind} | Sem {c.semester} | 👤 {instructor_str}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── /list_rooms ───────────────────────────────────────────────────────────────

@admin_only
@department_required
async def cmd_list_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        rooms = list_rooms(session)
    if not rooms:
        await update.message.reply_text("No rooms added yet. Use /add_room or /add_lab.")
        return

    lines = ["🏢 *All Rooms & Labs*\n"]
    for r in rooms:
        icon = "🔬" if r.room_type == "lab" else "🏫"
        cap = f" | {r.capacity} seats" if r.capacity else ""
        lines.append(f"  {icon} `[{r.id:>3}]` {r.name}{cap}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── /generate_schedule ────────────────────────────────────────────────────────

@admin_only
@department_required
async def cmd_generate_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⚙️ Generating schedule, please wait…")
    with get_session() as session:
        # Clear existing schedule first
        cleared = clear_schedule(session)
        assigned, unassigned = generate_schedule(session)

    msg = f"✅ Schedule generated!\n\n📌 Assigned: *{assigned}* sessions"
    if cleared:
        msg = f"🔄 Previous schedule cleared ({cleared} entries).\n\n" + msg
    if unassigned:
        msg += f"\n\n⚠️ *Could not assign {len(unassigned)} session(s):*\n"
        msg += "\n".join(f"  • {u}" for u in unassigned[:20])
        if len(unassigned) > 20:
            msg += f"\n  … and {len(unassigned) - 20} more"
        msg += "\n\nTip: Add more rooms/labs or reduce credit hours."

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ── /view_schedule conversation ───────────────────────────────────────────────

@admin_only
@department_required
async def vs_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["All batches", "2nd"], ["3rd", "4th"]]
    await update.message.reply_text(
        "📅 *View Schedule*\n\nSelect batch:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb(keyboard),
    )
    return VS_BATCH


async def vs_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    valid = ["All batches", "2nd", "3rd", "4th"]
    if text not in valid:
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=_kb([["All batches", "2nd"], ["3rd", "4th"]]),
        )
        return VS_BATCH
    context.user_data["vs_batch"] = None if text == "All batches" else text
    await update.message.reply_text(
        "Select section:",
        reply_markup=_kb([["All sections", "A", "B"]]),
    )
    return VS_SECTION


async def vs_section(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in ("All sections", "A", "B"):
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=_kb([["All sections", "A", "B"]]),
        )
        return VS_SECTION
    context.user_data["vs_section"] = None if text == "All sections" else text
    await update.message.reply_text(
        "Select semester:",
        reply_markup=_kb([["All semesters", "Semester 1", "Semester 2"]]),
    )
    return VS_SEMESTER


async def vs_semester(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    valid = {"All semesters": None, "Semester 1": 1, "Semester 2": 2}
    if text not in valid:
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=_kb([["All semesters", "Semester 1", "Semester 2"]]),
        )
        return VS_SEMESTER
    semester = valid[text]

    data = context.user_data
    with get_session() as session:
        entries = get_schedule(
            session,
            batch=data.get("vs_batch"),
            section=data.get("vs_section"),
            semester=semester,
        )
        text_out = format_schedule_text(entries)

    # Telegram message limit is 4096 chars; split if needed
    MAX = 4000
    if len(text_out) <= MAX:
        await update.message.reply_text(
            text_out, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove()
        )
    else:
        chunks = [text_out[i : i + MAX] for i in range(0, len(text_out), MAX)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ End of schedule.", reply_markup=ReplyKeyboardRemove())

    context.user_data.clear()
    return ConversationHandler.END


# ── /reset_schedule ───────────────────────────────────────────────────────────

@admin_only
@department_required
async def cmd_reset_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        count = clear_schedule(session)
    await update.message.reply_text(f"🗑️ Schedule cleared. Removed {count} entries.")


# ── /delete_course conversation ───────────────────────────────────────────────

@admin_only
@department_required
async def dc_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_session() as session:
        courses = list_courses(session)
    if not courses:
        await update.message.reply_text("No courses to delete.")
        return ConversationHandler.END

    # Build one button per course: "ID – Name (batch)"
    buttons = [[f"{c.id} – {c.name} ({c.batch} yr)"] for c in courses]
    buttons.append(["❌ Cancel"])
    await update.message.reply_text(
        "🗑️ *Delete Course*\n\nTap the course to remove:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb(buttons, one_time=True),
    )
    # Store valid labels for validation
    context.user_data["dc_options"] = {
        f"{c.id} – {c.name} ({c.batch} yr)": c.id for c in courses
    }
    return DC_PICK


async def dc_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "❌ Cancel":
        return await conv_cancel(update, context)

    options = context.user_data.get("dc_options", {})
    course_id = options.get(text)
    if course_id is None:
        await update.message.reply_text("Please tap one of the buttons.")
        return DC_PICK

    with get_session() as session:
        ok = delete_course(session, course_id)

    if ok:
        await update.message.reply_text(
            f"✅ *{text.split(' – ', 1)[1]}* deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("❌ Course not found.", reply_markup=ReplyKeyboardRemove())

    context.user_data.clear()
    return ConversationHandler.END


# ── /delete_room conversation ─────────────────────────────────────────────────

@admin_only
@department_required
async def dr_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_session() as session:
        rooms = list_rooms(session)
    if not rooms:
        await update.message.reply_text("No rooms to delete.")
        return ConversationHandler.END

    buttons = [[f"{r.id} – {r.name} ({r.room_type})"] for r in rooms]
    buttons.append(["❌ Cancel"])
    await update.message.reply_text(
        "🗑️ *Delete Room*\n\nTap the room to remove:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb(buttons, one_time=True),
    )
    context.user_data["dr_options"] = {
        f"{r.id} – {r.name} ({r.room_type})": r.id for r in rooms
    }
    return DR_PICK


async def dr_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "❌ Cancel":
        return await conv_cancel(update, context)

    options = context.user_data.get("dr_options", {})
    room_id = options.get(text)
    if room_id is None:
        await update.message.reply_text("Please tap one of the buttons.")
        return DR_PICK

    with get_session() as session:
        ok = delete_room(session, room_id)

    if ok:
        await update.message.reply_text(
            f"✅ *{text.split(' – ', 1)[1]}* deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text("❌ Room not found.", reply_markup=ReplyKeyboardRemove())

    context.user_data.clear()
    return ConversationHandler.END


# ── /assign_instructor conversation ──────────────────────────────────────────

@admin_only
@department_required
async def ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    with get_session() as session:
        courses = list_courses(session)
    if not courses:
        await update.message.reply_text("No courses found. Use /add_courses first.")
        return ConversationHandler.END

    buttons = [
        [f"{c.id} – {c.name} ({c.batch} yr) 👤 {c.instructor or 'TBA'}"]
        for c in courses
    ]
    buttons.append(["❌ Cancel"])
    await update.message.reply_text(
        "👤 *Assign Instructor*\n\nTap the course to update:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb(buttons, one_time=True),
    )
    context.user_data["ai_options"] = {
        f"{c.id} – {c.name} ({c.batch} yr) 👤 {c.instructor or 'TBA'}": c.id
        for c in courses
    }
    return AI_PICK


async def ai_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "❌ Cancel":
        return await conv_cancel(update, context)

    options = context.user_data.get("ai_options", {})
    course_id = options.get(text)
    if course_id is None:
        await update.message.reply_text("Please tap one of the buttons.")
        return AI_PICK

    context.user_data["ai_course_id"] = course_id
    context.user_data["ai_course_label"] = text
    await update.message.reply_text(
        f"Selected: *{text}*\n\n✏️ Type the instructor's full name:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return AI_NAME


async def ai_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    instructor = update.message.text.strip()
    if not instructor:
        await update.message.reply_text("Name cannot be empty. Please type the instructor's name:")
        return AI_NAME

    course_id = context.user_data["ai_course_id"]
    with get_session() as session:
        ok = update_instructor(session, course_id, instructor)

    if ok:
        await update.message.reply_text(
            f"✅ Instructor updated!\n\n👤 *{instructor}* assigned to course ID `{course_id}`.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("❌ Course not found.")

    context.user_data.clear()
    return ConversationHandler.END


# ── /assign_lab conversation ──────────────────────────────────────────────────
#
# Strict 1-to-1: one lab → one batch, one batch → one lab.
#
# Flow:
#   1. Pick a lab from button list  (shows current assignment)
#   2. Pick ONE batch               [2nd Year] [3rd Year] [4th Year]
#      + [🗑 Remove assignment]  (to unassign)
#   3. Confirm                      [✅ Confirm] [🔄 Change]
#

BATCH_SELECT_KB = _kb([["2nd Year", "3rd Year", "4th Year"], ["🗑 Remove assignment", "❌ Cancel"]])


@admin_only
@department_required
async def al_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show all labs with their current 1-to-1 batch assignment."""
    with get_session() as session:
        labs        = list_labs(session)
        assignments = get_lab_batch_assignments(session)   # {room_id: batch}

    if not labs:
        await update.message.reply_text(
            "No labs found. Use /add_lab to add labs first.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    buttons = []
    lab_map = {}
    for lab in labs:
        assigned_batch = assignments.get(lab.id)
        status = f"→ {assigned_batch} Year" if assigned_batch else "→ unassigned"
        label  = f"🔬 {lab.name}  [{status}]"
        buttons.append([label])
        lab_map[label] = lab.id

    buttons.append(["❌ Cancel"])
    context.user_data["al_lab_map"]   = lab_map
    context.user_data["al_lab_names"] = {lab.id: lab.name for lab in labs}

    await update.message.reply_text(
        "🔬 *Assign Lab to Batch*\n\n"
        "Each lab serves *one batch only*.\n"
        "Tap a lab to assign or change its batch:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb(buttons, one_time=True),
    )
    return AL_PICK


async def al_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "❌ Cancel":
        return await conv_cancel(update, context)

    lab_map = context.user_data.get("al_lab_map", {})
    room_id = lab_map.get(text)
    if room_id is None:
        await update.message.reply_text("Please tap one of the buttons.")
        return AL_PICK

    context.user_data["al_room_id"] = room_id
    lab_name = context.user_data["al_lab_names"][room_id]

    # Show current assignment
    with get_session() as session:
        assignments = get_lab_batch_assignments(session)
    current = assignments.get(room_id)
    current_str = f"Currently: *{current} Year*" if current else "Currently: _unassigned_"

    await update.message.reply_text(
        f"🔬 *{lab_name}*\n{current_str}\n\n"
        "Select the batch for this lab:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=BATCH_SELECT_KB,
    )
    return AL_BATCHES


async def al_batches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "❌ Cancel":
        return await conv_cancel(update, context)

    room_id  = context.user_data["al_room_id"]
    lab_name = context.user_data["al_lab_names"][room_id]

    if text == "🗑 Remove assignment":
        context.user_data["al_action"] = "remove"
        context.user_data["al_batch"]  = None
        await update.message.reply_text(
            f"🔬 *{lab_name}*\n\n"
            "This will *remove* the batch assignment.\n"
            "The lab will not be used in scheduling until reassigned.\n\n"
            "Tap *✅ Confirm* to proceed:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_kb([["✅ Confirm", "🔄 Change"]]),
        )
        return AL_CONFIRM

    # Map button label → batch key
    batch_map = {"2nd Year": "2nd", "3rd Year": "3rd", "4th Year": "4th"}
    batch = batch_map.get(text)
    if batch is None:
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=BATCH_SELECT_KB,
        )
        return AL_BATCHES

    context.user_data["al_action"] = "assign"
    context.user_data["al_batch"]  = batch

    await update.message.reply_text(
        f"🔬 *{lab_name}* → *{batch} Year*\n\n"
        "Tap *✅ Confirm* to save:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_kb([["✅ Confirm", "🔄 Change"]]),
    )
    return AL_CONFIRM


async def al_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text == "🔄 Change":
        room_id  = context.user_data["al_room_id"]
        lab_name = context.user_data["al_lab_names"][room_id]
        await update.message.reply_text(
            f"🔬 *{lab_name}* — select the batch:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=BATCH_SELECT_KB,
        )
        return AL_BATCHES

    if text != "✅ Confirm":
        await update.message.reply_text(
            "Please tap one of the buttons:",
            reply_markup=_kb([["✅ Confirm", "🔄 Change"]]),
        )
        return AL_CONFIRM

    room_id  = context.user_data["al_room_id"]
    lab_name = context.user_data["al_lab_names"][room_id]
    action   = context.user_data["al_action"]
    batch    = context.user_data.get("al_batch")

    if action == "remove":
        with get_session() as session:
            removed = remove_lab_assignment(session, room_id)
        if removed:
            msg = f"🗑 Assignment removed. *{lab_name}* is now unassigned."
        else:
            msg = f"ℹ️ *{lab_name}* had no assignment to remove."
    else:
        with get_session() as session:
            ok, err = assign_lab_to_batch(session, room_id, batch)
        if ok:
            msg = f"✅ *{lab_name}* assigned to *{batch} Year*."
        else:
            msg = f"❌ Could not assign: {err}"

    await update.message.reply_text(
        msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END


# ── /list_lab_assignments  (quick view) ───────────────────────────────────────

@admin_only
@department_required
async def cmd_list_lab_assignments(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    with get_session() as session:
        labs        = list_labs(session)
        assignments = get_lab_batch_assignments(session)   # {room_id: batch}

    if not labs:
        await update.message.reply_text("No labs found. Use /add_lab first.")
        return

    lines = ["🔬 *Lab → Batch Assignments*\n"]
    for lab in labs:
        batch = assignments.get(lab.id)
        cap   = f" | {lab.capacity} seats" if lab.capacity else ""
        if batch:
            lines.append(f"  🔬 *{lab.name}*{cap}  →  *{batch} Year*")
        else:
            lines.append(f"  🔬 *{lab.name}*{cap}  →  _unassigned_")

    # Also show which batches still need a lab
    assigned_batches = set(assignments.values())
    missing = [b for b in ["2nd", "3rd", "4th"] if b not in assigned_batches]
    if missing:
        lines.append(
            "\n⚠️ *Batches without a lab:* "
            + ", ".join(f"*{b} Year*" for b in missing)
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )


# ── /curriculum conversation ──────────────────────────────────────────────────
#
# Flow:
#   1. Select year   [Year 1][Year 2][Year 3][Year 4][All]
#   2. Select semester  [Semester I][Semester II][Both]
#   → Display matching courses
#

YEAR_KB = _kb([["Year 1", "Year 2"], ["Year 3", "Year 4"], ["📋 All years"]])
SEM_KB  = _kb([["Semester I", "Semester II", "Both"]])

_YEAR_MAP = {"Year 1": 1, "Year 2": 2, "Year 3": 3, "Year 4": 4}
_SEM_MAP  = {"Semester I": 1, "Semester II": 2, "Both": None}


@admin_only
@department_required
async def cur_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📗 *Curriculum Browser*\n\nSelect a year:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=YEAR_KB,
    )
    return CUR_YEAR


async def cur_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    valid = list(_YEAR_MAP.keys()) + ["📋 All years"]
    if text not in valid:
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=YEAR_KB)
        return CUR_YEAR

    context.user_data["cur_year"] = _YEAR_MAP.get(text)  # None = all years
    await update.message.reply_text(
        "Select semester:",
        reply_markup=SEM_KB,
    )
    return CUR_SEMESTER


async def cur_semester(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text not in _SEM_MAP:
        await update.message.reply_text("Please tap one of the buttons:", reply_markup=SEM_KB)
        return CUR_SEMESTER

    year = context.user_data.get("cur_year")
    semester = _SEM_MAP[text]

    with get_session() as session:
        courses = get_curriculum_courses(session, year=year, semester=semester)
        result  = format_curriculum_text(courses)

    MAX = 4000
    if len(result) <= MAX:
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove()
        )
    else:
        for chunk in [result[i:i + MAX] for i in range(0, len(result), MAX)]:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ End of curriculum.", reply_markup=ReplyKeyboardRemove())

    context.user_data.clear()
    return ConversationHandler.END


# ── /search_course ────────────────────────────────────────────────────────────

@admin_only
@department_required
async def sc_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔍 *Search Curriculum*\n\nType a course name or code:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return SC_QUERY


async def sc_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Please type a search term:")
        return SC_QUERY

    with get_session() as session:
        courses = search_curriculum(session, query)
        result  = format_curriculum_text(courses)

    if not courses:
        await update.message.reply_text(
            f"No courses found matching *{query}*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await update.message.reply_text(
            result, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove()
        )

    return ConversationHandler.END


# ── Application builder ───────────────────────────────────────────────────────

def build_application(token: str) -> Application:
    """Wire all handlers and return the configured Application."""
    app = Application.builder().token(token).build()

    # /start — department selection conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("start", cmd_start)],
            states={
                DEPT_PICK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, dept_pick)],
                DEPT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, dept_confirm)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /switch_department conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("switch_department", sw_start)],
            states={
                SW_PICK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, sw_pick)],
                SW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, sw_confirm)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # Simple commands
    app.add_handler(CommandHandler("seed_slots", cmd_seed_slots))
    app.add_handler(CommandHandler("list_courses", cmd_list_courses))
    app.add_handler(CommandHandler("list_rooms", cmd_list_rooms))
    app.add_handler(CommandHandler("list_lab_assignments", cmd_list_lab_assignments))
    app.add_handler(CommandHandler("generate_schedule", cmd_generate_schedule))
    app.add_handler(CommandHandler("reset_schedule", cmd_reset_schedule))
    app.add_handler(CommandHandler("export_schedule", cmd_export_schedule))

    # /add_courses — button-driven, 1–10 courses per session
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("add_courses", mc_start)],
            states={
                MC_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_name)],
                MC_CREDITS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_credits)],
                MC_INSTRUCTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_instructor)],
                MC_TYPE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_type)],
                MC_BATCH:      [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_batch)],
                MC_SEMESTER:   [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_semester)],
                MC_ANOTHER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_another)],
                MC_CONFIRM:    [MessageHandler(filters.TEXT & ~filters.COMMAND, mc_confirm)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /add_room conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("add_room", _make_room_start("classroom"))],
            states={
                AR_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_name)],
                AR_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_capacity)],
                AR_ANOTHER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_another)],
                AR_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_confirm)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /add_lab conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("add_lab", _make_room_start("lab"))],
            states={
                AR_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_name)],
                AR_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_capacity)],
                AR_ANOTHER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_another)],
                AR_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ar_confirm)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /view_schedule conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("view_schedule", vs_start)],
            states={
                VS_BATCH:    [MessageHandler(filters.TEXT & ~filters.COMMAND, vs_batch)],
                VS_SECTION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, vs_section)],
                VS_SEMESTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, vs_semester)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /delete_course conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("delete_course", dc_start)],
            states={
                DC_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, dc_pick)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /delete_room conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("delete_room", dr_start)],
            states={
                DR_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, dr_pick)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /assign_instructor conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("assign_instructor", ai_start)],
            states={
                AI_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_pick)],
                AI_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_name)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /assign_lab conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("assign_lab", al_start)],
            states={
                AL_PICK:    [MessageHandler(filters.TEXT & ~filters.COMMAND, al_pick)],
                AL_BATCHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, al_batches)],
                AL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, al_confirm)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /curriculum conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("curriculum", cur_start)],
            states={
                CUR_YEAR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, cur_year)],
                CUR_SEMESTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, cur_semester)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    # /search_course conversation
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("search_course", sc_start)],
            states={
                SC_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, sc_query)],
            },
            fallbacks=[CommandHandler("cancel", conv_cancel)],
        )
    )

    return app


# ── /export_schedule ──────────────────────────────────────────────────────────

@admin_only
@department_required
async def cmd_export_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export the full schedule to Excel and send as a file."""
    await update.message.reply_text("📊 Generating Excel file…")
    try:
        from utils.export import export_to_excel
        path = export_to_excel(output_path="/tmp/schedule.xlsx")
        with open(path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="IT_Department_Schedule.xlsx",
                caption="📅 Haramaya University IT Department — Full Schedule",
            )
        os.remove(path)
    except Exception as exc:
        logger.exception("Export failed")
        await update.message.reply_text(f"❌ Export failed: {exc}")
