# 3. Technology Selection Report

The brief asks nine questions. Each is answered below with the reasoning that
actually drove the decision, including the places where we were wrong and
changed course.

## 3.1 Why this programming language?

**Python 3.12.**

The deciding factor was that this is graded on object oriented design, so the
language had to make OOP *visible* rather than ceremonial. Python gives us
abstract base classes, properties, enums with behaviour attached, dataclasses
and structural pattern matching, and it does so without the boilerplate that
would bury the design under getters and setters.

Three specific features earned their place:

- **`abc.ABC` with `@abstractmethod`** gives real contracts. `AssignmentStrategy`
  cannot be instantiated, and a subclass that forgets `_rank` fails at
  construction, not at runtime.
- **`@property`** lets `Incident` expose thirty read-only attributes with no
  public setters, which is what makes encapsulation enforceable rather than a
  naming convention.
- **Enums with methods.** `Priority.rank` and `Impact.weight` put behaviour on
  the value, so the priority formula reads as the formula rather than as a
  dictionary lookup.

Python is also what the team already knew well enough to spend the time on
design rather than on syntax, which matters on a three week project. We state
that plainly because the brief warns against choosing on familiarity alone, and
familiarity was a tiebreaker here, not the reason.

## 3.2 Why this frontend technology?

**Server rendered Jinja2 templates, vanilla JavaScript, no framework.**

This is the choice most likely to be questioned, so the reasoning matters.

A single page application in React would have meant duplicating authorisation
logic in the client, because the interface has to decide which buttons to show,
and that decision depends on the role *and* the state machine. Duplicating it
means two implementations that drift. Server rendering means the server computes
`User.available_actions(incident)` once and the template renders whatever comes
back. The technician sees fewer buttons, not disabled ones, and the rule exists
in exactly one place.

JavaScript is used for two things only: the live priority preview on the report
form, and the category suggestion. Both call the server rather than
reimplementing the algorithm, for the same reason: there is one priority
formula in this system and it lives in `app/domain/priority.py`.

The cost is that the interface is less fluid than an SPA. For an internal
operations tool used by technicians working a queue, we judged that an
acceptable trade for not having a second codebase.

**Styling** follows a written design system (`docs/design-system.md`) rather
than a component library, because the brief grades user experience and a
default Bootstrap theme is recognisably a default. Colour is reserved for
status, so the only saturated colour on screen is a priority or an SLA state.

## 3.3 Why this backend technology?

**FastAPI with Uvicorn.**

- **Dependency injection** is the feature that mattered most. `Depends(get_current_user)`
  returns the correct `User` subclass, so every endpoint receives an object that
  already knows what its role may do. Authorisation becomes a method call rather
  than a decorator stack.
- **Centralised exception handling.** Our `ITSMError` hierarchy carries its own
  HTTP status, so one handler translates seventeen exception types, returning
  JSON to an API caller and a rendered page to a browser.
- **ASGI and background tasks.** The SLA monitor is an asyncio task started in
  the application lifespan. This is the single hardest requirement to satisfy on
  a serverless platform and the reason we did not deploy to Vercel.
- **Automatic OpenAPI documentation** at `/docs`, free.

Django was the main alternative and was rejected deliberately: its ORM, admin
and auth would have done the interesting work for us. Technician assignment
would have become a `models.py` query rather than a Strategy hierarchy, and we
would have had less to show on an OOP rubric, not more.

## 3.4 Why this database?

**PostgreSQL, hosted on Supabase.**

PostgreSQL because the data is relational and the constraints are real:
incidents reference reporters, services, categories and technicians; a priority
must be one of four values; a feedback rating must be 1 to 5. Those are CHECK
constraints and foreign keys, not application conventions. A document store
would have made the many-to-many between technicians and skills awkward and
would have given up referential integrity for flexibility we do not need.

Specific Postgres features we rely on: `gen_random_uuid()` for identifiers, a
sequence for human readable employee codes, `JSONB` for audit detail that varies
by event type, `NUMERIC` for SLA hours, and the `pg_trgm` extension with a GIN
index to support duplicate detection.

Supabase because it provides managed Postgres with a REST interface, free at our
scale, with no server to administer.

