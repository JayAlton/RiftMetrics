import tempfile
import unittest
from pathlib import Path
from riftmetrics.draft_scoring import score_pool, load_external_priors


class DraftScoringTests(unittest.TestCase):
    def test_role_and_queue_filtering(self):
        rows = [
            dict(champion="Warwick", role="JUNGLE", queue_id=400, win=1, enemy_jungler="Kayn"),
            dict(champion="Warwick", role="TOP", queue_id=400, win=0, enemy_jungler="Kayn"),
            dict(champion="Warwick", role="JUNGLE", queue_id=420, win=0, enemy_jungler="Kayn"),
        ]
        score = score_pool(rows, ["Warwick"], "Kayn")[0]
        self.assertEqual((score["games"], score["wins"], score["matchup_games"]), (1, 1, 1))

    def test_missing_external_data(self):
        result = score_pool([], ["Lillia"], "Taliyah")[0]
        self.assertIsNone(result["personal_wr"])
        self.assertIsNone(result["external"])

    def test_csv_rejects_invalid_rates(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.csv"
            path.write_text("champion,enemy_jungler,win_rate_pct,sample_size,source,patch,updated_at\n"
                            "Lillia,Taliyah,52,100,site,16.22,2026-11-11\n"
                            "Lillia,Kayn,200,100,site,16.22,2026-11-11\n")
            values = load_external_priors(path)
            self.assertEqual(len(values), 1)
            self.assertAlmostEqual(values[("lillia", "taliyah")]["rate"], .52)


if __name__ == "__main__":
    unittest.main()
