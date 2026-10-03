# Intent-based Healing: A Unified Framework for Semantic Error Recovery in Distributed Agentic Systems

**Jean Carlo Nascimento (Suissa)**
AllasCode Institute
suissaidev@gmail.com

---

## Abstract

Contemporary software systems treat errors as terminal states, returning opaque failure signals that discard the semantic content of the originating request. This paper introduces **Intent-based Healing (IbH)**, a design philosophy and architectural framework in which systems preserve, analyze, and act upon user intent rather than halting execution upon encountering malformed or unexpected input. We formalize the distinction between *data* (the payload as received) and *intention* (the semantic goal the payload encodes), and argue that recoverable errors represent not failures but incomplete transformations. We introduce four complementary concepts: the **Healing Pipeline**, a staged remediation model; **Adaptive Observability Negotiation (AON)**, a protocol for surfacing diagnostic state to the appropriate actor; **Human-in-the-Healing-Loop (HitHL)**, a formal role for human collaboration in cases where automated recovery is insufficient; and **Anti-Fragile Intent Accumulation**, the emergent property by which systems that implement IbH improve structurally with each failure. We present empirical cases from production systems, including a CLI self-healing agent (ProjectSupervisor) and an agentic CRM platform, and situate IbH within existing literature on resilience engineering, anti-fragility, and semantic systems. We conclude that opaque error responses are not a technical inevitability but an architectural choice — and a costly one.

**Keywords:** intent-based healing, self-healing systems, anti-fragility, adaptive observability, human-in-the-loop, semantic error recovery, event sourcing, agentic systems

---

## 1. Introduction

The HTTP 500 response has become so normalized in software development that its presence is rarely questioned. Systems receive structured input, identify that the input deviates from expected form, and return a failure signal — discarding all semantic content carried by the original request. This behavior is pervasive across API layers, CLI tooling, validation pipelines, and agentic orchestration frameworks.

We argue that this behavior represents a fundamental architectural deficiency, not a technical constraint.

Consider the following error, produced by a Go application that requires a running PostgreSQL instance:

```
failed to connect to `host=localhost user=postgres database=postgres`:
server error (FATAL: the database system is starting up (SQLSTATE 57P03))
```

This message encodes actionable knowledge: the target host, the expected user, the database name, the failure mode (startup delay rather than misconfiguration), and even the SQLSTATE code. A system equipped to reason about this information can, without human intervention, initiate Docker, execute `docker-compose up -d`, perform a health check against `pg_isready`, and retry the originating command. The error message itself is not an endpoint — it is an invitation to heal.

This paper formalizes the theoretical basis and practical implementation of **Intent-based Healing (IbH)**: a framework in which systems treat recoverable failures as intermediate states in an ongoing semantic negotiation, rather than as definitive termination signals.

The contributions of this paper are:

1. A formal definition of *intent* as the atomic unit of system interaction, distinct from payload or request
2. A taxonomy of error classes by their healability — the degree to which automated or semi-automated recovery is possible
3. A staged Healing Pipeline model with formal termination conditions
4. The **Adaptive Observability Negotiation (AON)** protocol, specifying how diagnostic state is surfaced to the appropriate actor
5. The **Human-in-the-Healing-Loop (HitHL)** role, defining when and how human collaboration is incorporated into the healing process
6. The **Anti-Fragile Intent Accumulation** property, describing system improvement as a function of failure history
7. Empirical cases from production systems

---

## 2. Related Work

### 2.1 Self-Healing in Infrastructure

The dominant literature on self-healing systems addresses infrastructure concerns: service restart policies, container orchestration health checks, circuit breakers, and retry budgets [CITATION: Humble & Farley, 2010; Nygard, 2007]. Kubernetes [CITATION: Burns et al., 2016] exemplifies this paradigm: when a pod fails, it is rescheduled. When a health check fails, the pod is killed and recreated. The system returns to its prior state.

This is **restoration**, not healing. The system does not learn from the failure. It does not improve its response to the class of error that caused the failure. It does not preserve the semantic intent of the operation that was interrupted. It merely resets.

### 2.2 Anti-Fragility

Taleb's concept of anti-fragility [CITATION: Taleb, 2012] provides a theoretical foundation for IbH. Anti-fragile systems are not merely resilient (they do not simply withstand stress) nor merely robust (they do not merely recover from stress). They improve *because of* stress. Each perturbation yields new structural capability.

IbH operationalizes this concept at the application layer: each error that passes through a healing pipeline either resolves automatically, adding a new healing rule to the system's operational memory, or escalates to human collaboration, adding a new case to the system's healability taxonomy.

### 2.3 Intent Recognition

