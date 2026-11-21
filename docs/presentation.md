# Demo video script

**Target length: 17 minutes.** The brief says 15 to 20, so 17 leaves room to run
over without breaching and is comfortably past the minimum. A 13 minute video
risks marks for being under length.

**File name:** `67_OOP_S1_2025-2026_Project`

**Every member must introduce themselves and explain a module.** That is stated
in the brief, and it is the easiest mark to lose. Each section below opens with
the speaker saying their name.

---

## Before you hit record

Run through all of this. It takes ten minutes and it is the difference between a
clean take and four retakes.

```sh
cd ~/Documents/codingProjects/OOPS/OOPS_PROJECT_67

# 1. Reset the demo data so the SLA spread looks real, not all-breached.
PYTHONPATH=. .venv/bin/python scripts/age_demo_data.py

# 2. Start the server.
.venv/bin/uvicorn app.main:app --port 8000
```

| Check | Why |
|---|---|
| Re-run `age_demo_data.py` **on the day you record** | Incidents age in real time. Left alone for a week, every SLA reads breached and the dashboard looks broken. |
| Browser at 1440 wide, zoom 110 percent | Text is legible when the video is compressed. |
| Close every other tab, hide bookmarks | Nothing personal on screen. |
| Open three private windows, one per role | Lets you switch roles instantly instead of signing in and out on camera. |
| Have `INC-` references written down | Reading a reference off the screen mid-sentence kills the pace. |
| Mute notifications on the machine | |
| Test the microphone on a 30 second take first | More demos are ruined by audio than by anything else. |
| Have the code open in the editor at `app/domain/states.py` | Section 7 switches to code. |

**Accounts**, all with password `campus2026`:

| Role | Email |
|---|---|
| Administrator | `admin@bits.ac.in` |
| Technician | `priya@bits.ac.in` |
| Employee | `ravi@bits.ac.in` |

---

## 1. Opening and the problem · 1:30 · **Amith**

> "Hello, I am Amith. Our group is number 67, and this is I-ITSM, an Intelligent
> IT Service Management and Incident Resolution System for BITS Hyderabad.
>
> The problem we set out to solve is one everybody on campus has had. The
> payment portal goes down, or the wifi drops in D block, and there is no
> reliable way to report it and no way to find out what happened next. Reports
> go in by phone call or by message. Nobody can say how many incidents are open
> right now, which technician is overloaded, or whether the same service has
> failed three times this month.
>
> The deeper problem is that the information needed to make a good decision is
> never in one place. Priority needs impact, urgency and how critical the
> service is. Assignment needs skills, workload and availability. None of that
> is recorded anywhere, so every decision gets made from memory.
>
> What we built manages the complete lifecycle of an incident: report, classify,
> prioritise, assign, investigate, resolve, verify, close. I will show you three
> complete workflows through it."

**On screen:** the sign-in page, then the administrator overview.

---

## 2. Architecture and the OOP design · 2:00 · **Amith**

**On screen:** `docs/diagrams/01-architecture.md` rendered on GitHub, then
`03-class-diagram.md`.

> "Before the demo, thirty seconds on how it is built, because this is an object
> oriented design project and the design is the point.
>
> It is layered. Browser, API, services, domain, repository, database. Each
> layer depends only on the one below it, and the dependency at the bottom is on
> an interface rather than on our database, which matters in a moment.
>
> The rule we enforced is that business logic lives in the domain and service
> layers only. The routers validate input and render. The database holds data
> and constraints. We actually had to remove two SQL triggers that were doing
> technician assignment and SLA arithmetic inside the database, because logic in
> two engines drifts, and logic buried in plpgsql cannot be expressed as an
> object.
>
> We implemented five design patterns, where the brief asked for two. State for
> the incident lifecycle. Strategy, twice, for priority and for assignment.
> Observer for notifications and auditing. Repository for persistence. Factory
> for construction. Each one solves a problem the brief actually poses, and I
> will point at each of them as it appears in the demo."

---

## 3. Workflow one, an employee reports an incident · 3:30 · **Anirudh**

**Signed in as `ravi@bits.ac.in`.**

