import unittest
from build import ROOT, render
from simulation import BERTHS, POLICIES, SCENARIOS, Vessel, experiment, manifest, replay


class SimulationTests(unittest.TestCase):
    def test_schedules_preserve_capacity_arrival_and_inputs(self):
        for scenario in SCENARIOS:
            vessels = manifest(101, scenario)
            expected = {v.name: v for v in vessels}
            for policy in POLICIES:
                rows = replay(list(reversed(vessels)), policy)
                self.assertEqual(rows, replay(vessels, policy))
                self.assertCountEqual([r["name"] for r in rows], expected.keys())
                ends = {}
                for row in rows:
                    v = expected[row["name"]]
                    self.assertIn(v.kind, BERTHS[row["berth"]])
                    self.assertGreaterEqual(row["start"], max(v.arrival, ends.get(row["berth"], 0)))
                    self.assertEqual(row["finish"] - row["start"], v.handling)
                    self.assertEqual(row["wait"], row["start"] - v.arrival)
                    ends[row["berth"]] = row["finish"]

    def test_service_estimate_drives_shortest_choice(self):
        vessels = [Vessel("early", "cargo", 0, 0, 400, 10),
                   Vessel("short estimate", "cargo", 1, 1, 30, 500)]
        # Force both to queue for the next free compatible berth.
        blockers = [Vessel("block cargo", "cargo", 0, 0, 1, 65),
                    Vessel("block flexible", "cargo", 0, 0, 1, 80)]
        rows = replay(blockers + vessels, "shortest")
        self.assertEqual(rows[2]["name"], "short estimate")
        self.assertEqual(rows[2]["start"], 65)

    def test_aging_prioritizes_long_wait(self):
        vessels = [Vessel("A", "cargo", 0, 0, 1, 850),
                   Vessel("B", "cargo", 0, 0, 1, 850),
                   Vessel("old", "cargo", 1, 1, 500, 10),
                   Vessel("new", "cargo", 840, 840, 25, 10)]
        self.assertEqual(replay(vessels, "shortest")[2]["name"], "new")
        self.assertEqual(replay(vessels, "aging")[2]["name"], "old")

    def test_unarrived_vessel_cannot_block_a_berth(self):
        vessels = [Vessel("short", "cargo", 0, 100, 1, 2),
                   Vessel("long", "cargo", 0, 10, 90, 50)]
        rows = replay(vessels, "shortest")
        self.assertEqual([(r["name"], r["start"]) for r in rows], [("long", 10), ("short", 100)])

    def test_committed_report_reproduces(self):
        self.assertEqual((ROOT / "index.html").read_text(encoding="utf-8"), render(experiment()))
