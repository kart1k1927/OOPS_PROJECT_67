-- 1. Profiles 
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('EMPLOYEE', 'TECHNICIAN', 'ADMIN')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Services 
CREATE TABLE services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    business_criticality SMALLINT CHECK (business_criticality BETWEEN 1 AND 5),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. SLA Policies 
CREATE TABLE sla_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id UUID REFERENCES services(id) ON DELETE CASCADE,
    priority_level TEXT NOT NULL CHECK (priority_level IN ('P1', 'P2', 'P3', 'P4')),
    response_target_mins INTEGER NOT NULL,
    resolution_target_mins INTEGER NOT NULL,
    warning_before_mins INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE (service_id, priority_level)
);

-- 4. Technician Skills 
CREATE TABLE technician_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    technician_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    experience_level SMALLINT CHECK (experience_level BETWEEN 1 AND 5),
    UNIQUE (technician_id, skill_name)
);

-- 5. Incidents 
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_id UUID REFERENCES profiles(id),
    service_id UUID REFERENCES services(id),
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    impact TEXT CHECK (impact IN ('Low', 'Medium', 'High')),
    urgency TEXT CHECK (urgency IN ('Low', 'Medium', 'High')),
    affected_users_count INTEGER DEFAULT 1,
    priority TEXT CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    status TEXT DEFAULT 'NEW' CHECK (status IN ('NEW', 'ASSIGNED', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'VERIFIED', 'CLOSED')),
    assigned_technician_id UUID REFERENCES profiles(id),
    assigned_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    response_deadline_at TIMESTAMPTZ,
    resolution_deadline_at TIMESTAMPTZ,
    response_sla_breached BOOLEAN DEFAULT FALSE,
    resolution_sla_breached BOOLEAN DEFAULT FALSE,
    resolution TEXT,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Incident Updates
CREATE TABLE incident_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    author_id UUID REFERENCES profiles(id),
    update_type TEXT NOT NULL,
    content TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES profiles(id),
    action TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    description TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- 8. Notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- Dynamic categories table
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Update incidents table to reference category_id
ALTER TABLE incidents DROP COLUMN IF EXISTS category;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES categories(id) ON DELETE SET NULL;