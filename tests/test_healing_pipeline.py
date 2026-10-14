import unittest

from poc.healing_pipeline import (
    AliasHealing,
    ContextualPhoneHealing,
    FormatNormalizationHealing,
    HealingPipeline,
    HumanNegotiationHealing,
    TypeCoercionHealing,
)


class HealingPipelineTests(unittest.TestCase):
    def test_stage_1_alias_heals_alias_only_case(self):
        result = HealingPipeline().run({
            "userName": "ana", "email": "ana@example.com", "age": 30
        })
        self.assertEqual(result.status, "HEALED")
        self.assertEqual(result.payload["username"], "ana")
        self.assertTrue(any(e.stage == "H1_alias" and e.outcome == "changed" for e in result.events))

    def test_alias_stage_does_not_heal_string_age_but_next_stage_does(self):
        payload = {"username": "bia", "email": "bia@example.com", "age": "32"}
        _, _, alias_changes = AliasHealing().apply(payload, {})
        self.assertEqual(alias_changes, {})
        result = HealingPipeline().run(payload)
        self.assertEqual(result.status, "HEALED")
        self.assertEqual(result.payload["age"], 32)
        self.assertTrue(any(e.stage == "H1_type_coercion" and e.outcome == "changed" for e in result.events))

    def test_coercion_does_not_fix_email_whitespace_but_normalization_does(self):
        payload = {"username": "caio", "email": " CAIO@EXAMPLE.COM ", "age": 28}
        _, _, changes = TypeCoercionHealing().apply(payload, {})
        self.assertEqual(changes, {})
        result = HealingPipeline().run(payload)
        self.assertEqual(result.status, "HEALED")
        self.assertEqual(result.payload["email"], "caio@example.com")

    def test_phone_requires_explicit_context(self):
        payload = {"username": "duda", "email": "duda@example.com", "age": 24, "phone": "11987654321"}
        _, _, no_context_changes = ContextualPhoneHealing().apply(payload, {})
        self.assertEqual(no_context_changes, {})
        result = HealingPipeline().run(payload, {"country_calling_code": "55"})
        self.assertEqual(result.status, "HEALED")
        self.assertEqual(result.payload["phone"], "+5511987654321")

    def test_human_negotiation_resolves_missing_email_only_with_answer(self):
        payload = {"username": "eva", "age": 21}
        no_answer = HealingPipeline().run(payload)
        self.assertEqual(no_answer.status, "ESCALATED")
        healed = HealingPipeline().run(payload, {"human_answers": {"email": "eva@example.com"}})
        self.assertEqual(healed.status, "HEALED")
        self.assertEqual(healed.payload["email"], "eva@example.com")

    def test_invalid_email_is_not_silently_guessed(self):
        payload = {"username": "rui", "email": "rui@invalid", "age": 40}
        result = HealingPipeline().run(payload)
        self.assertEqual(result.status, "ESCALATED")
        self.assertIn("missing_or_invalid:email", result.unresolved)

    def test_invalid_age_range_is_not_coerced_into_validity(self):
        result = HealingPipeline().run({"username": "sara", "email": "sara@example.com", "age": "999"})
        self.assertEqual(result.status, "ESCALATED")
        self.assertIn("invalid:age", result.unresolved)

    def test_stage_order_is_weak_to_strong(self):
        names = [stage.name for stage in HealingPipeline().stages]
        self.assertEqual(names, [
            "H1_alias", "H1_type_coercion", "H1_format_normalization",
            "H2_contextual_phone", "H3_human_negotiation"
        ])


if __name__ == "__main__":
    unittest.main()
