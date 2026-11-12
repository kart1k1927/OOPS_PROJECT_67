<a id="readme-top"></a>

# Team plan and work split

> Written 2026-11-11, before implementation. Kept because the ownership table,
> the schedule and the Definition of Done are all material for the report.
> For how to install and run the application, see the README.
> For what is actually built, see the README and `docs/design-system.md`.

# I-ITSM - Intelligent IT Service Management & Incident Resolution System

**CS F213 / MAC F212 - Object Oriented Programming, Semester I, 2026-2027**
**Group 67** · Repository: <https://github.com/kart1k1927/OOPS_PROJECT_67>

A web application that manages the complete lifecycle of an IT incident:
**Report → Classify → Prioritize → Assign → Investigate → Resolve → Verify → Close.**

**Hard deadline: 22 November 2026** (report PDF + 15-20 min demo video, file named `67_OOP_S1_2025-2026_Project`).

---

<details>
<summary>Table of Contents</summary>

1. [Tech Stack](#tech-stack)
2. [Team & Ownership](#team--ownership)
3. [Target Architecture](#target-architecture)
4. [Interface Contracts](#interface-contracts-freeze-these-first)
5. [Design Patterns](#design-patterns-we-implement)
6. [Work Breakdown](#work-breakdown)
7. [Schedule](#schedule)
8. [Known Breakages](#known-breakages-to-fix-first)
9. [Getting Started](#getting-started)
10. [Git Workflow](#git-workflow)
11. [Definition of Done](#definition-of-done)

</details>

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Backend / API | FastAPI + Uvicorn |
| Frontend | Jinja2 server-rendered templates + vanilla JS + Bootstrap 5 |
| Database | PostgreSQL (Supabase), accessed via `supabase-py` |
| Auth | Supabase Auth + JWT (PyJWT), role-based authorization |
| Architecture | Layered: Presentation → API → Service → Domain → Repository → Database |

Every one of these choices has to be defended in the Technology Selection Report (9 questions, see
[Work Breakdown](#work-breakdown)). "We already knew it" is explicitly called out in the problem
statement as *not* an acceptable justification.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Team & Ownership

Five members. Each person owns a vertical slice plus a documentation deliverable. **Everyone must
understand the whole system** - the evaluator can ask any member about any module, and the group
gets a single shared score.

| Member | Role | Owns (code) | Owns (deliverable) |
|---|---|---|---|
| **Amith** | Lead / Domain & OOP Core | `app/domain/`, `app/core/exceptions.py`, integration & release | Architecture diagram, **Class diagram**, Technology Selection Report, final PDF assembly |
| **Inian** | Backend API & Security | `app/api/routers/auth.py`, `incidents.py`, `app/core/security.py`, exception handlers | Use Case diagram, **Test case document (15+ cases)** |
| **Anirudh** | Frontend & UX | `app/templates/`, `app/static/`, `app/api/routers/pages.py` | Requirements Specification, video recording & editing |
| **Lokith** | Data & Persistence | `app/database/`, `app/repositories/`, `app/services/sla_service.py`, `admin.py`, `technicians.py` | **ER diagram** + Database Design document |
| **Kartik** | Intelligent & Automated Features | `app/services/intelligence/`, `app/services/notification_service.py`, observers | Problem Analysis, write-up of the intelligence algorithms |

**File ownership is a merge-conflict rule, not a wall.** Touch someone else's file → tell them in the
group chat before you push. `app/main.py` and `app/database/schema.sql` are shared; change them only
in a dedicated commit with a clear message.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Target Architecture

```
app/
├── main.py                       # app factory, router + template + exception-handler wiring   [SHARED]
├── core/
│   ├── config.py                 # settings loaded from .env                                   [Amith]
│   ├── security.py               # JWT issue/verify, current_user + require_role dependencies  [Inian]
│   └── exceptions.py             # custom exception hierarchy                                  [Amith]
├── domain/                                                                                   # [Amith]
│   ├── enums.py                  # Role, Status, Priority, Impact, Urgency
│   ├── users.py                  # User (abstract) → Employee / Technician / Admin
│   ├── incident.py               # Incident aggregate root
│   ├── states.py                 # State pattern: OpenState, AssignedState, ... ClosedState
│   ├── priority.py               # PriorityStrategy (abstract) + implementations
│   ├── assignment.py             # AssignmentStrategy (abstract) + implementations
│   ├── events.py                 # Subject / Observer base classes, IncidentEvent
│   └── factories.py              # IncidentFactory, UserFactory, NotificationFactory
├── repositories/                                                                             # [Lokith]
│   ├── base.py                   # Repository abstract base (add/get/list/update/delete)
│   ├── incident_repo.py          # + search() with 5+ filter criteria
│   ├── user_repo.py
│   ├── service_repo.py
│   └── audit_repo.py
├── services/
│   ├── incident_service.py       # use-case orchestration                                     [Amith+Inian]
│   ├── notification_service.py   # NotificationChannel abstraction, 2+ channels               [Kartik]
│   ├── sla_service.py            # deadline calc, breach sweep, escalation checks             [Lokith]
│   └── intelligence/                                                                         # [Kartik]
│       ├── duplicate_detector.py
│       ├── categorizer.py
│       ├── escalation_engine.py
│       ├── sla_risk.py
│       └── recommender.py
├── api/routers/                  # thin HTTP layer - no business logic here
├── templates/                                                                                # [Anirudh]
├── static/                                                                                   # [Anirudh]
└── database/                     # schema.sql, seed.sql, migrations                          [Lokith]
```

**Hard rule: business logic lives in `domain/` and `services/`, not in routers and not in SQL
triggers.** This is an OOP course project - logic hidden inside plpgsql earns zero OOP marks. The
existing triggers (`assign_incident_technician`, `set_incident_sla_deadlines`) get demoted to a
safety net; Python is the source of truth. Document that decision in the report, don't just delete
them silently.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Interface Contracts (freeze these first)

Agreed on **day 1** so all five people can build in parallel against stubs. Nobody changes a
signature below without telling the group.

```python
# domain/assignment.py
class AssignmentStrategy(ABC):
    @abstractmethod
    def select(self, incident: Incident, technicians: list[Technician]) -> Technician | None: ...

# domain/priority.py
class PriorityStrategy(ABC):
    @abstractmethod
    def calculate(self, incident: Incident, service: Service) -> Priority: ...

# domain/states.py
class IncidentState(ABC):
    @abstractmethod
    def allowed_transitions(self) -> set[Status]: ...
    @abstractmethod
    def on_enter(self, incident: Incident) -> None: ...

# domain/events.py
class Observer(ABC):
    @abstractmethod
    def notify(self, event: IncidentEvent) -> None: ...

# repositories/base.py
class Repository(ABC, Generic[T]):
    @abstractmethod
    def add(self, entity: T) -> T: ...
    @abstractmethod
    def get(self, entity_id: UUID) -> T | None: ...
    @abstractmethod
    def list(self, **filters) -> list[T]: ...
    @abstractmethod
    def update(self, entity: T) -> T: ...

# services/notification_service.py
class NotificationChannel(ABC):
    @abstractmethod
    def send(self, user: User, title: str, message: str) -> None: ...
```

Everyone writes against the abstract class. Lokith's repositories can return fakes for the first two
days so Inian and Kartik aren't blocked on the database.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Design Patterns We Implement

Minimum required is two. We ship five, because "Technical Depth" is 15 marks and the patterns are
the cheapest way to earn them.

| Pattern | Where | Why | Owner |
|---|---|---|---|
| **State** | `domain/states.py` - incident lifecycle | Spec demands invalid transitions be *prevented* (`OPEN → CLOSED` must fail). One class per state, each declaring its legal successors. | Amith |
| **Strategy** | `domain/assignment.py` (3 impls), `domain/priority.py` (2 impls) | Spec requires ≥2 assignment strategies that are swappable without redesigning the app. | Amith |
| **Observer** | `domain/events.py` + `NotificationObserver`, `AuditLogObserver` | Every status change fans out to notifications and the audit trail without the incident knowing who's listening. | Kartik |
| **Repository** | `repositories/` | Isolates Supabase behind an interface - also makes the 15 test cases possible without a live DB. | Lokith |
| **Factory** | `domain/factories.py` | Builds `Incident` with priority already computed and the right initial state; builds the correct `User` subclass from a role string. | Amith |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Work Breakdown

### Amith - Lead / Domain & OOP Core

The part the rubric grades hardest. No HTTP, no SQL, no framework imports in `domain/` - pure
Python objects that could be unit-tested with zero infrastructure.

- [ ] `domain/enums.py` - `Role`, `Status`, `Priority`, `Impact`, `Urgency` as real enums
- [ ] `domain/users.py` - abstract `User` with `employee_code`, private `_role`, property accessors;
      subclasses `Employee`, `Technician` (skills, workload, availability), `Admin`. Inheritance only
      where "is-a" genuinely holds - be ready to defend it.
- [ ] `domain/incident.py` - `Incident` aggregate: encapsulated fields, no public setters on
      `status`/`priority`, composition with `Service`, `SLA`, `list[IncidentUpdate]`
- [ ] `domain/states.py` - one class per status; `Incident.transition_to()` delegates to the current
      state and raises `InvalidStateTransitionError` on an illegal move
- [ ] `domain/priority.py` - `WeightedPriorityStrategy`
      (`impact × urgency × business_criticality`, plus affected-user count) → P1-P4, and a second
      `RuleBasedPriorityStrategy`. **Nothing currently computes priority at all - it is hardcoded
      `'P3'` in the schema.** Document the formula and the thresholds.
- [ ] `domain/assignment.py` - `SkillBasedAssignment` (uses `technician_skills`),
      `LoadBalancedAssignment`, `RoundRobinAssignment`
- [ ] `domain/events.py` + `domain/factories.py`
- [ ] `core/exceptions.py` - `ITSMError` base → `InvalidStateTransitionError`,
      `TechnicianUnavailableError`, `WorkloadExceededError`, `ServiceNotFoundError`,
      `SLAPolicyMissingError`, `DuplicateIncidentError`, `UnauthorizedOperationError`
- [ ] Integration: own `main.py` wiring, review every PR, cut the final release tag
- [ ] **Docs:** architecture diagram, class diagram (classes, attributes, methods, interfaces,
      inheritance, associations, composition/aggregation), Technology Selection Report, assemble the
      final PDF

### Inian - Backend API & Security

Routers stay thin: validate input, call a service, map exceptions to HTTP codes. All five router
files are currently comment-only stubs; `auth.py` has seven routes that return placeholder strings.

- [ ] `core/security.py` - JWT issue/verify (PyJWT is already a dependency and unused), password
      handling, `get_current_user()` and `require_role(...)` FastAPI dependencies
- [ ] `auth.py` - real register (creates the `profiles` row, which nothing does today), login,
      logout, session check. Delete the dead reset-password / verify-email stubs or implement them.
- [ ] `incidents.py` - create, list (role-scoped), detail, update, assign, acknowledge, add note,
      resolve, verify, close, plus `GET /incidents/search` with **≥5 filter criteria** (id, date
      range, status, priority, category, service, technician, SLA status)
- [ ] Pydantic request/response schemas, with validation errors returning useful messages
- [ ] Exception handlers in `main.py` mapping every `ITSMError` subclass to the right status code
      (403 unauthorized operation, 409 invalid transition, 422 bad input, …)
- [ ] **Docs:** use case diagram; collect 3 test cases from each member and assemble the
      **15+ test case document** (normal operations, boundary conditions, invalid inputs, exceptions,
      authorization, business rules)

### Anirudh - Frontend & UX

Three visibly different interfaces - the problem statement explicitly requires the GUI to differ per
role, with clear links to move between views.

- [ ] Wire `Jinja2Templates` in `main.py` and serve pages from `pages.py`
- [ ] **Fix the broken asset links.** Every template contains a literal Python expression in the
      href - `href="BASE_DIR / "app" /"static" / "css" / "style.css"` - so no CSS or JS has ever
      loaded. Correct path is `/static/style.css` via `url_for`.
- [ ] `login.html` / `signup.html` - post to the real auth endpoints, show errors, redirect by role
- [ ] **Employee view** (`clienthome.html`) - report incident, my incidents + live status, add info,
      view resolution, post-resolution feedback
- [ ] **Technician view** (`ithome.html`) - currently a copy-paste duplicate of the employee page;
      rebuild it: assigned queue sorted by priority, acknowledge, investigation notes, status
      updates, request info, resolve, my workload
- [ ] **Admin dashboard** (new) - incident overview tiles, technician workload table, service
      analysis, SLA violations, audit log viewer, user/service/SLA/category management, assignment
      strategy switcher
- [ ] Fill the four empty JS files (`login.js`, `signup.js`, `clienthome.js`, `ithome.js` - all 0
      bytes) + a new `admin.js`; fetch-based calls, client-side validation, notification bell
- [ ] `index.html` is empty - make it the landing/redirect page
- [ ] SLA countdown colour coding (green / amber / breached) - cheap, demos extremely well
- [ ] **Docs:** Requirements Specification (functional, non-functional, user roles, business rules);
      record and edit the 15-20 min demo video

### Lokith - Data & Persistence

- [ ] `repositories/` - `Repository` ABC plus incident / user / service / audit implementations
      wrapping `supabase-py`, so no router or service ever touches the client directly
- [ ] `incident_repo.search()` backing Inian's 5+ filter criteria
- [ ] Schema corrections and a migration file (don't edit `schema.sql` in place once others have run
      it - add `migrations/002_*.sql`)
- [ ] Expand `seed.sql`: demo users for all three roles, technician skills, and ~30 historical
      incidents. **The demo and every analytics screen is worthless without realistic seed data** -
      this is on the critical path for the video, not an afterthought.
- [ ] `sla_service.py` - response/resolution/escalation deadline calculation in Python, breach
      detection, warnings *before* deadlines. `refresh_incident_sla_breaches()` exists in the schema
      but is never scheduled or called, so every breach flag in the database is permanently `FALSE`.
      Either schedule it (Supabase Cron) or drive it from a FastAPI background task - then say which,
      and why, in the report.
- [ ] `admin.py` router - dashboard metrics, technician workload report, service analysis, SLA
      violation report, audit log access, user/service/category/SLA CRUD
- [ ] `technicians.py` router - my queue, my workload, skills management
- [ ] `AuditLogObserver` writing to `audit_logs` (timestamp, user, action, incident id, previous
      state, new state, description). The table exists; nothing writes to it.
- [ ] Decide the fate of the root-level `admin-queries.ts`, `customer-queries.ts`,
      `technician-queries.ts`. They are a parallel TypeScript backend that references columns that
      **do not exist** (`response_sla_breached` vs the real `response_breached`; `profiles.name` and
      `profiles.email`, neither of which is in the schema). Port the useful queries into the Python
      repositories, then delete the `.ts` files. Submitting two half-backends reads as confusion.
- [ ] **Docs:** ER diagram + Database Design document (schema, relationships, sample data, and the
      justification for PostgreSQL/Supabase)

### Kartik - Intelligent & Automated Features

Owns the "Intelligent Features" requirement (≥2 mandatory) and the Innovation marks (10). AI/ML is
explicitly optional - a well-designed rule-based system scores full marks, so build rule-based
first and only reach for a model if there's time left.

Mandatory (pick at least two, these three are the best value):

- [ ] **Duplicate / similar incident detection** - on create, flag incidents on the same service with
      overlapping keywords inside a time window (token overlap or trigram similarity; Postgres
      `pg_trgm` does the heavy lifting). Demo workflow 3 depends on this.
- [ ] **Automatic escalation** - unacknowledged critical incident → Technician → Team Lead →
      Administrator → IT Manager, driven off `escalation_deadline_at`
- [ ] **Automatic categorization** - suggest a category from the description text (keyword and weighted
      rules over the 9 seeded categories)

Also yours:

- [ ] `notification_service.py` - `NotificationChannel` abstraction with **≥2 channels**
      (in-app writing to the `notifications` table + email or a simulated SMS/console channel).
      Simulation is explicitly acceptable. The table exists and nothing writes to it today.
- [ ] `NotificationObserver` - fires on incident created, assigned, priority changed, SLA
      approaching, SLA violated, resolved, closed
- [ ] Adding a third channel must require **no change** to existing code - that's the point of the
      abstraction, and it's what you'll be asked to demonstrate

Stretch (Innovation marks, only after the above are done):

- [ ] **SLA risk detection** - predict which open incidents will breach
- [ ] **Smart technician recommendation** - rank by skills × workload × experience × service history
- [ ] **Suggested resolution** - surface resolutions from similar historical incidents
- [ ] **Docs:** Problem Analysis (problem, stakeholders, existing challenges, proposed solution,
      assumptions) + a clear write-up of each algorithm and its rationale

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Schedule

Eleven days. The dependency that matters: **Amith's domain interfaces unblock everyone, and Lokith's
seed data unblocks the demo.** Both are front-loaded for that reason.

| Dates | Milestone | Who |
|---|---|---|
| **Nov 11-12** | Design freeze. Interface contracts agreed and pushed as abstract classes + stubs. Broken templates and `requirements.txt` fixed. Repo cleaned. | All |
| **Nov 13-15** | Core build. Domain model complete. Auth working. Repositories live. Three pages rendering real data. | All |
| **Nov 16-17** | **Integration checkpoint - workflow 1 must run end to end:** employee reports → priority computed → technician assigned → notification generated. Nothing new starts until this works. | All |
| **Nov 18-19** | Intelligent features, notifications, audit trail, admin dashboard, search/reports. Everyone writes their 3 test cases. | All |
| **Nov 20** | **Feature freeze.** Bug-fixing only. All diagrams drawn. Documentation written. | All |
| **Nov 21** | Record the video (every member introduces themselves and explains their module). Assemble and proofread the PDF. | Anirudh records, Amith assembles |
| **Nov 22** | Submit - report PDF + `67_OOP_S1_2025-2026_Project` video. Buffer day; do not plan work here. | Amith |

**Daily:** a one-line status in the group chat - done / doing / blocked. If you're blocked for more
than half a day, say so; nobody can read minds.

### The three workflows the video must demonstrate

1. Employee reports → system prioritizes → technician assigned → notification generated
2. Technician investigates → SLA monitored → incident resolved → user notified
3. Multiple incidents reported → duplicates/related identified → correlated or escalated

Rehearse these before recording. Seed the database so each one takes under three minutes.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Known Breakages to Fix First

Small, embarrassing, and all fixable on day 1.

- [ ] **Templates** - literal `BASE_DIR / "app" /"static" / ...` inside `href`/`src` attributes in
      four files; CSS and JS have never loaded. Also `style.css` lives at `static/style.css`, not
      `static/css/style.css`. - *Anirudh*
- [ ] **`requirements.txt`** - a UTF-16 copy of itself is prepended to the file (the mojibake header).
      Rewrite as plain UTF-8. - *Amith*
- [ ] **`main.py:22`** - the root route returns `"Wesdfsdfseflcome to the IT Service Management
      Backend!"`. - *Amith*
- [ ] **`app/templates/index.html`** and all four files in `app/static/js/` are **empty**. - *Anirudh*
- [ ] **Root-level `.ts` files** - a second, broken backend referencing non-existent columns.
      - *Lokith*
- [ ] **No Jinja2 configured** - `jinja2` is a dependency, `Jinja2Templates` is never instantiated,
      so not a single template is served. - *Anirudh*
- [ ] **This README** replaced the one copy-pasted from an unrelated neural-network repo. Done.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Getting Started

### Prerequisites

- Python 3.12+
- A Supabase project (ask Amith for the `.env` values - **never commit `.env`**, it's gitignored)

### Installation

1. Clone and enter the repo:
   ```sh
   git clone https://github.com/kart1k1927/OOPS_PROJECT_67.git
   cd OOPS_PROJECT_67
   ```

2. Create your own branch - **do not work on `main`**:
   ```sh
   git switch -c <your-name>/<what-youre-building>
   ```

3. Create a virtual environment and install dependencies:
   ```sh
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   ```
   On Windows PowerShell the activate line is `.venv\Scripts\Activate.ps1`.

4. Configure the environment:
   ```sh
   cp .env.example .env
   ```
   Then fill in `SUPABASE_URL` and `SUPABASE_ANON_KEY`.

5. Run the development server:
   ```sh
   uvicorn app.main:app --reload
   ```
   - App: <http://127.0.0.1:8000>
   - Interactive API docs: <http://127.0.0.1:8000/docs>
   - Health check: <http://127.0.0.1:8000/health>

### Database setup

Run against the Supabase SQL editor, in this order:

```
app/database/schema.sql     -> tables, indexes, triggers, RLS policies
app/database/seed.sql       -> categories, services, SLA policies
app/database/migrations/    -> any later changes, in filename order
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Git Workflow

`main` is the submission branch. It must always run.

1. Branch per task: `git switch -c anirudh/admin-dashboard`
2. Stage deliberately - `git add .` sweeps up junk. Check first:
   ```sh
   git status
   ```
3. Commit with a message that says what changed:
   ```sh
   git commit -m "feat(domain): add State pattern for incident lifecycle"
   ```
   Prefixes: `feat` / `fix` / `refactor` / `docs` / `test` / `chore`.
4. Push your branch, never straight to `main`:
   ```sh
   git push -u origin $(git branch --show-current)
   ```
5. Open a pull request. **Amith reviews and merges.** At least one other member reads the diff -
   that's also how everybody ends up understanding the whole system before the viva.

Never commit: `.env`, `.venv/`, `__pycache__/`, `node_modules/`. All already gitignored - keep it
that way.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Definition of Done

Mapped to the 120-mark rubric. Nothing is "done" until its box is ticked.

**System Design & Architecture - 10**
- [ ] Layered architecture implemented as described, and defensible
- [ ] Architecture diagram + class diagram submitted

**Functionality (MVP) - 60**
- [ ] Three user roles: Employee, Technician, Administrator
- [ ] Incident create / view / update / assign / resolve / close
- [ ] Priority computed from impact, urgency and business criticality
- [ ] **Two or more** assignment strategies, swappable at runtime
- [ ] SLA calculation, deadline tracking, violation detection
- [ ] **Two or more** notification mechanisms
- [ ] Complete audit trail per incident
- [ ] **Five or more** search/filter criteria
- [ ] **Two or more** intelligent/automated features
- [ ] Persistent storage for users, services, incidents, technicians, SLA policies, audit records,
      resolutions

**User Experience - 10**
- [ ] Visibly distinct GUI per role, with working navigation between views
- [ ] Authentication, role-based authorization, input validation
- [ ] SLA status visible at a glance

**Technical Depth - 15**
- [ ] Encapsulation, abstraction, inheritance, polymorphism, interfaces, composition,
      association/aggregation all demonstrable - and each one locatable in the code on request
- [ ] Five design patterns implemented
- [ ] Appropriate collections/data structures, chosen for a reason you can state

**Testing & Validation - 5**
- [ ] 15+ documented test cases: normal, boundary, invalid input, exceptions, authorization,
      business rules
- [ ] Custom exception hierarchy covering invalid login, unauthorized operation, invalid state
      transition, technician unavailable, workload exceeded, service not found, missing SLA config,
      duplicate incident, database failure, invalid input

**Innovation - 10**
- [ ] At least one item from the Innovation Challenge list, beyond the two required intelligent
      features

**Documentation & Presentation - 10**
- [ ] Problem Analysis · Requirements Specification · System Architecture · UML (use case + class) ·
      Technology Stack · Source Code · Database Design · Testing · Demo
- [ ] Single group PDF report
- [ ] 15-20 min video, every member speaking, three complete workflows, named
      `67_OOP_S1_2025-2026_Project`

<p align="right">(<a href="#readme-top">back to top</a>)</p>