> "I am Anirudh, and I built the interface. This is the employee view. Ravi can
> only see incidents he reported, and that is enforced on the server, not by
> hiding links.
>
> I will report the payment outage."

**Click Report an incident. Type the title slowly:**
`Payment application is unavailable`

> "Watch the panel at the bottom as I fill this in."

**Fill description, select Payment Application, set impact HIGH, urgency HIGH,
affected users 120.**

> "That panel is live. Every change recalculates the priority on the server and
> sends back both the answer and the working. Right now it reads: impact HIGH
> times urgency HIGH times criticality 5 equals 45, plus 4 for 120 people
> affected, score 49, which maps to P1 Critical. And it tells me the SLA that
> comes with it: respond in five minutes, resolve in thirty.
>
> That is the Strategy pattern, visible. The formula is one class,
> `WeightedPriorityStrategy`. There is a second one, `MatrixPriorityStrategy`,
> using the ITIL grid instead, and an administrator can switch between them at
> runtime. Lokith will show that later.
>
> Notice I never chose a category. The system read the description and suggested
> Application, and it shows which words it used.
>
> One more thing before I submit."

**Point at the duplicate warning if it appears.**

> "It has compared this against recent reports on the same service and flagged a
> possible duplicate. It flags, it does not block, because a helpdesk that
> refuses reports is worse than one with duplicates in it."

**Submit.**

> "Logged as INC-something, priority P1, already assigned to a technician, with
> a resolution deadline. Nobody touched it. The priority was calculated, the
> category inferred, the technician chosen by strategy and the notification
> sent, all before this page rendered."

---

## 4. Workflow two, a technician resolves it · 3:30 · **Inian**

**Switch to the window signed in as `priya@bits.ac.in`.**

> "I am Inian, and I worked on the API layer and the authorisation. This is
> Priya's queue, sorted by priority and then by how close the SLA deadline is.
>
> Here is the incident Anirudh just reported, at the top because it is P1."

**Open it. Point at the right-hand action panel.**

> "This panel is the part I want you to look at. It shows one button:
> Acknowledge. Not a row of greyed out buttons, one button. The server asked the
> incident what state it is in, asked the state object what transitions it
> permits, asked the role what it is allowed to do, and rendered what came back.
> A technician never has to work out why something is disabled, because
> disabled things are not there.
>
> That is the State pattern. There is one class per status, and each one
> declares where it may go."

**Click Acknowledge. Then Start investigating. Then show the resolve form.**

> "Acknowledged, which stamps first response. Then In Progress, and now the
> options have changed: resolve, or put it on hold waiting for the reporter.
>
> Below that, resolutions that worked on similar incidents before, pulled from
> history. Kartik built that.
>
> Now, the important part. This is not just the interface being polite."

**Open a terminal or show the test file `tests/test_api.py::test_52`.**

> "We have a test that forges the request. It posts resolve directly to an
> incident that is still in ASSIGNED state, skipping the interface entirely. It
> comes back 403 and the incident does not move. Authorisation and the state
> machine are checked together, in the service, on every single write. The
> interface not showing a button is not the control."

**Resolve it with a real note.**

> "Resolved. The reporter has been notified, and it is now waiting for them to
> confirm the fix before it can be closed."

**Switch back to Ravi's window, refresh, confirm the fix, close, rate it.**

> "Ravi confirms, closes, and rates it. Verified then Closed, in that order.
> Ravi cannot close an incident he has not verified, and that is a business
> rule, not a UI convention."

---

## 5. Workflow three, duplicates, correlation and escalation · 3:00 · **Kartik**

**Back in Ravi's or another employee's window.**

> "I am Kartik, and I built the intelligent and automated features. There are
> seven. All of them are rule based, deliberately. The brief says AI and machine
> learning are optional and a well designed rule based system is acceptable, and
> a rule we can explain line by line is worth more in an operations tool than a
> model we cannot.
>
> The brief gives an example: three reports of one payment outage. Let me do
> exactly that."

**Report a second incident:** `Payment transaction failing at checkout`,
description `Payment keeps failing when I try to pay the hostel fee.`

