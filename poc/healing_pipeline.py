"""Minimal, deterministic Intent-based Healing pipeline proof of concept.

Run: python -m unittest discover -s tests -v
Run demo: python poc/healing_pipeline.py
No external dependencies. Healing is deliberately conservative: ambiguous or
security-sensitive values are never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable


@dataclass
class HealingEvent:
    stage: str
    outcome: str
    changes: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class HealingResult:
    original: dict[str, Any]
    payload: dict[str, Any]
    status: str
    events: list[HealingEvent]
    unresolved: list[str]

    @property
    def healed(self) -> bool:
        return self.status == "HEALED"


class HealingStage:
    name = "abstract"

    def apply(self, payload: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
        raise NotImplementedError


class AliasHealing(HealingStage):
    """Weakest stage: only deterministic field-name aliases."""
    name = "H1_alias"

    aliases = {"userName": "username", "phoneNumber": "phone", "emailAddress": "email"}

    def apply(self, payload, context):
        result = dict(payload)
        changes = {}
        for old, new in self.aliases.items():
            if old in result and new not in result:
                result[new] = result.pop(old)
                changes[old] = new
        return result, [], changes


class TypeCoercionHealing(HealingStage):
    """Converts only unambiguous primitive representations."""
    name = "H1_type_coercion"

    def apply(self, payload, context):
        result = dict(payload)
        changes = {}
        for key, value in list(result.items()):
            if isinstance(value, str):
                stripped = value.strip()
                if key == "age" and re.fullmatch(r"\d{1,3}", stripped):
                    result[key] = int(stripped)
                    changes[key] = {"from": value, "to": result[key]}
                elif key == "active" and stripped.lower() in {"true", "false"}:
                    result[key] = stripped.lower() == "true"
                    changes[key] = {"from": value, "to": result[key]}
        return result, [], changes


class FormatNormalizationHealing(HealingStage):
    """Normalizes formatting but does not invent or repair semantic content."""
    name = "H1_format_normalization"

    def apply(self, payload, context):
        result = dict(payload)
        changes = {}
        if isinstance(result.get("email"), str):
            old = result["email"]
            new = old.strip().lower()
            if new != old:
                result["email"] = new
                changes["email"] = {"from": old, "to": new}
        if isinstance(result.get("phone"), str):
            old = result["phone"]
            new = re.sub(r"[\s().-]", "", old)
            if new != old:
                result["phone"] = new
                changes["phone"] = {"from": old, "to": new}
        return result, [], changes


class ContextualPhoneHealing(HealingStage):
    """Uses explicit, trusted context; never guesses a country code."""
    name = "H2_contextual_phone"

    def apply(self, payload, context):
        result = dict(payload)
        changes = {}
        phone = result.get("phone")
        country_code = context.get("country_calling_code")
        if isinstance(phone, str) and phone and not phone.startswith("+") and country_code:
            digits = re.sub(r"\D", "", phone)
            code = re.sub(r"\D", "", str(country_code))
            if digits and code:
                result["phone"] = f"+{code}{digits}"
                changes["phone"] = {"from": phone, "to": result["phone"], "context": "country_calling_code"}
        return result, [], changes


class HumanNegotiationHealing(HealingStage):
    """Final/strongest stage: resolves only when an explicit human answer exists."""
    name = "H3_human_negotiation"

    def apply(self, payload, context):
        result = dict(payload)
        answers = context.get("human_answers", {})
        changes = {}
        unresolved = []
        for key in ("username", "email", "phone"):
            if not result.get(key):
                answer = answers.get(key)
                if isinstance(answer, str) and answer.strip():
                    result[key] = answer.strip()
                    changes[key] = {"from": result.get(key), "to": answer.strip(), "source": "human"}
                else:
                    unresolved.append(f"missing:{key}")
        # An invalid email is ambiguous; ask a human rather than auto-correcting its domain.
        email = result.get("email")
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(email)):
            answer = answers.get("email")
            if isinstance(answer, str) and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", answer.strip()):
                changes["email"] = {"from": email, "to": answer.strip(), "source": "human"}
                result["email"] = answer.strip()
                unresolved = [item for item in unresolved if item != "missing:email"]
            else:
                unresolved.append("ambiguous_or_invalid:email")
        return result, unresolved, changes


def validate(payload: dict[str, Any]) -> list[str]:
    issues = []
    if not isinstance(payload.get("username"), str) or not payload["username"].strip():
        issues.append("missing_or_invalid:username")
    if not isinstance(payload.get("email"), str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", payload["email"]):
        issues.append("missing_or_invalid:email")
    if not isinstance(payload.get("age"), int) or isinstance(payload.get("age"), bool) or not 0 <= payload["age"] <= 120:
        issues.append("invalid:age")
    if payload.get("phone") is not None and not re.fullmatch(r"\+?\d{8,15}", str(payload["phone"])):
        issues.append("invalid:phone")
    return issues


class HealingPipeline:
    def __init__(self, stages: list[HealingStage] | None = None):
        self.stages = stages or [
            AliasHealing(),
            TypeCoercionHealing(),
            FormatNormalizationHealing(),
            ContextualPhoneHealing(),
            HumanNegotiationHealing(),
        ]

    def run(self, payload: dict[str, Any], context: dict[str, Any] | None = None) -> HealingResult:
        original = dict(payload)
        current = dict(payload)
        context = context or {}
        events = []
        for stage in self.stages:
            before = dict(current)
            current, unresolved, changes = stage.apply(current, context)
            events.append(HealingEvent(stage.name, "changed" if changes else "no_change", changes))
            issues = validate(current)
            if not issues:
                events.append(HealingEvent("validation", "passed"))
                return HealingResult(original, current, "HEALED", events, [])
            events.append(HealingEvent("validation", "still_invalid", reason=", ".join(issues)))
            # Preserve stage-specific unresolved signals in the trace; continue to next stage.
            if unresolved:
                events.append(HealingEvent(stage.name, "needs_input", reason=", ".join(unresolved)))
        issues = validate(current)
        return HealingResult(original, current, "ESCALATED" if issues else "HEALED", events, issues)


def demo():
    cases = [
        ("1. Alias-only: first stage heals", {"userName": "ana", "email": "ana@example.com", "age": 30}),
        ("2. String age: alias stage cannot heal; coercion heals", {"username": "bia", "email": "bia@example.com", "age": "32"}),
        ("3. Formatting: earlier stages cannot heal; normalization heals", {"username": "caio", "email": " CAIO@EXAMPLE.COM ", "age": 28}),
        ("4. Context required: phone heals only with trusted country code", {"username": "duda", "email": "duda@example.com", "age": 24, "phone": "11987654321"}),
        ("5. Missing email: automation cannot invent it; human answer heals", {"username": "eva", "age": 21}),
        ("6. No context or human answer: remains unresolved", {"username": "rui", "age": 40}),
    ]
    pipeline = HealingPipeline()
    for title, payload in cases:
        context = {"country_calling_code": "55"} if title.startswith("4.") else {}
        if title.startswith("5."):
            context["human_answers"] = {"email": "eva@example.com"}
        result = pipeline.run(payload, context)
        print(f"\n{title}\n  status={result.status}; payload={result.payload}")
        for event in result.events:
            if event.outcome != "no_change":
                suffix = f" ({event.reason})" if event.reason else ""
                print(f"  - {event.stage}: {event.outcome}{suffix}")
        if result.unresolved:
            print(f"  unresolved={result.unresolved}")


if __name__ == "__main__":
    demo()
