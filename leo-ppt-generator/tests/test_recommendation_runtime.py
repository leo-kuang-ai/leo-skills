from __future__ import annotations

import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "runtime" / "src"))

from leo_ppt_generator.recommendation import recommend_styles


class RecommendationEligibilityTest(unittest.TestCase):
    def test_deck_query_excludes_page_component_only_styles(self) -> None:
        deck = recommend_styles({"domain": "科技", "genre": "发布会"}, limit=20)
        self.assertTrue(deck["candidates"])
        self.assertTrue(all(candidate["verified"] for candidate in deck["candidates"]))
        self.assertTrue(any("page-component" in disclosure
                            for disclosure in deck["disclosures"]))

    def test_browse_query_keeps_unverified_candidates_reachable(self) -> None:
        browse = recommend_styles({"domain": "科技", "genre": "发布会"},
                                  limit=20, deck_query=False)
        self.assertTrue(browse["candidates"])
        self.assertTrue(any(not candidate["verified"]
                            for candidate in browse["candidates"]))


if __name__ == "__main__":
    unittest.main()