> "Before I submit, look here. It has found the earlier incident and told me how
> similar it is and which words they share. It compares every new report against
> recent ones on the same service using a blend of two similarity measures, with
> a bonus for matching service and category."

**Submit, then switch to the admin window, show the Correlated incidents banner.**

> "On the administrator's overview, this is the other half: correlation. Rather
> than six separate rows, it says Payment Application has this many open
> incidents, worst priority P1. A cluster on one service in a short window is
> usually one underlying fault.
>
> Third feature: escalation. If a critical incident is not acknowledged before
> its escalation deadline, it climbs a ladder. Technician, senior technician,
> administrator, IT management. It widens who is being told. It never reassigns
> the incident, because taking work off somebody who is already on it helps
> nobody.
>
> And fourth, this panel: predicted SLA risk. These are open incidents the
> system expects to breach, before they do, scored on five weighted signals, and
> it says why in words. Ninety-two percent of the window gone, nobody has
> responded, the assigned technician is carrying six, critical priority."

---

## 6. The administrator view and runtime configuration · 2:30 · **Lokith**

**Admin window.**

> "I am Lokith, and I worked on the database and the persistence layer.
>
> This is the operations overview. Total, open, P1 open, resolved, SLA
> violations. Technician workload with skills and capacity. Service analysis.
> Incidents by category. All of it computed from the live database."

**Go to System settings.**

> "This screen is the one I would point at if you asked me to prove the design
> claim. Four technician assignment strategies. Skill based, load balanced,
> round robin, experience weighted. The active one is skill based.
>
> I am going to change it."

**Select Load balanced, click Use this strategy.**

> "No restart. No deploy. No code change. The next incident reported will be
> assigned by a completely different rule. That is the Strategy pattern doing
> the thing it exists for, and the brief specifically asks that the assignment
> strategy be changeable without redesigning the application.
>
> Below that, the priority algorithm, same mechanism. Below that, the automated
> features can each be switched off. And at the bottom, the full lifecycle table
> rendered straight out of the state machine, so this documentation cannot drift
> from the code."

**Go to Services and SLA.**

> "SLA targets per priority, editable. Business criticality per service, which
> feeds straight into the priority formula. Adding a category here needs no code
> change at all."

**Go to Audit log.**

> "And the audit log. Every state change, who did it, previous state, new state.
> This is written by an observer, not by each service remembering to log. If an
> event was published, it was recorded. It cannot drift."

---

## 7. The code, and the patterns · 2:30 · **Amith**

**Switch to the editor. Open `app/domain/states.py`.**

> "Two minutes in the code, on the two pieces that carry the design.
>
> This is the State pattern. One class per status. Each declares which
> transitions it permits and what entering it records. The brief names one
> transition specifically that must be prevented: a new incident jumping
> straight to closed. `OpenState` permits CLASSIFIED and ASSIGNED, and nothing
> else, so it is not that we check for that case, it is that the case cannot be
> expressed.
>
> Adding a new state is a new class. No existing code changes."

**Open `app/domain/users.py`.**

> "And this is the user hierarchy. `User` is abstract. Employee, Technician and
> Administrator inherit from it. What differs between them is not data, it is
> behaviour: where signing in takes them, which incidents they may open, and
> what they may do to one.
>
> The whole application calls those three methods. There is no `if role equals
> admin` anywhere in the codebase. Adding a Team Lead role means adding a class."

**Open `app/domain/assignment.py` briefly, then the terminal.**

> "Four assignment strategies, all behind one abstract base class."

**Run the tests on camera:**

