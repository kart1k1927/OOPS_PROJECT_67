

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. EMPLOYEE CODE SEQUENCE

CREATE SEQUENCE IF NOT EXISTS public.employee_code_seq
    START WITH 1
    INCREMENT BY 1;

-- 2. PROFILES
-- UUID remains linked to Supabase Auth.
-- employee_code is the short ID displayed in the UI.

CREATE TABLE public.profiles (
    id UUID PRIMARY KEY
        REFERENCES auth.users(id) ON DELETE CASCADE,

    employee_code TEXT UNIQUE NOT NULL
        DEFAULT (
            'EMP' || LPAD(
                NEXTVAL('public.employee_code_seq')::TEXT,
                3,
                '0'
            )
        ),

    role TEXT NOT NULL DEFAULT 'EMPLOYEE'
        CHECK (role IN ('EMPLOYEE', 'TECHNICIAN', 'ADMIN')),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. CATEGORIES

CREATE TABLE public.categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. SERVICES
-- Business criticality: 1 = lowest, 5 = highest.

CREATE TABLE public.services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    business_criticality INTEGER NOT NULL DEFAULT 3
        CHECK (business_criticality BETWEEN 1 AND 5),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. SLA POLICIES
-- All SLA durations are measured in HOURS.

CREATE TABLE public.sla_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    priority TEXT NOT NULL UNIQUE
        CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),

    response_hours NUMERIC(8,2) NOT NULL
        CHECK (response_hours > 0),

    resolution_hours NUMERIC(8,2) NOT NULL
        CHECK (resolution_hours > 0),

    escalation_hours NUMERIC(8,2) NOT NULL
        CHECK (escalation_hours > 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. TECHNICIAN SKILLS

CREATE TABLE public.technician_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    technician_id UUID NOT NULL
        REFERENCES public.profiles(id) ON DELETE CASCADE,

    category_id UUID NOT NULL
        REFERENCES public.categories(id) ON DELETE CASCADE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (technician_id, category_id)
);

-- 7. INCIDENTS
-- Keep category_id as requested.

CREATE TABLE public.incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    reporter_id UUID NOT NULL
        REFERENCES public.profiles(id),

    service_id UUID REFERENCES public.services(id),

    category_id UUID REFERENCES public.categories(id),

    title TEXT NOT NULL,
    description TEXT,

    impact TEXT NOT NULL DEFAULT 'MEDIUM'
        CHECK (impact IN ('LOW', 'MEDIUM', 'HIGH')),

    urgency TEXT NOT NULL DEFAULT 'MEDIUM'
        CHECK (urgency IN ('LOW', 'MEDIUM', 'HIGH')),

    affected_users_count INTEGER NOT NULL DEFAULT 1
        CHECK (affected_users_count >= 1),

    priority TEXT NOT NULL DEFAULT 'P3'
        CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),

    status TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (
            status IN (
                'OPEN',
                'ASSIGNED',
                'IN_PROGRESS',
                'PENDING',
                'RESOLVED',
                'CLOSED'
            )
        ),

    assigned_technician_id UUID
        REFERENCES public.profiles(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    first_response_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,

    response_deadline_at TIMESTAMPTZ,
    resolution_deadline_at TIMESTAMPTZ,
    escalation_deadline_at TIMESTAMPTZ,

    response_breached BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_breached BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_breached BOOLEAN NOT NULL DEFAULT FALSE
);

-- 8. INCIDENT UPDATES

CREATE TABLE public.incident_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    incident_id UUID NOT NULL
        REFERENCES public.incidents(id) ON DELETE CASCADE,

    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,

    update_type TEXT NOT NULL DEFAULT 'COMMENT'
        CHECK (
            update_type IN (
                'COMMENT',
                'STATUS_CHANGE',
                'ASSIGNMENT',
                'SYSTEM'
            )
        ),

    message TEXT NOT NULL,

    old_status TEXT,
    new_status TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. AUDIT LOGS

CREATE TABLE public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    actor_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,

    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. NOTIFICATIONS

CREATE TABLE public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES public.profiles(id) ON DELETE CASCADE,

    incident_id UUID
        REFERENCES public.incidents(id) ON DELETE CASCADE,

    title TEXT NOT NULL,
    message TEXT NOT NULL,

    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. INDEXES
-- All referenced created_at columns exist above.

CREATE INDEX idx_incidents_created_at
    ON public.incidents(created_at DESC);

CREATE INDEX idx_incidents_status
    ON public.incidents(status);

CREATE INDEX idx_incidents_priority
    ON public.incidents(priority);

CREATE INDEX idx_incidents_reporter
    ON public.incidents(reporter_id);

CREATE INDEX idx_incidents_assignee
    ON public.incidents(assigned_technician_id);

CREATE INDEX idx_incidents_service
    ON public.incidents(service_id);

