import tempfile
import unittest
from pathlib import Path

import deadlock2


class ChronicleRulesTests(unittest.TestCase):
    def test_chronicle_keeps_only_five_actions(self):
        state = deadlock2.GameState()
        for index in range(8):
            state.add_chronicle(f"Detailed action {index}.", epoch=1_700_000_000 + index)
        self.assertEqual(len(state.chronicle), 5)
        self.assertEqual(state.chronicle[0].detail, "Detailed action 3.")
        self.assertEqual(state.chronicle[-1].detail, "Detailed action 7.")

    def test_timestamp_has_no_seconds(self):
        stamp = deadlock2.timestamp_12h(1_700_000_000)
        self.assertRegex(stamp, r"^\d{1,2}:\d{2} (AM|PM)$")

    def test_assistant_applies_exactly_one_decision_per_full_minute(self):
        state = deadlock2.GameState(last_assistant_epoch=1_000.0)
        applied = state.apply_due_assistant_decisions(1_181.0)
        self.assertEqual(applied, 3)
        self.assertEqual(state.assistant_decisions, 3)
        self.assertEqual(state.last_assistant_epoch, 1_180.0)

    def test_offline_progress_uses_same_minute_cadence(self):
        state = deadlock2.GameState(
            last_assistant_epoch=2_000.0,
            last_active_epoch=2_000.0,
        )
        report = deadlock2.apply_offline_progress(state, now=2_125.0)
        self.assertEqual(report.away_seconds, 125)
        self.assertEqual(report.decisions_applied, 2)
        self.assertEqual(state.assistant_decisions, 2)

    def test_save_round_trip_retains_five_chronicle_entries(self):
        state = deadlock2.GameState(race="Human")
        state.researched_technologies.extend(["Electronics", "Metallurgy"])
        for index in range(7):
            state.add_chronicle(f"Order {index}.")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "save.json"
            deadlock2.silent_save(state, path)
            loaded = deadlock2.load_state(path)
        self.assertEqual(loaded.race, "Human")
        self.assertEqual(len(loaded.chronicle), 5)
        self.assertEqual(loaded.researched_technologies, ["Electronics", "Metallurgy"])

    def test_advanced_resource_tasks_are_technology_gated(self):
        state = deadlock2.GameState()
        self.assertFalse(state.can_use_task("Mine Endurium"))
        self.assertFalse(state.can_use_task("Electronic Parts"))
        self.assertFalse(state.can_use_task("Iron to Steel"))
        self.assertFalse(state.can_use_task("Endurium to Triidium"))
        self.assertFalse(state.can_use_task("Anti-Matter Pods"))

    def test_metallurgy_unlocks_iron_to_steel(self):
        state = deadlock2.GameState(researched_technologies=["Metallurgy"])
        self.assertTrue(state.can_use_task("Iron to Steel"))
        self.assertFalse(state.can_use_task("Endurium to Triidium"))

    def test_research_prerequisites_unlock_in_canon_order(self):
        state = deadlock2.GameState()
        self.assertIn("Nuclear Fusion", state.eligible_technologies())
        self.assertIn("Electronics", state.eligible_technologies())
        self.assertIn("Metallurgy", state.eligible_technologies())
        self.assertNotIn("Chaos Computer", state.eligible_technologies())
        state.researched_technologies.extend(["Nuclear Fusion", "Electronics"])
        self.assertIn("Chaos Computer", state.eligible_technologies())

    def test_assistant_never_selects_blocked_task(self):
        state = deadlock2.GameState(last_assistant_epoch=1_000.0)
        for minute in range(1, 20):
            state.make_assistant_decision(1_000.0 + minute * 60)
            self.assertTrue(state.can_use_task(state.assistant_focus))

    def test_canon_metal_values(self):
        self.assertEqual(
            deadlock2.METAL_VALUES,
            {"Iron": 1, "Steel": 5, "Endurium": 5, "Tridium": 10},
        )


if __name__ == "__main__":
    unittest.main()
