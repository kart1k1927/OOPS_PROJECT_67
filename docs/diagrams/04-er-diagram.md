# Entity relationship diagram

Nine tables in PostgreSQL, as created by `schema.sql` and amended by
migration 002.

```mermaid
erDiagram
    PROFILES ||--o{ INCIDENTS : "reports"
    PROFILES ||--o{ INCIDENTS : "is assigned"
    PROFILES ||--o{ TECHNICIAN_SKILLS : "has"
    PROFILES ||--o{ INCIDENT_UPDATES : "writes"
    PROFILES ||--o{ AUDIT_LOGS : "acts in"
    PROFILES ||--o{ NOTIFICATIONS : "receives"

    CATEGORIES ||--o{ INCIDENTS : "classifies"
    CATEGORIES ||--o{ TECHNICIAN_SKILLS : "is a skill in"

    SERVICES ||--o{ INCIDENTS : "is affected by"

    SLA_POLICIES ||--o{ INCIDENTS : "sets targets for"

    INCIDENTS ||--o{ INCIDENT_UPDATES : "has history"
    INCIDENTS ||--o{ NOTIFICATIONS : "triggers"
    INCIDENTS ||--o| INCIDENTS : "may duplicate"

    PROFILES {
        uuid id PK
        text employee_code UK "EMP001, from a sequence"
        text full_name "added by migration 002"
        text email UK "added by migration 002"
        text password_hash "added by migration 002, PBKDF2"
        text role "EMPLOYEE, TECHNICIAN or ADMIN"
        boolean is_active
        integer max_workload "assignment ceiling"
        integer experience_level "1 to 5"
        timestamptz created_at
    }

    CATEGORIES {
        uuid id PK
        text name UK
        text description
        timestamptz created_at
    }

    SERVICES {
        uuid id PK
        text name UK
        text description
        integer business_criticality "1 to 5, feeds priority"
        boolean is_active
        timestamptz created_at
    }

    SLA_POLICIES {
        uuid id PK
        text priority UK "P1 to P4"
        numeric response_hours "widened to 10,4 by migration 002"
        numeric resolution_hours
        numeric escalation_hours
        timestamptz created_at
    }

    TECHNICIAN_SKILLS {
        uuid id PK
        uuid technician_id FK
        uuid category_id FK
        timestamptz created_at
    }

    INCIDENTS {
        uuid id PK
        uuid reporter_id FK
        uuid service_id FK
        uuid category_id FK
        uuid assigned_technician_id FK
        uuid duplicate_of_id FK "self reference"
        text title
        text description
        text impact "LOW, MEDIUM, HIGH"
        text urgency "LOW, MEDIUM, HIGH"
        integer affected_users_count
        text priority "P1 to P4, calculated"
        numeric priority_score "the computed score"
        text status "9 states, enforced in Python"
        integer escalation_level "0 to 3"
        timestamptz created_at
        timestamptz updated_at
        timestamptz first_response_at
        timestamptz acknowledged_at
        timestamptz resolved_at
        timestamptz verified_at
        timestamptz closed_at
        timestamptz response_deadline_at
        timestamptz resolution_deadline_at
        timestamptz escalation_deadline_at
        boolean response_breached
        boolean resolution_breached
        boolean escalation_breached
        text resolution_notes
        text closure_notes
        integer feedback_rating "1 to 5"
        text feedback_comment
    }

    INCIDENT_UPDATES {
        uuid id PK
        uuid incident_id FK
        uuid user_id FK
        text update_type "COMMENT, STATUS_CHANGE, ASSIGNMENT, SYSTEM"
        text message
        text old_status
        text new_status
        timestamptz created_at
    }

    AUDIT_LOGS {
        uuid id PK
        uuid actor_id FK
        text action
        text entity_type
        uuid entity_id
        jsonb details
        timestamptz created_at
    }

    NOTIFICATIONS {
        uuid id PK
        uuid user_id FK
        uuid incident_id FK
        text title
        text message
        text channel "IN_APP, EMAIL or SMS"
        text event_type
        boolean is_read
        timestamptz created_at
    }
```

## Design notes

**`PROFILES` has two relationships to `INCIDENTS`.** One as reporter, one as
assigned technician. Both are foreign keys to the same table, which is why the
Supabase queries have to name the constraint explicitly
(`incidents!incidents_reporter_id_fkey`) rather than letting it infer the join.

**`SLA_POLICIES` relates to `INCIDENTS` through the priority value**, not a
foreign key. Priority is a four value domain, so the policy is looked up by it.
This keeps an incident's priority meaningful even if a policy row is edited.

**`INCIDENTS.duplicate_of_id` is a self reference**, nullable and
`ON DELETE SET NULL`. The duplicate detector writes it; nothing depends on it
being present.

**Three sets of timestamps are stored rather than derived.** The lifecycle
stamps (`acknowledged_at` through `closed_at`), the three deadlines, and the
three breach booleans. The deadlines could be computed from `created_at` plus
the policy, but storing them means a policy edit does not silently move the
deadline on an incident that was already running under the old one.

**Row level security is enabled on every table.** The backend connects with the
service role key and authorises in Python, where the object model can express
it; RLS remains as a second line in case anything else ever connects.

**Indexes** are on `incidents(created_at, status, priority, reporter_id,
assigned_technician_id, service_id)`, on `incident_updates(incident_id)`, on
`audit_logs(created_at)`, on `notifications(user_id)`, and a GIN trigram index
on `incidents(title)` for duplicate detection.
