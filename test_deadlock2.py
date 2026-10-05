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
        for index in range(7):
            state.add_chronicle(f"Order {index}.")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "save.json"
            deadlock2.silent_save(state, path)
            loaded = deadlock2.load_state(path)
        self.assertEqual(loaded.race, "Human")
        self.assertEqual(len(loaded.chronicle), 5)


if __name__ == "__main__":
    unittest.main()
