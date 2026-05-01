-- ============================================================
-- ITSMB — Full Database Setup for Supabase
-- Run this entire file in:
--   Supabase Dashboard → SQL Editor → New query → Paste → Run
-- ============================================================


-- ── 1. DROP existing tables (safe re-run) ────────────────────
DROP TABLE IF EXISTS schedule_entries   CASCADE;
DROP TABLE IF EXISTS lab_batch_assignments CASCADE;
DROP TABLE IF EXISTS time_slots         CASCADE;
DROP TABLE IF EXISTS rooms              CASCADE;
DROP TABLE IF EXISTS courses            CASCADE;
DROP TABLE IF EXISTS curriculum_courses CASCADE;
DROP TABLE IF EXISTS curriculum_semesters CASCADE;
DROP TABLE IF EXISTS admin_profiles     CASCADE;


-- ── 2. SCHEMA ─────────────────────────────────────────────────

-- Admin profiles (one row per department head)
CREATE TABLE admin_profiles (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT      NOT NULL UNIQUE,
    department  VARCHAR(120) NOT NULL,
    full_name   VARCHAR(120)
);

-- Curriculum semesters
CREATE TABLE curriculum_semesters (
    id       SERIAL PRIMARY KEY,
    year     INTEGER      NOT NULL,
    semester INTEGER      NOT NULL,
    label    VARCHAR(50)  NOT NULL,
    status   VARCHAR(100),
    CONSTRAINT uq_curriculum_semester UNIQUE (year, semester)
);

-- Curriculum courses
CREATE TABLE curriculum_courses (
    id           SERIAL PRIMARY KEY,
    semester_id  INTEGER      NOT NULL REFERENCES curriculum_semesters(id) ON DELETE CASCADE,
    code         VARCHAR(30)  NOT NULL,
    title        VARCHAR(200) NOT NULL,
    full_name    VARCHAR(200),
    credits      INTEGER,
    credit_hours INTEGER,
    note         VARCHAR(200)
);

-- Courses (added by department head)
CREATE TABLE courses (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(120) NOT NULL,
    credit_hours INTEGER      NOT NULL,
    is_lab       BOOLEAN      NOT NULL DEFAULT FALSE,
    batch        VARCHAR(10)  NOT NULL,
    semester     INTEGER      NOT NULL,
    instructor   VARCHAR(120) NOT NULL DEFAULT 'TBA',
    CONSTRAINT ck_credit_hours_range CHECK (credit_hours >= 1 AND credit_hours <= 4)
);

-- Rooms and labs
CREATE TABLE rooms (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(60)  NOT NULL UNIQUE,
    room_type VARCHAR(20)  NOT NULL,   -- 'classroom' | 'lab'
    capacity  INTEGER
);

-- Lab → Batch assignments (strict 1-to-1)
CREATE TABLE lab_batch_assignments (
    id      SERIAL PRIMARY KEY,
    room_id INTEGER     NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    batch   VARCHAR(10) NOT NULL,
    CONSTRAINT uq_lab_one_batch  UNIQUE (room_id),
    CONSTRAINT uq_batch_one_lab  UNIQUE (batch)
);

-- Time slots (Mon–Fri, 08:00–17:00)
CREATE TABLE time_slots (
    id         SERIAL PRIMARY KEY,
    day        VARCHAR(15) NOT NULL,
    start_hour INTEGER     NOT NULL,
    end_hour   INTEGER     NOT NULL,
    CONSTRAINT uq_timeslot UNIQUE (day, start_hour)
);

-- Schedule entries
CREATE TABLE schedule_entries (
    id           SERIAL PRIMARY KEY,
    course_id    INTEGER    NOT NULL REFERENCES courses(id)    ON DELETE CASCADE,
    room_id      INTEGER    NOT NULL REFERENCES rooms(id)      ON DELETE CASCADE,
    time_slot_id INTEGER    NOT NULL REFERENCES time_slots(id) ON DELETE CASCADE,
    batch        VARCHAR(10) NOT NULL,
    section      VARCHAR(5)  NOT NULL,
    semester     INTEGER     NOT NULL,
    CONSTRAINT uq_room_slot    UNIQUE (room_id, time_slot_id),
    CONSTRAINT uq_section_slot UNIQUE (batch, section, time_slot_id)
);


-- ── 3. SEED — Time Slots (Mon–Fri, 08:00–17:00) ──────────────

