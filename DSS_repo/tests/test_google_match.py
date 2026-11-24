import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from match_google_places import metres, pick_match, plain, similarity  # noqa: E402


def place(pid, name, lat, lon):
    return {"id": pid, "displayName": {"text": name}, "location": {"latitude": lat, "longitude": lon}}


class MatchTests(unittest.TestCase):
    def test_plain_strips_vietnamese_marks(self):
        self.assertEqual(plain("Cầu Sông Hàn – Đà Nẵng!"), "cau song han da nang")

    def test_similarity_ignores_generic_words(self):
        self.assertGreater(similarity("CaPhe Thu Uyen", "Cà phê Thư Uyên"), 0.8)
        self.assertLess(similarity("Cafe Win", "Cafe Anh"), 0.45)
        self.assertEqual(similarity("", "Cafe"), 0.0)

    def test_metres(self):
        self.assertAlmostEqual(metres(16.06, 108.22, 16.06, 108.221), 107, delta=3)

    def test_picks_the_close_similar_candidate(self):
        candidates = [place("far", "Tulip Hotel", 16.2, 108.3), place("other", "Hoa Việt Hotel", 16.0701, 108.2241),
                      place("right", "Tulip Hotel Đà Nẵng", 16.0702, 108.2242)]
        match = pick_match("Tulip Hotel", 16.07, 108.224, candidates)
        self.assertEqual(match["place_id"], "right")
        self.assertLess(match["distance_m"], 60)

    def test_rejects_a_different_place_next_door_and_a_namesake_far_away(self):
        self.assertIsNone(pick_match("Chin Stays", 16.07, 108.224, [place("x", "PNJ", 16.0701, 108.2241)]))
        self.assertIsNone(pick_match("Tulip Hotel", 16.07, 108.224, [place("x", "Tulip Hotel", 16.08, 108.224)]))
        self.assertIsNone(pick_match("Tulip Hotel", 16.07, 108.224, []))
        self.assertIsNone(pick_match("Tulip Hotel", 16.07, 108.224, [{"id": "x", "displayName": {"text": "Tulip Hotel"}}]))


if __name__ == "__main__":
    unittest.main()
