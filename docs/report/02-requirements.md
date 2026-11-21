# 2. Requirements Specification

## 2.1 User roles

| Role | Class | Lands on | Sees |
|---|---|---|---|
| Employee | `Employee` | `/my-incidents` | Only incidents they reported |
| Technician | `Technician` | `/queue` | Incidents assigned to them, plus unassigned ones |
| Administrator | `Administrator` | `/operations` | Everything |

Scoping is polymorphic, not conditional. `User.can_view()` is answered
differently by each subclass, and `IncidentService.search_for()` narrows the
query based on the type of the user it is given. Adding a Team Lead role means
adding a class.

## 2.2 Functional requirements

### FR-1 User management

| ID | Requirement | Where |
|---|---|---|
| FR-1.1 | A visitor can register as an employee with name, email and password | `AuthService.register` |
| FR-1.2 | Passwords are at least 8 characters and mix letters and numbers | `security.validate_password_strength` |
| FR-1.3 | A registered user can sign in and receives a session valid for 12 hours | `AuthService.authenticate` |
| FR-1.4 | An unknown email and a wrong password produce an identical message | `InvalidCredentialsError` |
| FR-1.5 | A deactivated account cannot sign in | `InactiveAccountError` |
| FR-1.6 | An administrator can change any user's role and activate or deactivate them | `/admin/people` |
| FR-1.7 | An administrator can set a technician's skills, capacity and experience | `/admin/people` |

### FR-2 Incident management

| ID | Requirement | Where |
|---|---|---|
| FR-2.1 | An employee can report an incident with title, description, service, category, impact, urgency and affected user count | `IncidentService.report` |
| FR-2.2 | A title must be 8 to 160 characters | `Incident._validated_title` |
| FR-2.3 | Affected users must be a whole number from 1 to 100000 | `Incident._validated_affected` |
| FR-2.4 | Every incident receives a unique reference of the form `INC-8F51D7` | `Incident.reference` |
| FR-2.5 | Any user can view an incident they are entitled to see | `User.can_view` |
| FR-2.6 | A technician can acknowledge, start, hold, resume and resolve an assigned incident | `Technician.available_actions` |
| FR-2.7 | A resolution must be at least 10 characters | `Incident.resolve` |
| FR-2.8 | A reporter can confirm a fix, reopen it, close it and rate it 1 to 5 | `Employee.available_actions` |
| FR-2.9 | Any entitled user can add a note to an open incident | `Incident.add_note` |
| FR-2.10 | An administrator can assign, reassign, change priority and escalate | `Administrator.available_actions` |

### FR-3 Classification and prioritisation

| ID | Requirement | Where |
|---|---|---|
| FR-3.1 | Incidents are classified into at least 9 categories | `categories` table |
| FR-3.2 | New categories can be added without changing code | `/admin/catalog` |
| FR-3.3 | Priority is calculated from impact, urgency, business criticality and affected users | `WeightedPriorityStrategy` |
| FR-3.4 | The calculation is shown to the reporter live, as they fill the form | `report.js` |
| FR-3.5 | At least two priority algorithms exist and are interchangeable | `WeightedPriorityStrategy`, `MatrixPriorityStrategy` |
| FR-3.6 | Priority maps to P1 Critical, P2 High, P3 Medium, P4 Low | `Priority` |
| FR-3.7 | Changing priority recalculates the SLA deadlines in the same operation | `Incident.apply_priority` |

### FR-4 Technician assignment

| ID | Requirement | Where |
|---|---|---|
| FR-4.1 | At least two assignment strategies exist | Four do |
| FR-4.2 | The active strategy can be changed at runtime without a restart | `/admin/settings` |
| FR-4.3 | No strategy assigns to an inactive technician | `AssignmentStrategy.available` |
| FR-4.4 | No strategy assigns past a technician's workload ceiling | `Technician.has_capacity` |
| FR-4.5 | If nobody is available the incident is still created, unassigned, with the reason recorded | `IncidentService.report` |
| FR-4.6 | An administrator can override the strategy and assign manually | `IncidentService.assign` |

### FR-5 SLA management

| ID | Requirement | Where |
|---|---|---|
| FR-5.1 | Each priority has response, resolution and escalation targets | `sla_policies` |
| FR-5.2 | Deadlines are derived from the policy when an incident is created | `SLATracker.recalculate` |
| FR-5.3 | SLA state is monitored continuously, not on demand | `SLAService.sweep`, every 60s |
| FR-5.4 | An incident past 75 percent of its window is flagged at risk and warned once | `AT_RISK_FRACTION` |
| FR-5.5 | An incident past its deadline is flagged breached and notified | `SLAService.sweep` |
| FR-5.6 | An administrator can trigger a sweep immediately | `/admin/sla/sweep` |
| FR-5.7 | SLA targets are editable by an administrator | `/admin/catalog` |

### FR-6 Lifecycle

| ID | Requirement | Where |
|---|---|---|
| FR-6.1 | The lifecycle is OPEN, CLASSIFIED, ASSIGNED, ACKNOWLEDGED, IN_PROGRESS, PENDING, RESOLVED, VERIFIED, CLOSED | `Status` |
| FR-6.2 | Illegal transitions are refused, OPEN to CLOSED specifically | `IncidentState.permits` |
| FR-6.3 | A refusal states what transitions are legal from here | `IncidentState.hint` |
| FR-6.4 | CLOSED is terminal | `ClosedState` |
| FR-6.5 | Entering a state stamps the relevant timestamp automatically | `IncidentState.on_enter` |

