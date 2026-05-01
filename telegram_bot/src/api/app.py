"""
FastAPI REST API for the IT Schedule Management Bot.
Shares the same database models and commands as the Telegram bot.

Run:
    uvicorn src.api.app:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from pydantic import BaseModel, Field

from src.database.db import get_session
from src.bot.commands import (
    add_course, list_courses, delete_course, update_instructor,
    add_room, list_rooms, list_labs, delete_room,
    assign_lab_to_batch, remove_lab_assignment, get_lab_batch_assignments,
    seed_time_slots, get_schedule, clear_schedule, format_schedule_text,
    get_curriculum_courses, search_curriculum,
    get_admin_profile, set_admin_department,
)
from src.config import DEPARTMENTS, BATCHES, SECTIONS

app = FastAPI(
    title="ITSMB API",
    description="IT Schedule Management Bot — REST API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CourseIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    credit_hours: int = Field(..., ge=1, le=4)
    is_lab: bool = False
    batch: str = Field(..., pattern="^(2nd|3rd|4th)$")
    semester: int = Field(..., ge=1, le=2)
    instructor: str = Field(default="TBA", max_length=120)


class CourseOut(BaseModel):
    id: int
    name: str
    credit_hours: int
    is_lab: bool
    batch: str
    semester: int
    instructor: str

    class Config:
        from_attributes = True


class RoomIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    room_type: str = Field(..., pattern="^(classroom|lab)$")
    capacity: Optional[int] = None


class RoomOut(BaseModel):
    id: int
    name: str
    room_type: str
    capacity: Optional[int]

    class Config:
        from_attributes = True


class InstructorIn(BaseModel):
    instructor: str = Field(..., min_length=1, max_length=120)


class LabAssignIn(BaseModel):
    batch: str = Field(..., pattern="^(2nd|3rd|4th)$")


class CurriculumCourseOut(BaseModel):
    id: int
    code: str
    title: str
    full_name: Optional[str]
    credits: Optional[int]
    credit_hours: Optional[int]
    note: Optional[str]
    semester_label: str
    year: int
    semester: int

    class Config:
        from_attributes = True


class ScheduleEntryOut(BaseModel):
    id: int
    course_name: str
    is_lab: bool
    instructor: str
    room_name: str
    batch: str
    section: str
    semester: int
    day: str
    start_hour: int
    end_hour: int
    time_label: str


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "ITSMB API"}


# ── Departments ───────────────────────────────────────────────────────────────

@app.get("/departments", tags=["System"])
def get_departments():
    return {"departments": DEPARTMENTS}


# ── Courses ───────────────────────────────────────────────────────────────────

@app.get("/courses", response_model=List[CourseOut], tags=["Courses"])
def get_courses(
    batch: Optional[str] = Query(None),
    semester: Optional[int] = Query(None),
):
    with get_session() as session:
        courses = list_courses(session)
        if batch:
            courses = [c for c in courses if c.batch == batch]
        if semester:
            courses = [c for c in courses if c.semester == semester]
        return [CourseOut.model_validate(c) for c in courses]


@app.post("/courses", response_model=CourseOut, status_code=201, tags=["Courses"])
def create_course(body: CourseIn):
    with get_session() as session:
        try:
            c = add_course(
                session,
                name=body.name,
                credit_hours=body.credit_hours,
                is_lab=body.is_lab,
                batch=body.batch,
                semester=body.semester,
                instructor=body.instructor,
            )
            return CourseOut.model_validate(c)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))


@app.delete("/courses/{course_id}", status_code=204, tags=["Courses"])
def remove_course(course_id: int):
    with get_session() as session:
        if not delete_course(session, course_id):
            raise HTTPException(status_code=404, detail="Course not found")


@app.patch("/courses/{course_id}/instructor", response_model=CourseOut, tags=["Courses"])
def set_instructor(course_id: int, body: InstructorIn):
    with get_session() as session:
        if not update_instructor(session, course_id, body.instructor):
            raise HTTPException(status_code=404, detail="Course not found")
        courses = list_courses(session)
        c = next((x for x in courses if x.id == course_id), None)
        return CourseOut.model_validate(c)


# ── Rooms ─────────────────────────────────────────────────────────────────────

@app.get("/rooms", response_model=List[RoomOut], tags=["Rooms"])
def get_rooms(room_type: Optional[str] = Query(None)):
    with get_session() as session:
        rooms = list_rooms(session)
        if room_type:
            rooms = [r for r in rooms if r.room_type == room_type]
        return [RoomOut.model_validate(r) for r in rooms]


@app.post("/rooms", response_model=RoomOut, status_code=201, tags=["Rooms"])
def create_room(body: RoomIn):
    with get_session() as session:
        r = add_room(session, name=body.name, room_type=body.room_type, capacity=body.capacity)
        return RoomOut.model_validate(r)


@app.delete("/rooms/{room_id}", status_code=204, tags=["Rooms"])
def remove_room(room_id: int):
    with get_session() as session:
        if not delete_room(session, room_id):
            raise HTTPException(status_code=404, detail="Room not found")


# ── Lab Assignments ───────────────────────────────────────────────────────────

@app.get("/labs/assignments", tags=["Labs"])
def get_assignments():
    with get_session() as session:
        labs = list_labs(session)
        assignments = get_lab_batch_assignments(session)
        return [
            {
                "lab_id": lab.id,
                "lab_name": lab.name,
                "capacity": lab.capacity,
                "assigned_batch": assignments.get(lab.id),
            }
            for lab in labs
        ]


@app.post("/labs/{lab_id}/assign", tags=["Labs"])
def assign_lab(lab_id: int, body: LabAssignIn):
    with get_session() as session:
        ok, err = assign_lab_to_batch(session, lab_id, body.batch)
        if not ok:
            raise HTTPException(status_code=409, detail=err)
        return {"lab_id": lab_id, "batch": body.batch, "status": "assigned"}


@app.delete("/labs/{lab_id}/assign", status_code=204, tags=["Labs"])
def unassign_lab(lab_id: int):
    with get_session() as session:
        if not remove_lab_assignment(session, lab_id):
            raise HTTPException(status_code=404, detail="No assignment found for this lab")


# ── Schedule ──────────────────────────────────────────────────────────────────

@app.get("/schedule", response_model=List[ScheduleEntryOut], tags=["Schedule"])
def get_timetable(
    batch: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    semester: Optional[int] = Query(None),
):
    with get_session() as session:
        entries = get_schedule(session, batch=batch, section=section, semester=semester)
        result = []
        for e in entries:
            result.append(ScheduleEntryOut(
                id=e.id,
                course_name=e.course.name,
                is_lab=e.course.is_lab,
                instructor=e.course.instructor,
                room_name=e.room.name,
                batch=e.batch,
                section=e.section,
                semester=e.semester,
                day=e.time_slot.day,
                start_hour=e.time_slot.start_hour,
                end_hour=e.time_slot.end_hour,
                time_label=e.time_slot.label,
            ))
        return result


@app.post("/schedule/generate", tags=["Schedule"])
def generate(clear_first: bool = Query(default=True)):
    from src.scheduler.engine import generate_schedule
    with get_session() as session:
        if clear_first:
            cleared = clear_schedule(session)
        else:
            cleared = 0
        assigned, unassigned = generate_schedule(session)
        return {
            "cleared": cleared,
            "assigned": assigned,
            "unassigned_count": len(unassigned),
            "unassigned": unassigned,
        }


@app.delete("/schedule", status_code=204, tags=["Schedule"])
def reset_schedule():
    with get_session() as session:
        clear_schedule(session)


# ── Curriculum ────────────────────────────────────────────────────────────────

@app.get("/curriculum", response_model=List[CurriculumCourseOut], tags=["Curriculum"])
def get_curriculum(
    year: Optional[int] = Query(None),
    semester: Optional[int] = Query(None),
):
    with get_session() as session:
        courses = get_curriculum_courses(session, year=year, semester=semester)
        result = []
        for c in courses:
            result.append(CurriculumCourseOut(
                id=c.id,
                code=c.code,
                title=c.title,
                full_name=c.full_name,
                credits=c.credits,
                credit_hours=c.credit_hours,
                note=c.note,
                semester_label=c.semester_obj.label,
                year=c.semester_obj.year,
                semester=c.semester_obj.semester,
            ))
        return result


@app.get("/curriculum/search", response_model=List[CurriculumCourseOut], tags=["Curriculum"])
def search_courses(q: str = Query(..., min_length=1)):
    with get_session() as session:
        courses = search_curriculum(session, q)
        result = []
        for c in courses:
            result.append(CurriculumCourseOut(
                id=c.id,
                code=c.code,
                title=c.title,
                full_name=c.full_name,
                credits=c.credits,
                credit_hours=c.credit_hours,
                note=c.note,
                semester_label=c.semester_obj.label,
                year=c.semester_obj.year,
                semester=c.semester_obj.semester,
            ))
        return result
