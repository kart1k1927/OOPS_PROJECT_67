# System architecture

Layered. Each layer depends only on the one below it, and the dependency at the
bottom is on an interface rather than on Supabase, which is what lets the test
suite substitute an in-memory implementation.

```mermaid
flowchart TB
    subgraph client["BROWSER"]
        direction LR
        UI["Jinja2 pages<br/>employee · technician · admin"]
        JS["report.js<br/>live priority preview"]
    end

    subgraph api["API LAYER · app/api"]
        direction LR
        ROUTE["Routers<br/>pages · auth · incidents<br/>technicians · admin"]
        DEPS["Dependencies<br/>current user · role gates"]
        ERR["Exception handlers<br/>ITSMError to HTTP"]
    end

    subgraph service["SERVICE LAYER · app/services"]
        direction LR
        INC["IncidentService<br/>single authorised write path"]
        SLA["SLAService<br/>background sweep, 60s"]
        INTEL["intelligence/<br/>duplicates · categorizer<br/>escalation · risk · recommender"]
        OTHER["AuthService<br/>NotificationService<br/>ReportingService"]
    end

    subgraph domain["DOMAIN LAYER · app/domain"]
        direction LR
        ENT["Incident<br/>User hierarchy<br/>SLATracker"]
        STATE["IncidentState<br/>State pattern"]
        STRAT["AssignmentStrategy<br/>PriorityStrategy<br/>Strategy pattern"]
        BUS["EventBus<br/>Observer pattern"]
    end

    subgraph repo["REPOSITORY LAYER · app/repositories"]
        direction LR
        IFACE["Repository interfaces<br/>abstract"]
        SUPA["Supabase<br/>implementation"]
        MEM["In-memory<br/>implementation<br/>used by tests"]
    end

    DB[("PostgreSQL · Supabase<br/>9 tables · RLS enabled")]

    client ==> api
    api ==> service
    service ==> domain
    service ==> repo
    domain -.->|events| service
    SUPA ==> DB
    SUPA -.->|implements| IFACE
    MEM -.->|implements| IFACE

    classDef box fill:#FFFFFF,stroke:#C3C8D0,color:#16181D
    classDef store fill:#EFF1F3,stroke:#16181D,color:#16181D
    class UI,JS,ROUTE,DEPS,ERR,INC,SLA,INTEL,OTHER,ENT,STATE,STRAT,BUS,IFACE,SUPA,MEM box
    class DB store
    style client fill:#F7F8F9,stroke:#E3E6EA
    style api fill:#F7F8F9,stroke:#E3E6EA
    style service fill:#F7F8F9,stroke:#E3E6EA
    style domain fill:#F7F8F9,stroke:#E3E6EA
    style repo fill:#F7F8F9,stroke:#E3E6EA
```

## Why it is shaped this way

**Business logic sits in the domain and service layers.** The routers validate
input, call a service and render. The database holds data and constraints. The
two triggers that originally did technician assignment and SLA arithmetic in
plpgsql were dropped by migration 002, because logic in two engines drifts and
logic buried in plpgsql earns nothing on an object oriented rubric.

**The dependency at the bottom points at an interface.** `IncidentService` holds
a `Repository`, not a `SupabaseIncidentRepository`. That is why
`scripts/demo_server.py` can run the entire application with no database and why
all 71 tests run with no network.

**The SLA monitor has its own connection pool.** It runs on a worker thread every
60 seconds. Sharing one pool with request handling caused intermittent 503s,
because Supabase drops idle HTTP/2 connections and both sides kept picking up
sockets the other had abandoned.
