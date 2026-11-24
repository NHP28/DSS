import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from kg_schema import build_rows, load_frames, normalize_district, time_slot  # noqa: E402


class KgSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_rows(*load_frames(ROOT / "data" / "danang"))

    def test_time_slots(self):
        self.assertEqual([time_slot(h) for h in (5, 10, 11, 13, 14, 17, 18, 22, 23, 0, 4)],
                         ["morning", "morning", "noon", "noon", "afternoon", "afternoon", "evening", "evening", "night", "night", "night"])

    def test_districts_match_the_api_table(self):
        self.assertEqual(normalize_district("Quận Sơn Trà"), "Sơn Trà")
        self.assertEqual(normalize_district("Hai Chau"), "Hải Châu")
        self.assertEqual(normalize_district("Ngu Hanh Son"), "Ngũ Hành Sơn")
        self.assertEqual(normalize_district("quận Liên Chiểu"), "Liên Chiểu")
        self.assertEqual(normalize_district("Danang"), "Hải Châu")

    def test_node_counts(self):
        rows = self.rows
        self.assertEqual((len(rows["users"]), len(rows["pois"]), len(rows["categories"]), len(rows["districts"]), len(rows["timeslots"])),
                         (1500, 996, 4, 7, 5))

    def test_visits_are_aggregated_without_losing_checkins(self):
        visited = self.rows["visited"]
        self.assertEqual(len({(r["source"], r["target"]) for r in visited}), len(visited))
        self.assertEqual(sum(r["count"] for r in visited), 36210)
        self.assertEqual(sum(r["count"] for r in self.rows["busy_at"]), 36210)
        self.assertEqual(sum(r["count"] for r in self.rows["active_at"]), 36210)

    def test_near_has_five_distinct_neighbours(self):
        near = self.rows["near"]
        self.assertEqual(len(near), 996 * 5)
        self.assertTrue(all(r["source"] != r["target"] and r["km"] >= 0 for r in near))

    def test_friendships_are_unordered_pairs(self):
        pairs = [(r["source"], r["target"]) for r in self.rows["friend_of"]]
        self.assertEqual(len(set(pairs)), len(pairs))
        self.assertTrue(all(a < b for a, b in pairs))

    def test_every_poi_has_category_and_district(self):
        self.assertEqual(len(self.rows["in_category"]), 996)
        self.assertEqual(len(self.rows["located_in"]), 996)


if __name__ == "__main__":
    unittest.main()
