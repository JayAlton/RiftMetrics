import unittest
from unittest.mock import patch
from riftmetrics.rank_groups import resolve_ranks, rank_label
from riftmetrics.external_stats import group_rank_records, blend_records
from riftmetrics.live_stats import fetch_pool


class RankGroupTests(unittest.TestCase):
    def row(self, rank, rate, sample, source='OP.GG', patch='16.22', date='2026-11-12'):
        return dict(champion='Warwick', enemy_jungler='Lillia', rank=rank, rate=rate,
                    sample=sample, source=source, patch=patch, region='All regions',
                    queue='420', role='JUNGLE', updated_at=date, expected_rate=None)

    def test_game_weighted_pooling_not_average_of_rates(self):
        rows = [self.row('Iron', .6, 100), self.row('Bronze', .4, 900)]
        pooled = group_rank_records(rows, ('Iron', 'Bronze'))
        self.assertEqual(len(pooled), 1)
        self.assertAlmostEqual(pooled[0]['rate'], .42)
        self.assertEqual(pooled[0]['sample'], 1000)
        self.assertEqual(len(pooled[0]['rank_details']), 2)

    def test_no_cross_patch_or_incomplete_rank_group(self):
        rows = [self.row('Iron', .6, 100), self.row('Bronze', .4, 900, patch='16.21')]
        self.assertEqual(group_rank_records(rows, ('Iron', 'Bronze')), [])
        self.assertEqual(group_rank_records(rows[:1], ('Iron', 'Bronze')), [])

    def test_sources_are_not_counted_as_independent_games(self):
        rows = [self.row(rank, rate, 500, source=source)
                for source, rate in [('OP.GG', .6), ('Lolalytics', .4)]
                for rank in ['Iron', 'Bronze']]
        prior = blend_records(group_rank_records(rows, ('Iron', 'Bronze')))[('warwick', 'lillia')]
        self.assertAlmostEqual(prior['rate'], .5)
        self.assertEqual(prior['sample'], 1000)  # largest source, not 2,000 unique games

    def test_snapshots_deduplicated_before_pooling(self):
        rows = [self.row('Iron', .1, 100, date='2026-11-10'),
                self.row('Iron', .6, 100), self.row('Bronze', .4, 100)]
        result = group_rank_records(rows, ('Iron', 'Bronze'))[0]
        self.assertEqual(result['sample'], 200)
        self.assertAlmostEqual(result['rate'], .5)

    def test_reject_overlapping_custom_filters(self):
        with self.assertRaises(ValueError):
            resolve_ranks(('Emerald', 'Emerald+'))
        self.assertEqual(resolve_ranks('Iron–Silver'), ('Iron', 'Bronze', 'Silver'))
        self.assertEqual(rank_label(('Bronze', 'Iron')), 'Iron + Bronze')
        self.assertEqual(resolve_ranks([]), ())

    def test_fetches_each_rank_separately_and_reuses_rank_specific_cache_api(self):
        with patch('riftmetrics.live_stats.fetch_one') as fetch:
            fetch.return_value = {'record': None}
            results = fetch_pool(['Warwick'], 'Lillia', sources=['OP.GG'], rank=('Iron', 'Bronze'))
            self.assertEqual(len(results), 2)
            self.assertEqual({call.args[-1] for call in fetch.call_args_list}, {'Iron', 'Bronze'})
