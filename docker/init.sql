-- ============================================================
-- LabSense — PostgreSQL Schema Initialization
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- ENUM Types
-- ────────────────────────────────────────────────────────────

CREATE TYPE pc_state_enum AS ENUM (
    'AVAILABLE',
    'IN_USE',
    'AVAILABLE_SLEEP',
    'MAINTENANCE'
);

CREATE TYPE lab_state_enum AS ENUM (
    'OPEN',
    'OCCUPIED',
    'CLOSED'
);

CREATE TYPE user_role_enum AS ENUM (
    'STUDENT',
    'PROFESSOR',
    'ADMIN'
);

CREATE TYPE damage_report_status_enum AS ENUM (
    'PENDING',
    'APPROVED',
    'DISMISSED'
);

-- ────────────────────────────────────────────────────────────
-- Tables
-- ────────────────────────────────────────────────────────────

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    role          user_role_enum NOT NULL
);

CREATE TABLE labs (
    lab_id               TEXT PRIMARY KEY,
    lab_name             TEXT NOT NULL,
    operating_start_time TIME DEFAULT '08:00:00',
    operating_end_time   TIME DEFAULT '20:00:00'
);

CREATE TABLE pcs (
    pc_id              TEXT PRIMARY KEY,
    lab_id             TEXT REFERENCES labs(lab_id) ON DELETE CASCADE,
    current_state      pc_state_enum DEFAULT 'AVAILABLE',
    is_maintenance     BOOLEAN DEFAULT FALSE,
    last_heartbeat_at  TIMESTAMPTZ,
    installed_software JSONB DEFAULT '[]'::jsonb
);

CREATE TABLE state_transitions (
    id              SERIAL PRIMARY KEY,
    pc_id           TEXT REFERENCES pcs(pc_id) ON DELETE CASCADE,
    from_state      pc_state_enum,
    to_state        pc_state_enum,
    transitioned_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE master_timetables (
    timetable_id SERIAL PRIMARY KEY,
    lab_id       TEXT REFERENCES labs(lab_id) ON DELETE CASCADE,
    day_of_week  INT CHECK (day_of_week BETWEEN 1 AND 7),
    start_time   TIME,
    end_time     TIME,
    course_code  TEXT
);

CREATE TABLE slot_cancellations (
    cancellation_id    SERIAL PRIMARY KEY,
    timetable_id       INT REFERENCES master_timetables(timetable_id) ON DELETE CASCADE,
    cancelled_for_date DATE,
    cancelled_by       INT REFERENCES users(user_id)
);

CREATE TABLE damage_reports (
    report_id         SERIAL PRIMARY KEY,
    pc_id             TEXT REFERENCES pcs(pc_id) ON DELETE CASCADE,
    reported_by       INT REFERENCES users(user_id),
    issue_description TEXT,
    status            damage_report_status_enum DEFAULT 'PENDING',
    created_at        TIMESTAMPTZ DEFAULT now(),
    resolved_by       INT REFERENCES users(user_id),
    resolved_at       TIMESTAMPTZ
);

-- ────────────────────────────────────────────────────────────
-- Indexes
-- ────────────────────────────────────────────────────────────

CREATE INDEX idx_pcs_software ON pcs USING GIN (installed_software);

-- ────────────────────────────────────────────────────────────
-- Seed Data
-- ────────────────────────────────────────────────────────────

-- Lab
INSERT INTO labs (lab_id, lab_name) VALUES
    ('lab-a', 'Computer Lab A');

-- PCs
INSERT INTO pcs (pc_id, lab_id, current_state) VALUES
    ('lab-a-pc-1', 'lab-a', 'AVAILABLE'),
    ('lab-a-pc-2', 'lab-a', 'AVAILABLE'),
    ('lab-a-pc-3', 'lab-a', 'AVAILABLE'),
    ('lab-a-pc-4', 'lab-a', 'AVAILABLE'),
    ('lab-a-pc-5', 'lab-a', 'AVAILABLE');

-- Users (password: password123)
INSERT INTO users (email, password_hash, full_name, role) VALUES
    ('admin@labsense.dev',   '$2b$12$WApznUPhDubN0oeveSXHpOgKhBbzBuH1kV1eGuhIvBwm9mMoy1qoC', 'Admin User',    'ADMIN'),
    ('prof@labsense.dev',    '$2b$12$WApznUPhDubN0oeveSXHpOgKhBbzBuH1kV1eGuhIvBwm9mMoy1qoC', 'Prof. Kumar',   'PROFESSOR'),
    ('student@labsense.dev', '$2b$12$WApznUPhDubN0oeveSXHpOgKhBbzBuH1kV1eGuhIvBwm9mMoy1qoC', 'Rahul Sharma',  'STUDENT');

-- Timetable entries
INSERT INTO master_timetables (lab_id, day_of_week, start_time, end_time, course_code) VALUES
    ('lab-a', 1, '09:00', '11:00', 'CS204'),
    ('lab-a', 3, '14:00', '16:00', 'CS208'),
    ('lab-a', 5, '10:00', '12:00', 'CE102');
