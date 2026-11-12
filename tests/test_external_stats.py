import tempfile
import unittest
from pathlib import Path
from riftmetrics.external_stats import save_record, read_records, blend_records, cohort
from riftmetrics.draft_scoring import score_pool


class ExternalStatsTests(unittest.TestCase):
    def row(self, **values):
        return dict(dict(champion='Briar', enemy_jungler='Lillia', win_rate_pct=48,
            sample_size=1000, source='U.GG', patch='16.22', rank='Emerald+',
            region='All regions', queue='420', role='JUNGLE', updated_at='2026-11-12',
            expected_win_rate_pct=52), **values)

    def test_upsert_preserves_other_sources_and_patches(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'stats.csv'
            for row in [self.row(), self.row(source='OP.GG'), self.row(patch='16.21'), self.row(win_rate_pct=46)]:
                save_record(path, row)
            records = read_records(path)
            self.assertEqual(len(records), 3)
            prior = blend_records(records, cohort(self.row()))[('briar', 'lillia')]
            self.assertAlmostEqual(prior['rate'], .47)
            self.assertAlmostEqual(prior['delta'], -.05)
            self.assertEqual(len(prior['records']), 2)

    def test_never_blends_patches_or_cohorts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'stats.csv'
            for row in [self.row(), self.row(patch='16.21', win_rate_pct=90),
                        self.row(rank='Gold', win_rate_pct=90)]:
                save_record(path, row)
            prior = blend_records(read_records(path), cohort(self.row()))[('briar', 'lillia')]
            self.assertAlmostEqual(prior['rate'], .48)

    def test_unfavorable_matchup_lowers_ranking_and_is_directional(self):
        priors = {('briar', 'lillia'): dict(rate=.40, sample=1000)}
        scores = score_pool([], ['Briar', 'Darius'], 'Lillia', priors)
        self.assertEqual(scores[0]['champion'], 'Darius')
        briar = scores[1]
        self.assertLess(briar['external_score_change'], 0)
        self.assertAlmostEqual(briar['overall_external_weight'], .95 * .90)
        reverse = score_pool([], ['Lillia'], 'Briar', priors)[0]
        self.assertIsNone(reverse['external'])

    def test_head_to_head_slider_controls_score_effect(self):
        prior = {('briar', 'lillia'): dict(rate=.4, sample=1000)}
        no_matchup = score_pool([], ['Briar'], 'Lillia', prior, matchup_weight=0)[0]
        full_matchup = score_pool([], ['Briar'], 'Lillia', prior, matchup_weight=1)[0]
        self.assertEqual(no_matchup['external_score_change'], 0)
        self.assertLess(full_matchup['score'], no_matchup['score'])