INSERT INTO time_slots (day, start_hour, end_hour) VALUES
  ('Monday',    8,  9), ('Monday',    9, 10), ('Monday',   10, 11),
  ('Monday',   11, 12), ('Monday',   12, 13), ('Monday',   13, 14),
  ('Monday',   14, 15), ('Monday',   15, 16), ('Monday',   16, 17),
  ('Tuesday',   8,  9), ('Tuesday',   9, 10), ('Tuesday',  10, 11),
  ('Tuesday',  11, 12), ('Tuesday',  12, 13), ('Tuesday',  13, 14),
  ('Tuesday',  14, 15), ('Tuesday',  15, 16), ('Tuesday',  16, 17),
  ('Wednesday', 8,  9), ('Wednesday', 9, 10), ('Wednesday',10, 11),
  ('Wednesday',11, 12), ('Wednesday',12, 13), ('Wednesday',13, 14),
  ('Wednesday',14, 15), ('Wednesday',15, 16), ('Wednesday',16, 17),
  ('Thursday',  8,  9), ('Thursday',  9, 10), ('Thursday', 10, 11),
  ('Thursday', 11, 12), ('Thursday', 12, 13), ('Thursday', 13, 14),
  ('Thursday', 14, 15), ('Thursday', 15, 16), ('Thursday', 16, 17),
  ('Friday',    8,  9), ('Friday',    9, 10), ('Friday',   10, 11),
  ('Friday',   11, 12), ('Friday',   12, 13), ('Friday',   13, 14),
  ('Friday',   14, 15), ('Friday',   15, 16), ('Friday',   16, 17);


-- ── 4. SEED — Curriculum Semesters ───────────────────────────

INSERT INTO curriculum_semesters (year, semester, label, status) VALUES
  (1, 2, 'Year 1 Semester II',  NULL),
  (2, 1, 'Year 2 Semester I',   NULL),
  (2, 2, 'Year 2 Semester II',  NULL),
  (3, 1, 'Year 3 Semester I',   NULL),
  (3, 2, 'Year 3 Semester II',  NULL),
  (4, 1, 'Year 4 Semester I',   'placeholder — courses to be added'),
  (4, 2, 'Year 4 Semester II',  'placeholder — courses to be added');


-- ── 5. SEED — Curriculum Courses ─────────────────────────────

-- Year 1 Semester II  (semester_id = 1)
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (1, 'EmTe1012', 'Introduction to Emerging Technologies',       'Introduction to Emerging Technologies',          5, 3, NULL),
  (1, 'EnLa1012', 'Communicative English Skills II',             'Communicative English Language Skills II',        5, 3, NULL),
  (1, 'ITec1012', 'Basic Computer Programming',                  'Basic Computer Programming',                      5, 3, NULL),
  (1, 'Math1012', 'Applied Mathematics',                         'Applied Mathematics',                             5, 3, NULL),
  (1, 'HIST1012', 'History of Ethiopia and the Horn',            'History of Ethiopia and the Horn of Africa',      5, 3, NULL),
  (1, 'Anth1012', 'Anthropology of Ethiopian Societies and Cultures', 'Anthropology of Ethiopian Societies and Cultures', 4, 2, NULL),
  (1, 'MCiE1012', 'Moral and Civic Education',                   'Moral and Civic Education',                       4, 2, NULL);

-- Year 2 Semester I  (semester_id = 2)
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (2, 'Gltr2015', 'Global Trends',                               'Global Trends',                                   4, 2, NULL),
  (2, 'Incl2011', 'Inclusiveness',                               'Inclusiveness',                                   4, 2, NULL),
  (2, 'ITec2071', 'Basic Computer Programming',                  'Basic Computer Programming',                      5, 3, 'duplicate code — likely ITec2011 or similar'),
  (2, 'ITec2071', 'Fundamentals of Database Systems',            'Fundamentals of Database Systems',                5, 3, 'duplicate code — likely ITec2072 or similar'),
  (2, 'Stat2171', 'Introduction to Statistics',                  'Introduction to Statistics',                      5, 3, NULL),
  (2, 'Eeng2161', 'Fundamentals of Electricity and Electronics Device', 'Fundamentals of Electricity and Electronics Devices', 5, 3, NULL),
  (2, 'Eco2013',  'Economics',                                   'Economics',                                       5, 3, 'elective (*)');

