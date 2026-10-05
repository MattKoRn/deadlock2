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

    def test_random_map_is_repeatable_by_seed_and_changes_with_seed(self):
        first = deadlock2.build_random_map("Human", seed=12345)
        second = deadlock2.build_random_map("Human", seed=12345)
        third = deadlock2.build_random_map("Human", seed=54321)
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertNotIn("Human", first.rival_races)

    def test_world_victory_generates_new_map_and_keeps_research(self):
        state = deadlock2.GameState(race="Human")
        state.world_map = deadlock2.build_random_map("Human", seed=100)
        state.researched_technologies.extend(["Electronics", "Metallurgy"])
        old_scale = state.enemy_scale_rating()
        state.complete_world(seed=200)
        self.assertEqual(state.world_number, 2)
        self.assertEqual(state.worlds_completed, 1)
        self.assertGreater(state.permanent_power, 0)
        self.assertEqual(state.world_map.seed, 200)
        self.assertEqual(state.researched_technologies, ["Electronics", "Metallurgy"])
        self.assertGreater(state.enemy_scale_rating(), old_scale)

    def test_enemy_scale_never_caps(self):
        state = deadlock2.GameState(
            race="Human",
            world_number=10**50,
            worlds_completed=10**50,
            permanent_power=10**200,
        )
        first = state.enemy_scale_rating()
        state.world_number += 1
        state.permanent_power *= 10**20
        second = state.enemy_scale_rating()
        self.assertGreater(second, first)
        self.assertGreater(second, 10**50)

    def test_suffixes_continue_beyond_trillion_without_cap(self):
        self.assertEqual(deadlock2.format_big_number(10**3), "1K")
        self.assertEqual(deadlock2.format_big_number(10**6), "1M")
        self.assertEqual(deadlock2.format_big_number(10**9), "1B")
        self.assertEqual(deadlock2.format_big_number(10**12), "1T")
        self.assertEqual(deadlock2.format_big_number(10**15), "1aa")
        self.assertEqual(deadlock2.format_big_number(10**18), "1ab")
        huge = deadlock2.format_big_number(10**300)
        self.assertTrue(huge.startswith("1"))
        self.assertGreater(len(huge), 2)

    def test_save_round_trip_keeps_eternal_progress(self):
        state = deadlock2.GameState(
            race="Human",
            world_number=10**25,
            worlds_completed=10**25 - 1,
            permanent_power=10**150,
        )
        state.world_map = deadlock2.build_random_map("Human", seed=777)
        state.researched_technologies.extend(["Electronics", "Metallurgy"])
        for index in range(7):
            state.add_chronicle(f"Order {index}.")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "save.json"
            deadlock2.silent_save(state, path)
            loaded = deadlock2.load_state(path)
        self.assertEqual(loaded.world_number, 10**25)
        self.assertEqual(loaded.worlds_completed, 10**25 - 1)
        self.assertEqual(loaded.permanent_power, 10**150)
        self.assertEqual(loaded.world_map.seed, 777)
        self.assertEqual(loaded.researched_technologies, ["Electronics", "Metallurgy"])
        self.assertEqual(len(loaded.chronicle), 5)

    def test_chronicle_color_semantics_are_stable(self):
        self.assertEqual(
            deadlock2.chronicle_pair_for_detail("Rejected focus because task is blocked."),
            deadlock2.PAIR_DANGER,
        )
        self.assertEqual(
            deadlock2.chronicle_pair_for_detail("Completed research order for Metallurgy."),
            deadlock2.PAIR_RESEARCH,
        )
        self.assertEqual(
            deadlock2.chronicle_pair_for_detail("Completed Eternal World 12 and generated Eternal World 13."),
            deadlock2.PAIR_WORLD,
        )
        self.assertEqual(
            deadlock2.chronicle_pair_for_detail("Colony Assistant decision #4 changed focus."),
            deadlock2.PAIR_INFO,
        )
        self.assertEqual(
            deadlock2.chronicle_pair_for_detail("Issued manual Build order."),
            deadlock2.PAIR_GOOD,
        )



if __name__ == "__main__":
    unittest.main()
