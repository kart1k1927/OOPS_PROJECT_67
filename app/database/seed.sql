


-- 1. CATEGORIES

INSERT INTO public.categories (name, description)
VALUES
    ('Hardware', 'Physical devices and computer equipment'),
    ('Software', 'Software errors and application problems'),
    ('Network', 'Connectivity and network infrastructure'),
    ('Database', 'Database access, performance and failures'),
    ('Cloud', 'Cloud infrastructure and hosted services'),
    ('Security', 'Security incidents and suspicious activity'),
    ('Authentication', 'Login and authentication problems'),
    ('Application', 'Business application incidents'),
    ('Storage', 'Storage capacity and file access problems')
ON CONFLICT (name) DO UPDATE
SET description = EXCLUDED.description;

-- 2. SERVICES
-- Business criticality ranges from 1 to 5.

INSERT INTO public.services
    (name, description, business_criticality, is_active)
VALUES
    (
        'Payment Application',
        'Payment processing and transaction services',
        5,
        TRUE
    ),
    (
        'Employee Portal',
        'Internal employee portal and self-service tools',
        3,
        TRUE
    ),
    (
        'Network Infrastructure',
        'Network connectivity and infrastructure',
        5,
        TRUE
    ),
    (
        'Email Service',
        'Corporate email and communication services',
        4,
        TRUE
    )
ON CONFLICT (name) DO UPDATE
SET
    description = EXCLUDED.description,
    business_criticality = EXCLUDED.business_criticality,
    is_active = EXCLUDED.is_active;

-- 3. SLA POLICIES
-- Durations are in hours.

INSERT INTO public.sla_policies
    (priority, response_hours, resolution_hours, escalation_hours)
VALUES
    ('P1', 0.0833, 0.50, 0.25),
    ('P2', 0.25,   2.00, 1.00),
    ('P3', 1.00,   8.00, 4.00),
    ('P4', 4.00,  24.00, 8.00)
ON CONFLICT (priority) DO UPDATE
SET
    response_hours = EXCLUDED.response_hours,
    resolution_hours = EXCLUDED.resolution_hours,
    escalation_hours = EXCLUDED.escalation_hours;

