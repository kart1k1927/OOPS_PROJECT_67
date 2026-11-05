
-- seed


-- 1. SEED CATEGORIES (Dynamic Lookup Table)
INSERT INTO categories (name, description) VALUES
    ('Hardware', 'Issues related to physical computers, servers, printers, and peripherals'),
    ('Software', 'Application crashes, bugs, and OS level issues'),
    ('Network', 'Connectivity, Wi-Fi, VPN, and routing issues'),
    ('Database', 'Data corruption, query timeouts, and DB connection failures'),
    ('Cloud', 'AWS, Azure, or cloud infrastructure failures'),
    ('Security', 'Unauthorized access, malware, or vulnerability reports'),
    ('Authentication', 'Login failures, password resets, and SSO issues'),
    ('Application', 'Specific internal software application errors'),
    ('Storage', 'Disk space, SAN/NAS, and file server issues')
ON CONFLICT (name) DO NOTHING;


-- 2. SEED PROFILES (Users, Technicians, Admins)
INSERT INTO profiles (id, name, email, role, is_active) VALUES
    ('11111111-1111-1111-1111-111111111111', 'System Administrator', 'admin@company.com', 'ADMIN', true),
    ('22222222-2222-2222-2222-222222222222', 'John Doe (Technician)', 'john.tech@company.com', 'TECHNICIAN', true),
    ('33333333-3333-3333-3333-333333333333', 'Sarah Connor (Technician)', 'sarah.tech@company.com', 'TECHNICIAN', true),
    ('44444444-4444-4444-4444-444444444444', 'Alice Smith (Employee)', 'alice.emp@company.com', 'EMPLOYEE', true)
ON CONFLICT (id) DO NOTHING;


-- 3. SEED SERVICES
INSERT INTO services (id, name, description, business_criticality, is_active) VALUES
    ('a1111111-1111-1111-1111-111111111111', 'Corporate Email Portal', 'Microsoft 365 and Exchange mail servers', 5, true),
    ('a2222222-2222-2222-2222-222222222222', 'Internal VPN & Remote Access', 'GlobalProtect VPN gateway for remote work', 4, true),
    ('a3333333-3333-3333-3333-333333333333', 'Customer Payments API', 'Stripe & Gateway payment processing system', 5, true),
    ('a4444444-4444-4444-4444-444444444444', 'Internal Wiki & HR Portal', 'Confluence and internal documentation portal', 2, true)
ON CONFLICT (id) DO NOTHING;


-- 4. SEED SLA POLICIES (Priority Deadlines)
INSERT INTO sla_policies (priority, response_time_hours, resolution_time_hours, escalation_time_hours) VALUES
    ('P1', 1, 4, 2),   -- Critical: 1 hr response, 4 hrs resolution
    ('P2', 2, 8, 4),   -- High: 2 hrs response, 8 hrs resolution
    ('P3', 4, 24, 12), -- Medium: 4 hrs response, 24 hrs resolution
    ('P4', 8, 48, 24)  -- Low: 8 hrs response, 48 hrs resolution
ON CONFLICT (priority) DO NOTHING;