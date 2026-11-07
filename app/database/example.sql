
INSERT INTO public.profiles (id, role)
SELECT u.id,
       CASE u.email
           WHEN 'admin@company.com' THEN 'ADMIN'
           WHEN 'john.tech@company.com' THEN 'TECHNICIAN'
           WHEN 'sarah.tech@company.com' THEN 'TECHNICIAN'
           WHEN 'alice.emp@company.com' THEN 'EMPLOYEE'
       END
FROM auth.users AS u
WHERE u.email IN (
    'admin@company.com',
    'john.tech@company.com',
    'sarah.tech@company.com',
    'alice.emp@company.com'
)
ON CONFLICT (id) DO UPDATE
SET role = EXCLUDED.role;
