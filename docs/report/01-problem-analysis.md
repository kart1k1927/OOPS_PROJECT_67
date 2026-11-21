# 1. Problem Analysis

## 1.1 The problem

BITS Pilani Hyderabad Campus runs on IT services that most people only notice
when they stop. The payment portal, campus wifi, the employee portal, email,
lab machines, the library printers, licence servers. When one of them fails, the
person affected has no reliable way to report it and no way to find out what
happened next.

Today that reporting happens informally: a phone call to CCIT, a message to
somebody who knows somebody, an email that may or may not be read. The
consequences are predictable and all of them were listed in the project brief:

| Failure | What it looks like on campus |
|---|---|
| Delayed response | A reported fault sits unread because nobody owns the inbox |
| Incorrect prioritisation | A single broken printer gets attention before a payment outage affecting 120 people |
| Inefficient technician allocation | One technician has eleven open jobs while another has two |
| SLA violations | Nobody agreed what "urgent" means in hours, so nothing is ever late |
| Poor visibility | No one can answer "how many incidents are open right now" |
| Duplicate reports | Forty people report one wifi outage as forty separate problems |
| Incomplete history | The fix is in a technician's head, so the next occurrence starts from zero |
| Recurring problems unnoticed | The same service fails monthly and nobody connects the instances |

The underlying issue is not that people are careless. It is that **the
information needed to make good decisions is never in one place**. Priority
needs impact, urgency and how critical the service is. Assignment needs skills,
current workload and availability. None of that is recorded anywhere, so every
decision is made from memory and intuition.

## 1.2 Stakeholders

| Stakeholder | What they need | What they currently get |
|---|---|---|
| **Employee / student** | To report a fault in under a minute and then see what is happening to it | A phone call and silence |
| **Technician** | A prioritised queue, the context to start work, and a workload that is survivable | Whatever reaches them, in whatever order it arrives |
| **IT Manager / Administrator** | To see service health, spot overloaded technicians and know which SLAs are being missed | No numbers at all |
| **CCIT / Maintenance Division** | Evidence to justify staffing and infrastructure spending | Anecdote |
| **The campus** | Services that come back quickly | Variable |

## 1.3 Existing challenges

**Prioritisation is subjective.** "Urgent" means whatever the reporter says it
means. There is no agreed formula, so two identical incidents get different
treatment depending on who logs them and how insistent they are.

**Assignment is ad hoc.** Jobs go to whoever is nearest or most recently
mentioned, not to whoever is trained in that category and has capacity.

**Nothing is measured.** Without recorded timestamps there is no way to say
whether response times are improving, which services fail most, or whether a
technician is overloaded.

**Knowledge is not retained.** The same incident recurs and the resolution has
to be rediscovered, because last time's fix was never written down against the
incident.

**No audit trail.** When something goes wrong in handling a fault, there is no
record of who did what and when.

## 1.4 Proposed solution

**I-ITSM**, an Intelligent IT Service Management and Incident Resolution System:
a web application that manages the complete lifecycle of an IT incident from
report through classification, prioritisation, assignment, investigation,
resolution, verification and closure.

The system directly answers each challenge above:

| Challenge | How I-ITSM addresses it |
|---|---|
| Subjective prioritisation | A documented formula, `impact x urgency x business criticality`, with a bump for the number of people affected, shown live on the report form as the reporter types |
| Ad hoc assignment | Four assignment strategies, selectable at runtime, all of which respect skills, workload ceilings and availability |
| Nothing measured | Every incident carries SLA deadlines derived from its priority, monitored continuously, with an administrator dashboard reporting open counts, workload, service health and violations |
| Knowledge lost | Every resolution is recorded against its incident, and similar past resolutions are surfaced to the technician working a new one |
| No audit trail | Every state change is written automatically by an observer, so the trail cannot drift out of step with what happened |
| Duplicate reports | New reports are compared against recent ones on the same service, and possible duplicates are shown to the reporter before they submit |

The central academic question the brief asks is how object oriented thinking
produces a maintainable, extensible system. The answer this project gives is
that **each of the varying policies above is an object, not a branch in a
function**. Adding a fifth assignment strategy means writing a class. Adding a
tenth lifecycle state means writing a class. Neither requires editing existing
code, and that is the difference between a system that can be handed to CCIT and
one that cannot.

## 1.5 Assumptions

1. **Scale.** Designed for a campus: hundreds of users, tens of technicians,
   tens of incidents per day. Not for an enterprise handling thousands daily.
2. **Trust.** Users are campus members with real identities. The system defends
   against mistakes and casual misuse, not a determined attacker.
3. **Email and SMS are simulated.** The brief states this is acceptable. Both
   channels write a full envelope to `logs/outbox.log`, so switching to a real
   SMTP or Twilio adapter means writing one class.
4. **One organisation.** No multi tenancy, no inter departmental separation
   beyond roles.
5. **Technicians self report capacity.** `max_workload` is configured by an
   administrator rather than inferred.
6. **Business criticality is set by an administrator**, on a 1 to 5 scale, and
   is treated as given rather than derived from usage data.
7. **English only.** No localisation.
8. **Rule based intelligence.** The brief explicitly makes AI and ML optional
   and states that a well designed rule based system is acceptable. We chose
   rule based deliberately, because every decision the system makes can then be
   explained line by line, which matters more in an operations tool than raw
   accuracy.