CREATE INDEX idx_incident_updates_incident
    ON public.incident_updates(incident_id, created_at DESC);

CREATE INDEX idx_audit_logs_created
    ON public.audit_logs(created_at DESC);

CREATE INDEX idx_notifications_user
    ON public.notifications(user_id, created_at DESC);

CREATE INDEX idx_technician_skills_category
    ON public.technician_skills(category_id);

-- 12. UPDATED_AT TRIGGER

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_incidents_updated_at
BEFORE UPDATE ON public.incidents
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();

-- 13. AUTOMATIC SLA DEADLINES

CREATE OR REPLACE FUNCTION public.set_incident_sla_deadlines()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_response NUMERIC;
    v_resolution NUMERIC;
    v_escalation NUMERIC;
BEGIN
    SELECT
        response_hours,
        resolution_hours,
        escalation_hours
    INTO
        v_response,
        v_resolution,
        v_escalation
    FROM public.sla_policies
    WHERE priority = NEW.priority;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No SLA policy configured for priority %',
            NEW.priority;
    END IF;

    IF TG_OP = 'INSERT'
       OR NEW.priority IS DISTINCT FROM OLD.priority
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN

        NEW.response_deadline_at :=
            NEW.created_at + (v_response * INTERVAL '1 hour');

        NEW.resolution_deadline_at :=
            NEW.created_at + (v_resolution * INTERVAL '1 hour');

        NEW.escalation_deadline_at :=
            NEW.created_at + (v_escalation * INTERVAL '1 hour');
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_incident_sla_deadlines
BEFORE INSERT OR UPDATE OF priority, created_at
ON public.incidents
FOR EACH ROW
EXECUTE FUNCTION public.set_incident_sla_deadlines();

-- 14. AUTOMATIC TECHNICIAN ASSIGNMENT
-- Assigns the active technician with the lowest workload.
-- An explicitly supplied technician is preserved.

CREATE OR REPLACE FUNCTION public.assign_incident_technician()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF NEW.assigned_technician_id IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT p.id
    INTO NEW.assigned_technician_id
    FROM public.profiles AS p
    WHERE p.role = 'TECHNICIAN'
      AND p.is_active = TRUE
    ORDER BY
        (
            SELECT COUNT(*)
            FROM public.incidents AS i
            WHERE i.assigned_technician_id = p.id
              AND i.status IN (
                  'ASSIGNED',
                  'IN_PROGRESS',
                  'PENDING'
              )
        ) ASC,
        p.created_at ASC,
        p.id ASC
    LIMIT 1;

    IF NEW.assigned_technician_id IS NOT NULL
       AND NEW.status = 'OPEN' THEN
        NEW.status := 'ASSIGNED';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_assign_incident_technician
BEFORE INSERT ON public.incidents
FOR EACH ROW
EXECUTE FUNCTION public.assign_incident_technician();

-- 15. REFRESH SLA BREACH FLAGS
-- Schedule this function periodically using Supabase
-- Cron or another scheduler. It does not run by itself.

CREATE OR REPLACE FUNCTION public.refresh_incident_sla_breaches()
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.incidents
    SET
        response_breached =
            first_response_at IS NULL
            AND response_deadline_at < NOW(),

        resolution_breached =
            resolved_at IS NULL
            AND resolution_deadline_at < NOW(),

        escalation_breached =
            status NOT IN ('RESOLVED', 'CLOSED')
            AND escalation_deadline_at < NOW()

    WHERE
        (
            first_response_at IS NULL
            AND response_deadline_at < NOW()
        )
        OR
        (
            resolved_at IS NULL
            AND resolution_deadline_at < NOW()
        )
        OR
        (
            status NOT IN ('RESOLVED', 'CLOSED')
            AND escalation_deadline_at < NOW()
        );
END;
$$;

-- 16. HELPER FUNCTIONS FOR RLS
-- SECURITY DEFINER avoids recursive profiles RLS checks.

CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS TEXT
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT p.role
    FROM public.profiles AS p
    WHERE p.id = (SELECT auth.uid())
      AND p.is_active = TRUE
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT COALESCE(
        public.current_user_role() = 'ADMIN',
        FALSE
    );
$$;

CREATE OR REPLACE FUNCTION public.is_technician()
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT COALESCE(
        public.current_user_role() = 'TECHNICIAN',
        FALSE
    );
$$;

-- 17. ENABLE ROW LEVEL SECURITY

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.services ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sla_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.technician_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incident_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- 18. PROFILES POLICIES

CREATE POLICY profiles_select
ON public.profiles
FOR SELECT TO authenticated
USING (
    id = (SELECT auth.uid())
    OR (SELECT public.is_admin())
);

CREATE POLICY profiles_insert_self
ON public.profiles
FOR INSERT TO authenticated
WITH CHECK (
    id = (SELECT auth.uid())
    AND role = 'EMPLOYEE'
);

