# Use case diagram

Three actors, plus the system itself, which is an actor here because seven
behaviours run without anybody asking.

```mermaid
flowchart LR
    EMP(["Employee"])
    TECH(["Technician"])
    ADMIN(["Administrator"])
    SYS(["System<br/>automated"])

    subgraph uc[" "]
        direction TB
        R1["Register and sign in"]
        R2["Report an incident"]
        R3["Track my incidents"]
        R4["Add information"]
        R5["Confirm the fix"]
        R6["Reopen an incident"]
        R7["Close an incident"]
        R8["Rate the resolution"]

        T1["View assigned queue"]
        T2["Acknowledge an incident"]
        T3["Start investigating"]
        T4["Add investigation notes"]
        T5["Request information"]
        T6["Resolve an incident"]
        T7["View my workload"]

        A1["Monitor all incidents"]
        A2["Assign or reassign"]
        A3["Change priority"]
        A4["Escalate"]
        A5["Manage people and skills"]
        A6["Manage services and SLA"]
        A7["Switch assignment strategy"]
        A8["View reports and analytics"]
        A9["View the audit log"]

        S1["Calculate priority"]
        S2["Classify automatically"]
        S3["Assign automatically"]
        S4["Detect duplicates"]
        S5["Correlate incidents"]
        S6["Monitor SLA and warn"]
        S7["Escalate automatically"]
        S8["Send notifications"]
        S9["Record the audit trail"]
    end

    EMP --- R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8
    TECH --- R1 & T1 & T2 & T3 & T4 & T5 & T6 & T7
    ADMIN --- R1 & A1 & A2 & A3 & A4 & A5 & A6 & A7 & A8 & A9
    SYS --- S1 & S2 & S3 & S4 & S5 & S6 & S7 & S8 & S9

    style uc fill:#F7F8F9,stroke:#E3E6EA
    classDef uc fill:#FFFFFF,stroke:#C3C8D0,color:#16181D
    classDef actor fill:#16181D,stroke:#16181D,color:#FFFFFF
    class R1,R2,R3,R4,R5,R6,R7,R8,T1,T2,T3,T4,T5,T6,T7,A1,A2,A3,A4,A5,A6,A7,A8,A9,S1,S2,S3,S4,S5,S6,S7,S8,S9 uc
    class EMP,TECH,ADMIN,SYS actor

    R2 -.->|includes| S1
    R2 -.->|includes| S2
    R2 -.->|includes| S4
    S1 -.->|includes| S3
    S6 -.->|extends| S7
    S7 -.->|includes| S8
```

## Notes

- **Register and sign in** is shared by all three human actors, which is why it
  appears once with three associations rather than three times.
- **Reporting an incident includes** priority calculation, automatic
  classification and duplicate detection. They are not optional steps a user can
  skip; they run as part of the use case.
- **SLA monitoring extends into escalation**: escalation only happens when the
  monitoring finds a deadline passed, so it is an extension rather than an
  inclusion.
- Authorisation is not drawn as use cases. It is enforced for every one of these
  by `User.require_action`, which consults the role and the state machine
  together.