**Where we were wrong.** We initially planned to use Supabase Auth and row level
security for authorisation. Two problems emerged. First, the project's auth
schema was unusable: GoTrue's admin API failed with "Database error finding
users" because the original profile rows had been inserted with hand written
UUIDs. Second, and more important, pushing authorisation into RLS policies would
have put the most interesting rules in SQL, where no object can express them.
Migration 002 moved identity into the application, and authorisation now lives
in `User.require_action`. RLS stays enabled as a second line of defence.

For the same reason we dropped two database triggers that had been doing
technician assignment and SLA arithmetic in plpgsql. Two engines writing the
same columns means the Python result gets silently overwritten, and logic buried
in a trigger earns nothing on an object oriented design rubric. The functions
remain in the database so the decision can be discussed.

## 3.5 Why this architecture?

**Layered: Presentation, API, Service, Domain, Repository, Database.**

Each layer depends only on the one below it, and the bottom dependency is on an
interface rather than on Supabase.

```
Browser -> Routers -> Services -> Domain -> Repository interface -> Supabase -> PostgreSQL
                                                 ^
                                                 +-- In-memory implementation (tests)
```

The rule we enforced is that **business logic lives in the domain and service
layers only**. Routers validate input, call a service and render. The database
holds data and constraints.

The payoff is concrete rather than theoretical. Because `IncidentService` holds
a `Repository` and not a `SupabaseIncidentRepository`:

- all 71 tests run with no database, no keys and no network
- `scripts/demo_server.py` runs the entire application in memory, so a team
  member without credentials can still work on the interface
- swapping Supabase for self hosted Postgres means writing one class

Microservices were considered and rejected as obviously wrong at this scale: a
campus helpdesk with four technicians does not need independently deployable
services, and we would have spent our time on inter service plumbing instead of
on the domain model, which is what is graded.

## 3.6 What alternatives did we consider?

| Decision | Chosen | Alternatives | Why rejected |
|---|---|---|---|
| Language | Python 3.12 | Java, C# | Both are strong OOP languages. Java with Spring Boot was the serious contender and would have given stronger compile time interface guarantees. Rejected on development speed for a three week project. |
| Backend | FastAPI | Django, Flask, Spring Boot | Django does too much for us. Flask would need the same pieces assembled by hand. Spring Boot was a real option, costed at roughly double the setup time. |
| Frontend | Jinja2 + vanilla JS | React, Vue, HTMX | React duplicates authorisation in the client. HTMX was genuinely attractive and is what we would use with more time. |
| Database | PostgreSQL | MySQL, MongoDB, SQLite | MySQL is comparable; Postgres won on JSONB and trigram search. MongoDB loses referential integrity. SQLite cannot be shared between developers. |
| Hosting | Supabase | Self hosted, Firebase | Firebase is document oriented. Self hosting adds administration we have no time for. |
| Auth | Own, with JWT | Supabase Auth, OAuth | Covered in 3.4. The project's GoTrue instance was broken, and delegating auth removes an OOP opportunity. |
| Password hashing | PBKDF2 (stdlib) | bcrypt, argon2 | Both are better. Both need a compiler toolchain to install. PBKDF2 at 390,000 iterations is the current Django default and installs with pip alone. |
| Intelligence | Rule based | scikit-learn, an LLM API | The brief makes ML optional. A rule based system can be explained line by line in a viva; a model checkpoint cannot, and we have no labelled campus data to train on. |
| Deployment | Render | Vercel, Fly.io, Heroku | Vercel is serverless, which breaks the background SLA monitor and the in-process strategy setting. |

## 3.7 Advantages and limitations

### Advantages

1. **The OOP is visible and defensible.** Five design patterns, each solving a
   problem the brief actually poses rather than inserted to tick a box.
2. **The test suite needs no infrastructure.** 71 tests, 12 seconds, no setup.
3. **Extension points are real.** A fifth assignment strategy is a class and a
   registry entry. We proved this by writing four.
4. **Errors are legible.** "Cannot close an incident that is not resolved" tells
   a technician what to do. "Invalid state transition" does not.
5. **Operational honesty.** SLA monitoring actually runs, every 60 seconds, in a
   background task.

### Limitations