Intent recognition in the context of conversational AI [CITATION: Gao et al., 2019] addresses the problem of inferring semantic goals from natural language utterances. IbH extends this concept to structured system interactions: a malformed API payload, a failed CLI command, or an invalid schema all carry intent that can be partially or fully recovered.

### 2.4 Human-in-the-Loop Systems

Human-in-the-loop (HITL) machine learning [CITATION: Amershi et al., 2014] describes paradigms in which human judgment is incorporated into model training and inference. IbH adopts this structure for a different purpose: not to improve model accuracy, but to resolve cases where automated healing is insufficient and human semantic judgment is required to produce a valid healing rule.

### 2.5 Gap

To our knowledge, no prior work formalizes a unified framework that connects intent preservation, semantic error analysis, staged automated recovery, adaptive observability, and human collaboration into a single architectural paradigm applicable across API layers, CLI tooling, agentic orchestration, and domain logic.

---

## 3. Theoretical Foundation

### 3.1 Defining Intent

Let a **request** $R$ be a tuple $(P, C, \tau)$ where:

- $P$ is the payload as received by the system
- $C$ is the context in which the request was made (route, session, prior state, user profile)
- $\tau$ is the timestamp of the request

We define **intent** $I(R)$ as the semantic goal encoded in $R$, independent of the specific form of $P$. For a POST request to `/users` with payload `{ userName: "alice", phoneNumber: "+5511999999999" }`, the intent is *create a user named Alice with a specified phone number*, regardless of whether the field names match the expected schema (`username`, `phone`).

Formally:

$$I(R) = f(P, C) \rightarrow G$$

where $G$ is a semantic goal drawn from the system's domain model, and $f$ is an intent extraction function that may be rule-based, model-based, or hybrid.

### 3.2 Error Classification by Healability

We propose a four-level taxonomy of errors:

| Level | Class | Definition | Example |
|-------|-------|------------|---------|
| H0 | **Opaque** | System cannot extract intent from the failure | Unstructured panic, corrupted state |
| H1 | **Inferable** | Intent is clear; correction requires no external information | Field name alias, type coercion, format normalization |
| H2 | **Contextual** | Intent is clear; correction requires contextual information | Missing area code inferrable from user locale |
| H3 | **Negotiable** | Intent is partially clear; correction requires human input | Ambiguous value that could satisfy multiple valid forms |

The Healing Pipeline operates on H1–H3 errors. H0 errors constitute the only class where returning an error to the user is architecturally justified — and even then, the error should carry maximum diagnostic content.

### 3.3 The Healability Threshold

For a given system $S$ at time $t$, we define its **healability threshold** $\Theta_S(t)$ as the proportion of all errors observed in $[0, t]$ that were resolved without returning an opaque failure to the user. An IbH-compliant system exhibits:

$$\lim_{t \to \infty} \Theta_S(t) = 1$$

as the system's healing rule base accumulates and covers an increasing proportion of the error space.

---

## 4. The Intent-based Healing Framework

### 4.1 The Healing Pipeline

The Healing Pipeline is a staged execution model with the following formal structure:

```
Intent Extraction → Healability Classification → Automated Healing Attempt
      → [success] → Intent Fulfilled → Log Healing Rule
      → [partial] → AON Escalation → HitHL → Rule Acquisition → Retry
      → [failure] → H0 Response with Maximum Diagnostic Content
```

Each stage has a defined termination condition and a defined escalation path. Critically, **returning an opaque error is never a first-order response**; it is a last resort reached only after H0 classification.

### 4.2 Adaptive Observability Negotiation (AON)

**AON** is a protocol that governs how diagnostic state is surfaced during a healing attempt. It answers the question: *who receives what information, and through what channel?*

We define three observability actors:

- **$A_{sys}$**: the system itself (automated healing layer)
- **$A_{dev}$**: the developer or operator
- **$A_{usr}$**: the end user

And two channel classes:

- **$C_{obs}$**: observability channels (read-only, streaming diagnostic state)
- **$C_{int}$**: interactivity channels (bidirectional, enabling healing collaboration)

In our production implementation, $C_{obs}$ is implemented via Server-Sent Events (SSE), delivering continuous state transitions as the healing pipeline executes. $C_{int}$ is implemented via WebSocket, enabling the relevant actor to submit corrections, confirmations, or new values that are immediately validated against the system's rule base.

The AON protocol selects the appropriate actor and channel pair based on error class:

| Error Class | Primary Actor | Channel |
|-------------|--------------|---------|
| H1 | $A_{sys}$ | None (internal) |
| H2 | $A_{sys}$ | $C_{obs}$ to $A_{dev}$ |
| H3 | $A_{usr}$ | $C_{obs}$ + $C_{int}$ |
| H0 | $A_{dev}$ | $C_{obs}$ with maximum diagnostic payload |

### 4.3 Human-in-the-Healing-Loop (HitHL)

