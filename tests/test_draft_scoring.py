import tempfile
import unittest
from pathlib import Path
from riftmetrics.draft_scoring import score_pool, load_external_priors


class DraftScoringTests(unittest.TestCase):
    def personal_rows(self, count, win=1):
        return [dict(champion='Briar', role='JUNGLE', queue_id=420,
                     win=win, enemy_jungler='Lillia') for _ in range(count)]

    def test_personal_weight_ramps_with_sample_and_covers_all_personal_paths(self):
        for games, expected in [(0, 0), (1, .0005), (5, .0125), (9, .0405), (10, .05), (30, .15)]:
            result = score_pool(self.personal_rows(games), ['Briar'], 'Lillia', queue_id=420)[0]
            self.assertAlmostEqual(result['personal_weight'], expected)
            self.assertAlmostEqual(result['personal_weight'] + result['neutral_weight'] + result['overall_external_weight'], 1)
            self.assertLessEqual(abs(result['score'] - .5), expected / 2)

    def test_few_personal_wins_do_not_override_bad_external_matchup(self):
        prior = {('briar', 'lillia'): dict(rate=.40, sample=2000)}
        result = score_pool(self.personal_rows(9), ['Briar'], 'Lillia', prior, queue_id=420)[0]
        self.assertLess(result['score'], .5)
        self.assertLess(result['personal_weight'], .05)
        self.assertAlmostEqual(result['overall_external_weight'], .855)

    def test_personal_budget_can_be_disabled_and_missing_external_stays_neutral(self):
        result = score_pool(self.personal_rows(5), ['Briar'], 'Lillia', queue_id=420, personal_max_weight=0)[0]
        self.assertEqual(result['score'], .5)
        self.assertEqual(result['neutral_weight'], 1)

    def test_role_and_queue_filtering(self):
        rows = [
            dict(champion="Warwick", role="JUNGLE", queue_id=400, win=1, enemy_jungler="Kayn"),
            dict(champion="Warwick", role="TOP", queue_id=400, win=0, enemy_jungler="Kayn"),
            dict(champion="Warwick", role="JUNGLE", queue_id=420, win=0, enemy_jungler="Kayn"),
        ]
        score = score_pool(rows, ["Warwick"], "Kayn")[0]
        self.assertEqual((score["games"], score["wins"], score["matchup_games"]), (1, 1, 1))

    def test_external_weight_and_sample_confidence(self):
        prior = {("lillia", "taliyah"): {"rate": .8, "sample": 1000}}
        neutral = score_pool([], ["Lillia"], "Taliyah", prior, external_weight=0)[0]
        weighted = score_pool([], ["Lillia"], "Taliyah", prior, external_weight=.5)[0]
        self.assertEqual(neutral["estimated_rate"], .5)
        self.assertAlmostEqual(weighted["estimated_rate"], .65)
        prior[("lillia", "taliyah")]["sample"] = 10
        small = score_pool([], ["Lillia"], "Taliyah", prior, external_weight=.5)[0]
        self.assertLess(small["score"], weighted["score"])

    def test_multiple_sources_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.csv"
            path.write_text("champion,enemy_jungler,win_rate_pct,sample_size,source\n"
                            "Lillia,Taliyah,60,1000,U.GG\n"
                            "Lillia,Taliyah,40,1000,OP.GG\n")
            prior = load_external_priors(path)[("lillia", "taliyah")]
            self.assertEqual(len(prior["records"]), 2)
            self.assertAlmostEqual(prior["rate"], .5)
            self.assertEqual(prior["sample"], 1000)

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