1. **Single process state.** The active assignment strategy, the round robin
   cursor and the once-per-incident SLA warning all live in memory. Running two
   workers would give two answers. This is the sharpest limitation and the
   reason deployment is pinned to one worker.
2. **Supabase REST, not SQL.** The repository layer uses PostgREST, so some
   aggregation that would be one SQL query is done in Python over fetched rows.
   `ReportingService.service_analysis` is the clearest example and would not
   scale past a few thousand incidents.
3. **No real time push.** The dashboard renders on page load. There are no
   websockets, so "real time" would be overclaiming.
4. **Rule based intelligence has a ceiling.** The categorizer scores keywords.
   An incident described in words it has never seen gets no suggestion.
5. **Simulated email and SMS.** Permitted by the brief, but not production.
6. **Mobile is scoped, not universal.** The three employee screens are
   responsive; technician and administrator screens target 1024 pixels and up.
7. **Timezone handling is UTC internally with local rendering.** Adequate for
   one campus, insufficient for multiple.

## 3.8 How does the technology support object oriented design?

| OOP concept | Python feature used | Where in this project |
|---|---|---|
| Abstraction | `abc.ABC`, `@abstractmethod` | `User`, `IncidentState`, `AssignmentStrategy`, `PriorityStrategy`, `Observer`, `NotificationChannel`, `Repository` |
| Encapsulation | Private attributes with `@property` | `Incident` has 37 read-only properties and no public setters |
| Inheritance | Class inheritance | `User` to `Employee`, `Technician`, `Administrator` |
| Polymorphism | Duck typing plus ABC contracts | `available_actions()` per role; `calculate()` per priority strategy; `select()` per assignment strategy |
| Interfaces | ABCs used as contracts | `Repository` has Supabase and in-memory implementations the services cannot tell apart |
| Composition | Object attributes | `Incident` has-a `SLATracker` |
| Aggregation | References to shared objects | `Incident` references `ITService` and `Category`, which outlive it |
| Exception handling | Exception class hierarchy | `ITSMError` with 18 subclasses, each carrying its HTTP status |
| Collections | `frozenset`, `Enum`, `dataclass`, `dict` | Transition tables as frozensets; strategy registries as dicts; value objects as frozen dataclasses |
| Generics | `typing.Generic` | `Repository[T]` |

FastAPI reinforces this rather than fighting it: its dependency injection hands
endpoints a constructed `User` subclass, so polymorphism reaches all the way to
the HTTP boundary.

## 3.9 How would the system evolve at significantly larger scale?

Current design target is campus scale: hundreds of users, tens of technicians,
tens of incidents per day. Here is what breaks, in the order it would break,
and what the fix is.

**At roughly 10x (hundreds of incidents per day)**

1. *In-process settings become wrong.* The active strategy, the round robin
   cursor and the warning set must move into the database or Redis so every
   worker agrees. This is the first thing to fix and the reason we ship one
   worker today.
2. *Python side aggregation becomes slow.* `ReportingService` fetches rows and
   counts them. These become SQL aggregates or materialised views.
3. *The SLA sweep scans every open incident every 60 seconds.* It becomes an
   indexed query for incidents whose deadline falls in the next interval.

**At roughly 100x (thousands per day)**

4. *One monitor process is a single point of failure.* It moves to a dedicated
   worker with a leader lock, or to a scheduled job queue such as Celery.
5. *Notifications block the request.* They move onto a queue, which the Observer
   pattern already makes easy: `NotificationObserver.notify` enqueues instead of
   sending, and nothing else changes.
6. *Duplicate detection becomes expensive.* Trigram similarity over recent
   incidents gives way to a vector index.
7. *Read traffic dominates.* Dashboards move to read replicas.

**Beyond that**

8. *Horizontal scaling needs stateless workers.* Sessions are already stateless
   JWTs, so this is mostly about point 1.
9. *Multi tenancy.* A `tenant_id` on every table, and RLS, which is already
   enabled, becomes the enforcement mechanism it was designed to be.

The architecture helps here in one specific way. Every one of these changes is
behind an interface that already exists. Moving notifications to a queue changes
one observer. Moving settings to Redis changes one class. Replacing Supabase
changes one repository implementation. None of them touch the domain model,
which is the part that encodes what an incident actually is.
