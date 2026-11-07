SELECT
    p.employee_code,
    u.email,
    p.role,
    p.is_active
FROM public.profiles AS p
JOIN auth.users AS u ON u.id = p.id
ORDER BY p.employee_code;