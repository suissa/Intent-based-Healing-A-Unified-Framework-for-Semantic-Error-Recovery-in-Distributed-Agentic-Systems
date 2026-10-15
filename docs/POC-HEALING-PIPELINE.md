# Intent-based Healing — staged proof of concept

This proof of concept demonstrates the central claim of IbH with a small, deterministic payload-validation workflow. It uses only Python's standard library and deliberately avoids infrastructure, agents, LLMs, and external services.

## Run it

From the repository root:

```bash
python poc/healing_pipeline.py
python -m unittest discover -s tests -v
```

## Scenario and staged sequence

The input represents a request to create a customer with `username`, `email`, and `age`, with an optional phone number. Every stage emits a trace event. The pipeline validates after each transformation and stops at the first valid state.

| Order | Healing strategy | What it heals | Deliberate counterexample |
|---|---|---|---|
| 1 — weakest | H1 field aliases | `userName → username` | `age: "32"` remains a string |
| 2 | H1 safe type coercion | `age: "32" → 32` | `email: " USER@EXAMPLE.COM "` remains invalid |
| 3 | H1 format normalization | Trims/lowercases email and strips phone formatting | A local phone number without country context remains invalid |
| 4 | H2 contextual phone completion | Adds a country calling code supplied by trusted context | Missing email cannot be inferred from the payload |
| 5 — strongest | H3 human negotiation | Uses an explicit human-provided answer for a missing/invalid email | Without an answer, the request remains escalated |

The ordering moves from deterministic, local transformations to transformations requiring trusted context and finally explicit human judgment. “Stronger” means broader information access and ability to resolve more cases, not permission to make riskier guesses.

## Expected scenarios

1. Alias-only payload is healed by stage 1.
2. String age defeats stage 1 but is healed by stage 2.
3. Email whitespace/case defeats earlier stages but is healed by stage 3.
4. A local phone number needs a trusted calling code and is healed by stage 4.
5. A missing email is not fabricated; stage 5 heals it only when a human answer is provided.
6. Without context or human input, the request ends as `ESCALATED`, preserving the payload and diagnostics.

## Safety and semantics

- No arbitrary domain correction (for example, `gmail.con → gmail.com`): that guess could silently change user intent.
- No invented personal data. Contextual healing only uses explicitly supplied trusted context. Phone validation requires normalized international format (`+` followed by 8–15 digits), so a local number cannot bypass contextual completion.
- No retry loop; each stage runs once, so the pipeline is bounded and deterministic.
- The original payload, transformed payload, stage outcomes, and validation diagnostics are returned for inspection.
- This is a proof of concept, not a production-ready security boundary. Real systems should add schema/domain-specific validation, authorization checks, audit retention policy, redaction of personal data, and explicit rules for which fields may be healed.

## What this proves — and does not prove

It demonstrates composability: a case rejected by one stage can be repaired by a later stage, while a case requiring unavailable information remains unresolved rather than being guessed. The test suite asserts both healing and non-healing boundaries. It does not establish universal healability or prove that every new failure will become automatically healable; that requires measured rule acquisition and evaluation over a growing corpus.
