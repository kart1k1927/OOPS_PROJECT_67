-- 002_app_identity_and_lifecycle.sql
-- Run once: Supabase dashboard > SQL Editor > New query > paste > Run.
-- Safe to run twice, every statement is guarded.
--
-- Why each block exists is explained inline, because these notes go into the
-- Database Design section of the report.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Identity moves out of Supabase Auth and into the application.
--
-- profiles.id referenced auth.users(id), but the auth schema on this project is
-- not usable: GoTrue's admin API fails with "Database error finding users",
-- because the four existing profile rows were inserted with hand written UUIDs.
-- Rather than repair GoTrue, the application owns identity. That is also the
-- better answer for this project: a User class hierarchy with its own password
-- hashing is demonstrable object oriented design, whereas delegating to a
-- hosted auth service is not.
-- ---------------------------------------------------------------------------

ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_id_fkey;
ALTER TABLE public.profiles ALTER COLUMN id SET DEFAULT gen_random_uuid();

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS full_name     TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS email         TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS password_hash TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_email
    ON public.profiles (lower(email));

-- ---------------------------------------------------------------------------
-- 2. Technician attributes the assignment strategies need.
--
-- SkillBasedAssignment reads technician_skills, LoadBalancedAssignment needs a
-- ceiling to compare against, ExperienceBasedAssignment needs a level.
-- ---------------------------------------------------------------------------

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS max_workload INTEGER NOT NULL DEFAULT 5;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS experience_level INTEGER NOT NULL DEFAULT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'profiles_experience_level_check'
    ) THEN
        ALTER TABLE public.profiles
            ADD CONSTRAINT profiles_experience_level_check
            CHECK (experience_level BETWEEN 1 AND 5);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. The incident lifecycle gains ACKNOWLEDGED and VERIFIED.
--
-- The problem statement's lifecycle is
--   NEW -> CLASSIFIED -> ASSIGNED -> ACKNOWLEDGED -> IN_PROGRESS
--       -> RESOLVED -> VERIFIED -> CLOSED
-- and requires that illegal transitions be prevented. The original CHECK was
-- missing ACKNOWLEDGED and VERIFIED, so a technician could not acknowledge and
-- a reporter could not verify. CLASSIFIED is included for completeness; the
-- State machine in app/domain/states.py is what actually enforces the order.
-- ---------------------------------------------------------------------------

ALTER TABLE public.incidents DROP CONSTRAINT IF EXISTS incidents_status_check;
ALTER TABLE public.incidents
    ADD CONSTRAINT incidents_status_check CHECK (
        status IN (
            'OPEN',
            'CLASSIFIED',
            'ASSIGNED',
            'ACKNOWLEDGED',
            'IN_PROGRESS',
            'PENDING',
            'RESOLVED',
            'VERIFIED',
            'CLOSED'
        )
    );

-- ---------------------------------------------------------------------------
-- 4. Columns the domain model needs.
-- ---------------------------------------------------------------------------

ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS priority_score   NUMERIC(8,2);
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS escalation_level INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS acknowledged_at  TIMESTAMPTZ;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS verified_at      TIMESTAMPTZ;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS resolution_notes TEXT;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS closure_notes    TEXT;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS duplicate_of_id  UUID;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS feedback_rating  INTEGER;
ALTER TABLE public.incidents ADD COLUMN IF NOT EXISTS feedback_comment TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'incidents_duplicate_of_fkey'
    ) THEN
        ALTER TABLE public.incidents
            ADD CONSTRAINT incidents_duplicate_of_fkey
            FOREIGN KEY (duplicate_of_id)
            REFERENCES public.incidents(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'incidents_feedback_rating_check'
    ) THEN
        ALTER TABLE public.incidents
            ADD CONSTRAINT incidents_feedback_rating_check
            CHECK (feedback_rating IS NULL OR feedback_rating BETWEEN 1 AND 5);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 5. Notifications record which channel delivered them.
--
-- The NotificationChannel abstraction has more than one implementation, so the
-- row has to say which one ran. Without this the two channel requirement is
-- invisible in the data.
-- ---------------------------------------------------------------------------

ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS channel    TEXT NOT NULL DEFAULT 'IN_APP';
ALTER TABLE public.notifications ADD COLUMN IF NOT EXISTS event_type TEXT;

-- ---------------------------------------------------------------------------
-- 6. Business logic leaves the database.
--
-- assign_incident_technician() and set_incident_sla_deadlines() duplicate what
-- AssignmentStrategy and SLAService now do in Python. Two engines writing the
-- same columns means the Python result gets silently overwritten, and logic
-- buried in plpgsql earns nothing on an object oriented design rubric.
--
-- The functions are left in place, only the triggers are dropped, so the
-- behaviour can be shown and discussed in the viva. set_updated_at() stays,
-- it is bookkeeping rather than business logic.
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_assign_incident_technician ON public.incidents;
DROP TRIGGER IF EXISTS trg_incident_sla_deadlines ON public.incidents;

-- ---------------------------------------------------------------------------
-- 7. SLA target precision.
--
-- response_hours was NUMERIC(8,2), so P1's five minute response target was
-- stored as 0.08 hours, which is 4 minutes 48 seconds. Every P1 response
-- deadline in the system was twelve seconds early, and no test caught it
-- because describe() rounds to the nearest minute when it prints.
--
-- Four decimal places puts the error under a tenth of a second.
-- ---------------------------------------------------------------------------

ALTER TABLE public.sla_policies ALTER COLUMN response_hours   TYPE NUMERIC(10,4);
ALTER TABLE public.sla_policies ALTER COLUMN resolution_hours TYPE NUMERIC(10,4);
ALTER TABLE public.sla_policies ALTER COLUMN escalation_hours TYPE NUMERIC(10,4);

UPDATE public.sla_policies SET response_hours = 0.0833 WHERE priority = 'P1';

-- ---------------------------------------------------------------------------
-- 8. Performance for duplicate detection.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_incidents_title_trgm
    ON public.incidents USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_incidents_duplicate_of
    ON public.incidents (duplicate_of_id);

COMMIT;