```sh
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

> "Fifty-eight documented test cases, seventy-one runs with the parameterised
> ones, covering normal operation, boundary conditions, invalid input,
> exceptions, authorisation and business rules.
>
> And they run in twelve seconds with no database, no credentials and no
> network. That is the Repository pattern paying for itself: there are two
> implementations of the same interface, one talking to PostgreSQL and one
> holding objects in a dictionary, and the services cannot tell which one they
> have."

---

## 8. Close · 0:30 · **Amith**

> "To summarise. Complete incident lifecycle with a state machine that refuses
> illegal transitions. Priority calculated from a documented formula. Four
> assignment strategies interchangeable at runtime. Continuous SLA monitoring
> with escalation. Three notification channels behind one abstraction. Seven
> rule based intelligent features. A complete audit trail written by observers.
> Nine search criteria. Five design patterns. Seventy-one tests.
>
> Thank you."

---

## Timing

| Section | Speaker | Minutes | Running |
|---|---|---|---|
| 1. Problem | Amith | 1:30 | 1:30 |
| 2. Architecture | Amith | 2:00 | 3:30 |
| 3. Workflow 1, report | Anirudh | 3:30 | 7:00 |
| 4. Workflow 2, resolve | Inian | 3:30 | 10:30 |
| 5. Workflow 3, duplicates | Kartik | 3:00 | 13:30 |
| 6. Admin and configuration | Lokith | 2:30 | 16:00 |
| 7. Code and patterns | Amith | 2:30 | 18:30 |
| 8. Close | Amith | 0:30 | **19:00** |

Nineteen minutes with no overruns. If you are running long, cut section 2 to one
minute and section 7 to ninety seconds; both are explanation rather than
demonstration. Do not cut the three workflows, they are required by the brief.

If you come in under fifteen, slow down rather than adding material. Talking
through what is on screen while it loads is better than a rushed extra feature.

---

## How to present it well

**Narrate the why, not the what.** "I am clicking Acknowledge" is worthless, the
marker can see that. "Acknowledging stamps first response, which is what the SLA
measures against" is worth marks.

**Pause after each claim.** When Inian says the forged request returns 403, stop
for a beat. Give it room to land.

**Never apologise on camera.** If something is slow, say what it is doing. If
something breaks, keep going and mention it in the report. Do not say "sorry,
this is usually faster".

**One person per section, no interruptions.** Handovers should be clean: "that is
the employee side, Inian will take the technician view."

**Record in one take if you can.** Editing five separate recordings together
always sounds worse than one continuous run with a stumble in it.

---

## Questions you should be ready for

The evaluator can ask anyone about any module, and the whole group gets one
score. Each of you should be able to answer all of these.

| Question | Answer |
|---|---|
| "Where is encapsulation?" | `Incident` has 37 read-only properties and no public setters. Status changes only through `transition_to`, priority only through `apply_priority`, which also moves the SLA so the two cannot drift apart. |
| "Show me polymorphism." | `User.available_actions()`. Three subclasses, three different answers, and the template calls it without knowing which it has. |
| "Why inheritance here and not composition?" | Because the "is-a" test genuinely passes and the subclasses differ in behaviour rather than data. We used composition where that was not true: `Incident` has-a `SLATracker`. |
| "What is the difference between your composition and your aggregation?" | `Incident` to `SLATracker` is composition, destroy the incident and the tracker goes. `Incident` to `ITService` is aggregation, the Payment Application service outlives any incident against it. |
| "Why rule based and not AI?" | The brief makes ML optional and says a well designed rule based system is acceptable. We have no labelled campus data to train on, and in an operations tool a decision that can be explained matters more than one that is marginally more accurate. |
| "Why did you not use Supabase Auth?" | Two reasons. The project's auth schema was broken, its admin API failed because profile rows had been inserted with hand written UUIDs. More importantly, delegating authorisation to row level security puts the most interesting rules in SQL where no object can express them. |
| "What would break at ten times the scale?" | The in-process state. The active strategy, the round robin cursor and the SLA warning set all live in memory, so two workers would disagree. That moves to Redis or the database. Section 3.9 of the report lists the rest in order. |
| "Why did you drop the database triggers?" | They duplicated what the Strategy classes and the SLA service do in Python. Two engines writing the same columns means one silently overwrites the other. The functions are still in the database if you want to see them. |
| "How do you know the authorisation works?" | `tests/test_api.py::test_52` forges the request past the interface and asserts a 403 and no state change. |
| "What is the weakest part?" | Single process state, and Python side aggregation in the reporting service that would not scale past a few thousand incidents. Both are in section 3.7 of the report. |

**If you do not know an answer, say so and say where you would look.** "I did not
write that module, but it is in `app/domain/assignment.py` and the strategy
selection happens in `IncidentService._assign_by_strategy`" is a far better
answer than guessing.
