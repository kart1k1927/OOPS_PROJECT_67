-- Quick sanity queries. Paste into the Supabase SQL editor.
-- Updated for migration 002: identity now lives in public.profiles, so these
-- no longer join against auth.users.

-- 1. Who exists, and what can they do
SELECT employee_code, full_name, email, role, is_active, max_workload, experience_level
FROM public.profiles
ORDER BY role, employee_code;

-- 2. Technician skills
SELECT p.employee_code, p.full_name, string_agg(c.name, ', ' ORDER BY c.name) AS skills
FROM public.profiles p
LEFT JOIN public.technician_skills ts ON ts.technician_id = p.id
LEFT JOIN public.categories c ON c.id = ts.category_id
WHERE p.role = 'TECHNICIAN'
GROUP BY p.employee_code, p.full_name
ORDER BY p.employee_code;

-- 3. Incident overview, the numbers the admin dashboard shows
SELECT status, priority, COUNT(*) AS count
FROM public.incidents
GROUP BY status, priority
ORDER BY priority, status;

-- 4. SLA position of everything still open
SELECT
    'INC-' || UPPER(LEFT(REPLACE(id::TEXT, '-', ''), 6)) AS reference,
    priority,
    status,
    resolution_deadline_at,
    resolution_breached,
    escalation_level
FROM public.incidents
WHERE status NOT IN ('RESOLVED', 'VERIFIED', 'CLOSED')
ORDER BY priority, resolution_deadline_at;

-- 5. The audit trail for one incident, in order
-- Replace the reference with the one you want to inspect.
SELECT created_at, action, details->>'description' AS description
FROM public.audit_logs
WHERE details->>'reference' = 'INC-XXXXXX'
ORDER BY created_at;

-- 6. Confirm the triggers that moved into Python are gone
SELECT tgname
FROM pg_trigger
WHERE tgrelid = 'public.incidents'::regclass AND NOT tgisinternal;
-- Expect only trg_incidents_updated_at.