The **HitHL** role is activated for H3 errors: cases where the system has extracted partial intent, identified the failure point, but cannot determine the correct correction without human semantic judgment.

In this role, the human actor is not presented with an error message. They are presented with:

1. The **current state** of the value under validation
2. The **specific rules that the current value violates**, expressed semantically (not as codes)
3. A **real-time validation frontier**: as the user modifies the value, the system continuously evaluates it against all applicable rules and surfaces the result of each rule individually
4. The **behavioral trace**: which system functions the value has passed through, which rules it satisfied, and which rules it failed

The user is invited to iterate. The UI does not submit the value until all applicable rules pass. There is no error return — only a negotiation toward a valid state.

When the user arrives at a valid value through this negotiation, the system records the transformation path (original value → corrected value, the rules that were violated, the corrections applied) as a new healing rule. If a similar case arises in the future, it is promoted to H1 or H2.

This is the mechanism by which human collaboration converts H3 errors into automated healing capability.

Formally, for a human correction event $\epsilon = (v_{invalid}, v_{valid}, R_{violated})$:

$$\text{HealingBase}_{t+1} = \text{HealingBase}_t \cup \{(v_{invalid}, v_{valid}, R_{violated})\}$$

where $R_{violated}$ is the set of rules violated by $v_{invalid}$.

### 4.4 Anti-Fragile Intent Accumulation

The system's HealingBase grows monotonically with each resolved H3 event and each new H1/H2 healing rule derived from automated analysis. This yields the **Anti-Fragile Intent Accumulation** property:

> *A system implementing IbH improves structurally as a direct function of the errors it encounters. Each failure either resolves automatically, enriching the HealingBase, or escalates to HitHL, enriching the HealingBase through human collaboration. The system becomes more capable, not less stable, as it encounters novel failure modes.*

This is the operational implementation of Taleb's anti-fragility at the application layer.

---

## 5. Implementation Evidence

### 5.1 ProjectSupervisor: CLI Self-Healing Agent

ProjectSupervisor is a shell-based IbH implementation for development environment startup errors. It monitors command output in real time, classifies errors against a semantic pattern base, and executes multi-stage remediation pipelines.

The canonical case is the PostgreSQL startup delay error from the evolution-go project:

```
failed to connect to `host=localhost user=postgres database=postgres`:
server error (FATAL: the database system is starting up (SQLSTATE 57P03))
```

Intent extraction identifies: target service (PostgreSQL), failure class (startup delay, not misconfiguration), remediation path (Docker initialization). The healing pipeline:

```conf
postgres_startup_delay|failed to connect to.*postgres.*FATAL: the database system is starting up|external_service|start_docker_desktop,docker_compose_up,postgres_health_check,retry_main_command
```

This is an H1 error. Intent is unambiguous; correction requires no external information. The system executes the pipeline, verifies service health, and retries — without any user interaction.

The same pattern applies to `nvm` version errors: the tool emits the exact command required to resolve its own failure. An IbH-compliant wrapper intercepts that output, extracts the command, executes it, and retries. The error becomes a one-time event.

### 5.2 Intent-based Healing in an Agentic CRM

In a CRM system, every inbound request carries potential commercial value. A payload with a misnamed field (`userName` instead of `username`, `phoneNumber` instead of `phone`, `"32"` instead of `32`, `gmail.con` instead of `gmail.com`) is not a failed request — it is a request whose intent is clear and whose form requires transformation.

The IbH implementation in this system applies the following sequence:

1. **Field alias resolution**: `userName → username`, `phoneNumber → phone`
2. **Type coercion**: `"32" → 32`, `"true" → true`
3. **Format normalization**: phone numbers stripped of formatting, email domains corrected via edit-distance heuristics
4. **Partial intent completion**: missing fields requested via AON, not returned as errors

The result is that no inbound commercial intent is discarded due to payload form. The system either completes the request, transforms it into a valid state, or initiates HitHL negotiation.

### 5.3 EventSourcing as the Enabling Substrate

IbH requires that intent be preserved across time, including across system restarts and session interruptions. EventSourcing [CITATION: Fowler, 2005] provides this substrate: every state transition is recorded as an immutable event in an EventStore.

When a healing negotiation (HitHL) is interrupted — the user stops responding, the session times out, the system restarts — the intent is not lost. It persists as a sequence of events in the EventStore. When the user returns, the system replays the event sequence, restores the negotiation state, and continues from the point of interruption.

This eliminates the "retry from scratch" failure mode entirely. The user's intention was captured at the moment of first contact. All subsequent interaction is continuation, not repetition.

Combined with CQRS [CITATION: Young, 2010], this architecture naturally separates intent capture (commands) from state projection (queries), making the healing pipeline a first-class concern rather than an afterthought in the command processing path.

---