-- Year 2 Semester II  (semester_id = 3)
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (3, 'ITec2022', 'Operating Systems',                           'Operating Systems',                               5, 3, NULL),
  (3, 'ITec2024', 'Computer Organization and Architecture',      'Computer Organization and Architecture',          5, 3, NULL),
  (3, 'ITec2102', 'Data Communication and Computer Networks',    'Data Communication and Computer Networks',        5, 3, NULL),
  (3, 'ITec2052', 'Data Structure and Algorithms',               'Data Structures and Algorithms',                  5, 3, NULL),
  (3, 'Math2182', 'Discrete Mathematics',                        'Discrete Mathematics',                            5, 3, NULL),
  (3, 'ITec2092', 'Internet Programming I',                      'Internet Programming I',                          5, 3, NULL);

-- Year 3 Semester I  (semester_id = 4)
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (4, 'ITec3061', 'System Analysis and Design',                  'Systems Analysis and Design',                     5, 3, NULL),
  (4, 'ITec3121', 'Multimedia Systems',                          'Multimedia Systems',                              5, 3, NULL),
  (4, 'ITec3051', 'Object Oriented Programming',                 'Object-Oriented Programming',                     5, 3, NULL),
  (4, 'ITec4122', 'Internet Programming II',                     'Internet Programming II',                         5, 3, NULL),
  (4, 'ITec3071', 'Advanced Database Systems',                   'Advanced Database Systems',                       5, 3, NULL),
  (4, 'ITec3101', 'Telecom Technologies',                        'Telecommunication Technologies',                  3, 2, NULL);

-- Year 3 Semester II  (semester_id = 5)
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (5, 'ITec3084', 'GIS and Remote Sensing',                      'Geographic Information Systems and Remote Sensing', 5, 3, NULL),
  (5, 'ITec3102', 'Introduction to Distributed System',          'Introduction to Distributed Systems',             5, 3, NULL),
  (5, 'ITec3062', 'Information Technology Project Management',   'Information Technology Project Management',       5, 3, NULL),
  (5, 'ITec3054', 'Event Driven Programming',                    'Event-Driven Programming',                        5, 3, NULL),
  (5, 'ITec3082', 'Information Storage and Retrieval',           'Information Storage and Retrieval',               5, 3, NULL),
  (5, 'ITec3032', 'Computer Maintenance and Technical Support',  'Computer Maintenance and Technical Support',      5, 3, NULL);

-- Year 4 Semester I  (semester_id = 6) — placeholders
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (6, 'TBD', 'Course 1', 'TBD', NULL, NULL, NULL),
  (6, 'TBD', 'Course 2', 'TBD', NULL, NULL, NULL),
  (6, 'TBD', 'Course 3', 'TBD', NULL, NULL, NULL),
  (6, 'TBD', 'Course 4', 'TBD', NULL, NULL, NULL),
  (6, 'TBD', 'Course 5', 'TBD', NULL, NULL, NULL),
  (6, 'TBD', 'Course 6', 'TBD', NULL, NULL, NULL);

-- Year 4 Semester II  (semester_id = 7) — placeholders
INSERT INTO curriculum_courses (semester_id, code, title, full_name, credits, credit_hours, note) VALUES
  (7, 'TBD', 'Course 1', 'TBD', NULL, NULL, NULL),
  (7, 'TBD', 'Course 2', 'TBD', NULL, NULL, NULL),
  (7, 'TBD', 'Course 3', 'TBD', NULL, NULL, NULL),
  (7, 'TBD', 'Course 4', 'TBD', NULL, NULL, NULL),
  (7, 'TBD', 'Course 5', 'TBD', NULL, NULL, NULL),
  (7, 'TBD', 'Course 6', 'TBD', NULL, NULL, NULL);


-- ── 6. VERIFY ─────────────────────────────────────────────────
SELECT 'admin_profiles'      AS tbl, COUNT(*) FROM admin_profiles      UNION ALL
SELECT 'curriculum_semesters',        COUNT(*) FROM curriculum_semesters UNION ALL
SELECT 'curriculum_courses',          COUNT(*) FROM curriculum_courses   UNION ALL
SELECT 'courses',                     COUNT(*) FROM courses              UNION ALL
SELECT 'rooms',                       COUNT(*) FROM rooms                UNION ALL
SELECT 'time_slots',                  COUNT(*) FROM time_slots           UNION ALL
SELECT 'schedule_entries',            COUNT(*) FROM schedule_entries;
