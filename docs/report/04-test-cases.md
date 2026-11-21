# 4. Test Cases

The brief asks for at least 15 documented test cases. This suite has **58 documented cases**, which expand to **71 individual runs** once parameterised cases are counted.

```sh
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

```
71 passed, 1 warning in 11.87s
```

Every case runs against in-memory repositories. No database, no credentials and no network are required, which is the practical payoff of the Repository pattern: the services cannot tell the difference between the real implementation and the test one.

## 4.1 Coverage against the categories the brief names

| Category | Cases |
|---|---|
| Normal operation | 23 · TC-44, TC-47, TC-49, TC-50, TC-51, TC-53, TC-54, TC-02, TC-09, TC-11, TC-12, TC-15, TC-17, TC-21, TC-22, TC-23, TC-30, TC-36, TC-37, TC-38, TC-39, TC-40, TC-42 |
| Boundary | 7 · TC-03, TC-07, TC-08, TC-10, TC-18, TC-19, TC-24 |
| Invalid input | 5 · TC-48, TC-05, TC-06, TC-31, TC-33 |
| Exception | 8 · TC-55, TC-16, TC-32, TC-35, TC-41, TC-56, TC-57, TC-58 |
| Authorization | 9 · TC-43, TC-45, TC-46, TC-52, TC-25, TC-26, TC-27, TC-28, TC-29 |
| Business rule | 6 · TC-01, TC-04, TC-13, TC-14, TC-20, TC-34 |

## 4.2 The cases


### `tests/test_api.py` · HTTP layer, real routes, templates and authorisation

| ID | Case | Type | Area | Expected result |
|---|---|---|---|---|
| TC-43 | Pages require a session | Authorization | HTTP | Passes, see assertions in the test body. |
| TC-44 | Each role lands on its own home | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-45 | An employee is refused the admin pages | Authorization | HTTP | Passes, see assertions in the test body. |
| TC-46 | A technician is refused the admin pages | Authorization | HTTP | Passes, see assertions in the test body. |
| TC-47 | Reporting an incident through the form works | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-48 | A short title is rejected with a readable message | Invalid input | HTTP | Passes, see assertions in the test body. |
| TC-49 | The live priority preview returns the calculation | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-50 | The category suggestion endpoint works | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-51 | A technician sees only the permitted actions | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-52 | A forged action is refused | Authorization | HTTP | The UI not offering a button is not the control. The service is. |
| TC-53 | An admin can switch strategy from the settings page | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-54 | The search filters combine | Normal operation | HTTP | Passes, see assertions in the test body. |
| TC-55 | A missing incident renders a real error page | Exception | HTTP | Passes, see assertions in the test body. |

### `tests/test_domain.py` · Domain layer, no infrastructure at all

| ID | Case | Type | Area | Expected result |
|---|---|---|---|---|
| TC-01 | New incident cannot jump straight to closed | Business rule | Lifecycle | The problem statement names OPEN -> CLOSED as the transition that must not be allowed without intermediate processing. |
| TC-02 | Full lifecycle runs in order | Normal operation | Lifecycle | Passes, see assertions in the test body. |
| TC-03 | Closed is terminal | Boundary | Lifecycle | Boundary condition: the last state has no exits at all. |
| TC-04 | Resolved can be reopened but not reassigned backwards | Business rule | Lifecycle | Passes, see assertions in the test body. |
| TC-05 | Titles are validated | Invalid input | Validation | Passes, see assertions in the test body. |
| TC-06 | Affected user count is validated (3 inputs) | Invalid input | Validation | Passes, see assertions in the test body. |
| TC-07 | Resolution requires a real explanation | Boundary | Validation | Boundary: exactly at the 10 character minimum passes, under it fails. |
| TC-08 | Feedback is bounded and only after resolution | Boundary | Validation | Passes, see assertions in the test body. |
| TC-09 | Weighted priority matches the documented formula | Normal operation | Priority | Passes, see assertions in the test body. |
| TC-10 | Priority bands cover the whole range | Boundary | Priority | Passes, see assertions in the test body. |
| TC-11 | The two priority strategies are interchangeable and differ | Normal operation | Priority | Polymorphism: same call, same return type, different policy. |
| TC-12 | Each strategy picks a different technician for the same incident | Normal operation | Assignment | Passes, see assertions in the test body. |
| TC-13 | No strategy assigns past a workload ceiling | Business rule | Assignment | Business rule: a technician at capacity is never selected. |
| TC-14 | Inactive technicians are never selected | Business rule | Assignment | Passes, see assertions in the test body. |
| TC-15 | Round robin actually rotates | Normal operation | Assignment | Passes, see assertions in the test body. |
| TC-16 | Assignment with no technicians at all is reported clearly | Exception | Assignment | Passes, see assertions in the test body. |
| TC-17 | Sla deadlines derive from the policy | Normal operation | SLA | Passes, see assertions in the test body. |
| TC-18 | Sla state crosses at the documented thresholds | Boundary | SLA | Boundary: at risk begins at 75 percent of the window, breached past 100. |
| TC-19 | Resolving inside the window counts as met not breached | Boundary | SLA | Passes, see assertions in the test body. |
| TC-20 | Priority change moves the deadline with it | Business rule | SLA | Business rule: priority and SLA cannot drift apart. |

### `tests/test_services.py` · Service layer, real orchestration over in-memory storage

| ID | Case | Type | Area | Expected result |
|---|---|---|---|---|
| TC-21 | Workflow one report prioritise assign notify | Normal operation | Workflow 1 | Employee reports -> system prioritises -> technician assigned -> notified. |
| TC-22 | Workflow two investigate resolve verify close | Normal operation | Workflow 2 | Passes, see assertions in the test body. |
| TC-23 | Workflow three duplicates are detected | Normal operation | Workflow 3 | The problem statement's own example: three reports of one outage. |
| TC-24 | Unrelated incidents are not flagged as duplicates | Boundary | Workflow 3 | Passes, see assertions in the test body. |
| TC-25 | An employee cannot open somebody elses incident | Authorization | Access control | Passes, see assertions in the test body. |
| TC-26 | A technician cannot act on another technicians incident | Authorization | Access control | Passes, see assertions in the test body. |
| TC-27 | A reporter cannot close an incident that is not verified | Authorization | Access control | Business rule and authorisation in one check: the action does not exist for this role in this state, so a crafted post cannot perform it. |
| TC-28 | An employee cannot assign a technician | Authorization | Access control | Passes, see assertions in the test body. |
| TC-29 | Search is scoped to the role | Authorization | Access control | Polymorphic scoping: the same query returns different rows per role. |
| TC-30 | Sign in succeeds with the right password | Normal operation | Authentication | Passes, see assertions in the test body. |
| TC-31 | Bad credentials all fail the same way | Invalid input | Authentication | The message must not reveal whether the address exists. |
| TC-32 | A deactivated account cannot sign in | Exception | Authentication | Passes, see assertions in the test body. |
| TC-33 | Registration rejects a weak password | Invalid input | Authentication | Passes, see assertions in the test body. |
| TC-34 | A retired service cannot be reported against | Business rule | Catalogue | Passes, see assertions in the test body. |
| TC-35 | A missing sla policy is refused with a clear message | Exception | SLA | Exception path: priority computes to P1 but no P1 policy is configured. |
| TC-36 | Changing the assignment strategy changes who gets the next incident | Normal operation | Assignment | The brief requires the strategy to be swappable without a redesign. |
| TC-37 | Automatic categorization fills a blank category | Normal operation | Intelligence | Passes, see assertions in the test body. |
| TC-38 | Sla sweep marks a breach and notifies | Normal operation | SLA | Passes, see assertions in the test body. |
| TC-39 | Escalation fires when a critical incident is not acknowledged | Normal operation | Intelligence | Passes, see assertions in the test body. |
| TC-40 | The audit trail records every state change in order | Normal operation | Audit | Passes, see assertions in the test body. |
| TC-41 | An observer that throws does not break the operation | Exception | Resilience | Resilience: a failing notification channel must not lose an incident. |
| TC-42 | Technician recommendation explains itself | Normal operation | Intelligence | Passes, see assertions in the test body. |
| TC-56 | A transient connection drop is retried | Exception | Resilience | Supabase drops idle HTTP/2 connections. The next call fails before the request is sent, which is a stale socket rather than a real failure. |
| TC-57 | A real error is not retried forever | Exception | Resilience | Passes, see assertions in the test body. |
| TC-58 | A failed audit write does not block a valid sign in | Exception | Resilience | Losing an audit line is bad. Refusing a correct password because the audit table was briefly unreachable is worse. |

## 4.3 The cases worth demonstrating

Four cases carry most of the weight when explaining the design.

**TC-01, OPEN cannot jump straight to CLOSED.** The brief names this transition
specifically as one that must be prevented. The test asserts the status is
unchanged after the attempt and that the error message lists what *is* legal
from here.

**TC-12, each strategy picks a different technician for the same incident.**
Three technicians, one incident, four strategies, three different answers. This
is the Strategy pattern proven rather than claimed.

**TC-52, a forged action is refused.** The interface not showing a button is not
the control. The test posts `resolve` directly to an incident in ASSIGNED state
and asserts a 403 and that the incident did not move.

**TC-41, an observer that throws does not break the operation.** A deliberately
broken observer is subscribed, an incident is reported, and the incident still
persists. Notification failure must not lose work.