## 6. Discussion

### 6.1 The Opaque Error as Architectural Failure

An opaque error — "Internal Server Error", "Invalid payload", "Field required" — is not a neutral technical response. It is an active discarding of semantic content. The system received information, identified that it did not conform to expected form, and chose to discard it rather than analyze it.

This choice has compounding costs: the user must retry (or abandon), the developer receives no diagnostic value, and the system learns nothing. The same error will occur again, under the same conditions, producing the same opaque response.

IbH reframes this as an architectural bug. The correct response to a recoverable error is not to report the problem, but to attempt recovery; if recovery fails, to negotiate with the appropriate actor; if negotiation fails, to surface maximum diagnostic content.

### 6.2 Scope of Application

The IbH framework applies uniformly across error domains that are typically treated in isolation:

| Domain | Conventional Response | IbH Response |
|--------|----------------------|--------------|
| API validation | 400/422 with error codes | Field alias resolution, type coercion, AON negotiation |
| CLI tool errors | Print error, exit 1 | Extract semantic content, execute remediation pipeline |
| Agentic tool calls | Return error to orchestrator | Correct call parameters, retry with adjusted arguments |
| Playwright selectors | Throw exception | Analyze DOM context, attempt alternative selector derivation |
| Schema validation | Reject payload | Apply transformations, surface specific rule violations via HitHL |
| Environment setup | Abort with error | Detect missing dependencies, install or configure automatically |

The common structure across all domains is: **error as incomplete transformation, not as terminal state**.

### 6.3 Limits and Failure Modes

IbH is not universally applicable. H0 errors — cases where intent cannot be extracted — represent a genuine limit. Security-sensitive contexts may require that certain validation failures terminate immediately without healing attempts, to prevent inference attacks. High-throughput systems may require that the healing pipeline be bounded in latency.

These are design parameters, not arguments against IbH. A system can implement IbH within defined bounds: maximum healing pipeline latency, excluded error classes, rate limits on HitHL negotiation channels.

---

## 7. Formal Properties

We state four formal properties of IbH-compliant systems:

**Property 1 (Intent Preservation):** For every request $R$ with healability class $\geq$ H1, the system maintains $I(R)$ throughout the healing pipeline and does not discard it without exhausting all pipeline stages.

**Property 2 (Monotonic Healing Base Growth):** $|\text{HealingBase}_t|$ is monotonically non-decreasing in $t$ for all healing rule acquisition events.

**Property 3 (HitHL Termination):** The HitHL negotiation for any given error instance terminates in one of two states: (a) value validated, healing rule acquired; (b) user session abandoned, intent preserved in EventStore for future continuation.

**Property 4 (Anti-Fragile Accumulation):** The expected healability of a novel error $e$ at time $t$ is an increasing function of $|\text{HealingBase}_t|$, as the HealingBase covers an increasing proportion of the error space.

---

## 8. Conclusion

We have presented Intent-based Healing as a unified architectural framework for semantic error recovery in software systems. The core claim is straightforward: *a system that can identify why a request failed, and that possesses the context necessary to attempt correction, has an obligation to attempt that correction rather than return an opaque failure signal.*

The theoretical contributions — the intent formalization, the healability taxonomy, the Healing Pipeline model, the AON protocol, the HitHL role, and the Anti-Fragile Accumulation property — provide a basis for rigorous implementation and evaluation.

The empirical cases — ProjectSupervisor, the agentic CRM, the Playwright and ESLint healing implementations — demonstrate that IbH is not a theoretical construct but a practical engineering discipline, applicable across domains and implemented with standard tooling.

The broader implication is cultural. Developers who have implemented IbH report a qualitative shift in their relationship to errors: the second occurrence of a previously encountered error is experienced not as normal but as a system deficiency — evidence that a healing rule should have been created after the first occurrence. This shift, once internalized, propagates: every error becomes a question about automation, not an occasion for manual intervention.

The opaque error is not a law of nature. It is an architectural choice. And it is one we can choose differently.

---

## References

- Amershi, S. et al. (2014). *Power to the People: The Role of Humans in Interactive Machine Learning*. AI Magazine.
- Burns, B. et al. (2016). *Borg, Omega, and Kubernetes*. ACM Queue.
- Fowler, M. (2005). *Event Sourcing*. martinfowler.com.
- Gao, J. et al. (2019). *Dialog State Tracking: A Neural Reading Comprehension Approach*. ACL.
- Humble, J. & Farley, D. (2010). *Continuous Delivery*. Addison-Wesley.
- Nygard, M. (2007). *Release It!*. Pragmatic Bookshelf.
- Taleb, N. N. (2012). *Antifragile: Things That Gain from Disorder*. Random House.
- Young, G. (2010). *CQRS Documents*. cqrs.files.wordpress.com.