CREATE POLICY profiles_update_self
ON public.profiles
FOR UPDATE TO authenticated
USING (id = (SELECT auth.uid()))
WITH CHECK (
    id = (SELECT auth.uid())
    AND role = 'EMPLOYEE'
);

CREATE POLICY profiles_admin_all
ON public.profiles
FOR ALL TO authenticated
USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));

-- 19. REFERENCE DATA POLICIES

CREATE POLICY categories_read
ON public.categories
FOR SELECT TO authenticated
USING (TRUE);

CREATE POLICY categories_admin_manage
ON public.categories
FOR ALL TO authenticated
USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));

CREATE POLICY services_read
ON public.services
FOR SELECT TO authenticated
USING (TRUE);

CREATE POLICY services_admin_manage
ON public.services
FOR ALL TO authenticated
USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));

CREATE POLICY sla_policies_read
ON public.sla_policies
FOR SELECT TO authenticated
USING (TRUE);

CREATE POLICY sla_policies_admin_manage
ON public.sla_policies
FOR ALL TO authenticated
USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));

-- 20. TECHNICIAN SKILLS POLICIES

CREATE POLICY skills_read
ON public.technician_skills
FOR SELECT TO authenticated
USING (
    technician_id = (SELECT auth.uid())
    OR (SELECT public.is_admin())
);

CREATE POLICY skills_admin_manage
ON public.technician_skills
FOR ALL TO authenticated
USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));


-- 21. INCIDENT POLICIES
-- Employees can see their own incidents.
-- Technicians can see incidents for operational work.
-- Only technicians/admins can update incidents.

CREATE POLICY incidents_read
ON public.incidents
FOR SELECT TO authenticated
USING (
    reporter_id = (SELECT auth.uid())
    OR assigned_technician_id = (SELECT auth.uid())
    OR (SELECT public.is_technician())
    OR (SELECT public.is_admin())
);

CREATE POLICY incidents_create
ON public.incidents
FOR INSERT TO authenticated
WITH CHECK (
    reporter_id = (SELECT auth.uid())
);

CREATE POLICY incidents_technician_update
ON public.incidents
FOR UPDATE TO authenticated
USING (
    (SELECT public.is_technician())
    OR (SELECT public.is_admin())
)
WITH CHECK (
    (SELECT public.is_technician())
    OR (SELECT public.is_admin())
);

CREATE POLICY incidents_admin_delete
ON public.incidents
FOR DELETE TO authenticated
USING ((SELECT public.is_admin()));

-- 22. INCIDENT UPDATE POLICIES

CREATE POLICY incident_updates_read
ON public.incident_updates
FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM public.incidents AS i
        WHERE i.id = incident_id
          AND (
              i.reporter_id = (SELECT auth.uid())
              OR i.assigned_technician_id = (SELECT auth.uid())
              OR (SELECT public.is_technician())
              OR (SELECT public.is_admin())
          )
    )
);

CREATE POLICY incident_updates_create
ON public.incident_updates
FOR INSERT TO authenticated
WITH CHECK (
    user_id = (SELECT auth.uid())
    AND EXISTS (
        SELECT 1
        FROM public.incidents AS i
        WHERE i.id = incident_id
          AND (
              i.reporter_id = (SELECT auth.uid())
              OR i.assigned_technician_id = (SELECT auth.uid())
              OR (SELECT public.is_technician())
              OR (SELECT public.is_admin())
          )
    )
);

CREATE POLICY incident_updates_admin_delete
ON public.incident_updates
FOR DELETE TO authenticated
USING ((SELECT public.is_admin()));

-- 23. AUDIT LOG POLICIES
-- Client users may read logs only if they are admins.
-- Inserts are intended to be performed by trusted backend
-- code using the Supabase service role.

CREATE POLICY audit_logs_admin_read
ON public.audit_logs
FOR SELECT TO authenticated
USING ((SELECT public.is_admin()));


-- 24. NOTIFICATION POLICIES


CREATE POLICY notifications_read_own
ON public.notifications
FOR SELECT TO authenticated
USING (
    user_id = (SELECT auth.uid())
    OR (SELECT public.is_admin())
);

CREATE POLICY notifications_update_own
ON public.notifications
FOR UPDATE TO authenticated
USING (user_id = (SELECT auth.uid()))
WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY notifications_admin_manage
ON public.notifications
FOR ALL TO authenticated
USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));


-- 25. TABLE PRIVILEGES
-- RLS policies and SQL privileges both apply.


GRANT USAGE ON SCHEMA public TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
ON public.profiles,
   public.categories,
   public.services,
   public.sla_policies,
   public.technician_skills,
   public.incidents,
   public.incident_updates,
   public.notifications
TO authenticated;

GRANT SELECT
ON public.audit_logs
TO authenticated;

GRANT USAGE, SELECT
ON SEQUENCE public.employee_code_seq
TO authenticated;