### FR-7 Notifications

| ID | Requirement | Where |
|---|---|---|
| FR-7.1 | At least two notification mechanisms exist | Three do: in-app, email, SMS |
| FR-7.2 | Notifications fire on created, assigned, acknowledged, priority changed, SLA approaching, SLA violated, escalated, resolved, verified, closed | `NotificationObserver.SUBSCRIBED` |
| FR-7.3 | Which channels run depends on priority | `NotificationService.channels_for` |
| FR-7.4 | A failed channel does not fail the operation | `NotificationService.dispatch` |
| FR-7.5 | The user who performed an action is not notified about it | `NotificationObserver._recipients` |
| FR-7.6 | Adding a channel requires no change to existing code | `NotificationChannel` |

### FR-8 Audit

| ID | Requirement | Where |
|---|---|---|
| FR-8.1 | Every incident keeps a complete history | `incident_updates` |
| FR-8.2 | Each entry records timestamp, user, action, incident, previous state, new state and description | `AuditLogObserver` |
| FR-8.3 | The trail is written by an observer, so it cannot drift from what happened | `EventBus.publish` |
| FR-8.4 | Only an administrator can read the full audit log | `Administrator.can_view_audit_log` |

### FR-9 Search and reporting

| ID | Requirement | Where |
|---|---|---|
| FR-9.1 | At least five search criteria. Nine exist and they combine | `IncidentQuery` |
| FR-9.2 | Criteria are free text, reference, status, priority, category, service, technician, SLA state and date range | `pages._query_from` |
| FR-9.3 | Four sort orders: priority, newest, recently updated, SLA deadline | `IncidentRepository.search` |
| FR-9.4 | The dashboard reports total, open, P1 open, resolved and SLA violations | `ReportingService.overview` |
| FR-9.5 | Technician workload, service analysis and category breakdown are reported | `ReportingService` |

### FR-10 Intelligent features

| ID | Requirement | Where |
|---|---|---|
| FR-10.1 | Duplicate detection on report, flagging rather than blocking | `DuplicateDetector.find` |
| FR-10.2 | Incident correlation by affected service | `DuplicateDetector.correlate` |
| FR-10.3 | Automatic categorization from the description | `IncidentCategorizer` |
| FR-10.4 | Automatic escalation through four tiers | `EscalationEngine` |
| FR-10.5 | SLA risk prediction with stated reasoning | `SLARiskDetector` |
| FR-10.6 | Technician recommendation with stated reasoning | `TechnicianRecommender` |
| FR-10.7 | Suggested resolutions from similar past incidents | `ResolutionRecommender` |

## 2.3 Non functional requirements

| ID | Requirement | How it is met |
|---|---|---|
| NFR-1 | **Maintainability.** Adding a strategy, state, role or channel must not require editing existing code | Abstract base classes with registries; verified by the fact that four assignment strategies share no code path |
| NFR-2 | **Testability.** The test suite must run without infrastructure | Repository pattern with an in-memory implementation; 71 tests, no database, no keys, no network |
| NFR-3 | **Security.** Passwords hashed, sessions signed, authorisation server side | PBKDF2-HMAC-SHA256 at 390,000 iterations; JWT in an HttpOnly cookie; `User.require_action` on every write |
| NFR-4 | **Usability.** A technician must see what to do next without reading documentation | The action panel shows only permitted actions, so there are no disabled buttons to interpret |
| NFR-5 | **Reliability.** A failure in a secondary concern must not lose primary work | Observers that raise are logged and skipped; audit write failures do not block sign in; transient database drops are retried |
| NFR-6 | **Performance.** Incident lists must render promptly at campus scale | Indexed on status, priority, reporter, assignee, service and created_at; a GIN trigram index supports duplicate detection |
| NFR-7 | **Auditability.** Every state change must be attributable | Observer driven audit log, 9 recorded event types |
| NFR-8 | **Accessibility.** Keyboard reachable, readable contrast | Visible focus ring on every interactive element; status conveyed by colour **and** a word, never colour alone |
| NFR-9 | **Portability.** Must run on any platform that runs a Python process | Dockerfile, Procfile and render.yaml, all using the same start command |

## 2.4 Business rules

| ID | Rule |
|---|---|
| BR-1 | An incident may only move between states the state machine permits. OPEN to CLOSED is refused. |
| BR-2 | CLOSED is final. There is no transition out of it. |
| BR-3 | Priority and SLA deadlines change together or not at all. |
| BR-4 | A technician at their workload ceiling is never assigned more work automatically. |
| BR-5 | An inactive technician is never assigned work. |
| BR-6 | An inactive service cannot have incidents reported against it. |
| BR-7 | A resolution requires at least 10 characters of explanation. |
| BR-8 | Feedback can only be given after an incident is resolved, and must be 1 to 5. |
| BR-9 | An employee may only view incidents they reported. |
| BR-10 | A technician may only act on incidents assigned to them. |
| BR-11 | A reporter may close an incident only after verifying the fix. |
| BR-12 | An incident with no SLA policy for its priority cannot be created. |
| BR-13 | An incident cannot be marked a duplicate of itself. |
| BR-14 | The person who performs an action is not notified about it. |
| BR-15 | Escalation widens who is informed. It never reassigns the incident. |
