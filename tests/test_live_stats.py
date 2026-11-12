import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import requests
from riftmetrics.live_stats import fetch_one, parse_lolalytics, parse_opgg, page, RANKS, LOL_RANK_LABELS

LOL = '''<script>Wrong 99% Win Rate 999 Games</script>
<div>IRON Patch 16.22</div><h2>Briar jungle vs Lillia jungle Build &amp; Runes</h2>
<p>Briar wins against Lillia 48.5% of the time.</p><div>48.5% Win Rate 1,234 Games</div>
<h3>Core Build</h3><img src="https://cdn5.lolalytics.com/item64/1001.webp" alt="Boots">
<h3>Item 4</h3><img src="https://cdn5.lolalytics.com/item64/9999.webp" alt="Excluded">'''
OP = '''<select id="selectTier"><option value="iron" selected="">Iron</option></select><h1>Briar Counters for Jungle, Patch 16.22</h1>
Search a champion Win rate Games Lee Sin 52.0% 200 Lillia 48.5% 1,234 Ekko 51.0% 900'''


class LiveStatsTests(unittest.TestCase):
    def test_all_ranks_have_distinct_urls_and_verified_source_labels(self):
        self.assertTrue({'Iron', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Emerald',
                         'Diamond', 'Master', 'Grandmaster', 'Challenger', 'All ranks'} <= set(RANKS))
        urls = set()
        for rank, tier in RANKS.items():
            urls.add(page('Lolalytics', 'Briar', 'Lillia', rank))
            lol = LOL.replace('IRON Patch', LOL_RANK_LABELS.get(rank, rank.upper()) + ' Patch')
            op = OP.replace('value="iron"', f'value="{tier}"')
            self.assertEqual(parse_lolalytics(lol, 'Briar', 'Lillia', 'test', rank)[0]['rank'], rank)
            self.assertEqual(parse_opgg(op, 'Briar', 'Lillia', 'test', rank)[0]['rank'], rank)
        self.assertEqual(len(urls), len(RANKS))

    def test_rank_is_in_url_and_wrong_source_rank_is_rejected(self):
        self.assertIn('tier=iron', page('OP.GG', 'Briar', 'Lillia'))
        self.assertNotEqual(page('Lolalytics', 'Briar', 'Lillia', 'Iron'),
                            page('Lolalytics', 'Briar', 'Lillia', 'Emerald+'))
        with self.assertRaises(ValueError):
            parse_lolalytics(LOL.replace('IRON Patch', 'EMERALD+ Patch'), 'Briar', 'Lillia', 'test')
        with self.assertRaises(ValueError):
            parse_opgg(OP.replace('value="iron"', 'value="emerald_plus"'), 'Briar', 'Lillia', 'test')

    def test_rank_specific_cache_does_not_reuse_emerald_data(self):
        with tempfile.TemporaryDirectory() as folder, patch('riftmetrics.live_stats.requests.get') as get:
            emerald = OP.replace('value="iron"', 'value="emerald_plus"')
            get.side_effect = [Mock(text=emerald), Mock(text=OP)]
            high = fetch_one('OP.GG', 'Briar', 'Lillia', folder, rank='Emerald+')
            low = fetch_one('OP.GG', 'Briar', 'Lillia', folder, rank='Iron')
            self.assertEqual(high['record']['rank'], 'Emerald+')
            self.assertEqual(low['record']['rank'], 'Iron')
            self.assertEqual(get.call_count, 2)
            self.assertEqual(len(list(Path(folder).glob('*.json'))), 2)

    def test_lolalytics_matchup_and_core_build(self):
        record, items = parse_lolalytics(LOL, 'Briar', 'Lillia', 'test')
        self.assertEqual(record['win_rate_pct'], 48.5)
        self.assertEqual(record['sample_size'], 1234)
        self.assertEqual(items, [dict(id=1001, name='Boots')])

    def test_opgg_candidate_perspective(self):
        record, _ = parse_opgg(OP, 'Briar', 'Lillia', 'test')
        self.assertEqual(record['win_rate_pct'], 48.5)
        with self.assertRaises(ValueError):
            parse_opgg(OP, 'Darius', 'Lillia', 'test')

    def test_invalid_pages_rejected(self):
        with self.assertRaises(ValueError):
            parse_lolalytics(LOL.replace('jungle vs', 'top vs'), 'Briar', 'Lillia', 'test')
        with self.assertRaises(ValueError):
            parse_lolalytics('<h1>Access denied</h1>', 'Briar', 'Lillia', 'test')

    def test_cache_reuses_all_opgg_matchups_without_network(self):
        with tempfile.TemporaryDirectory() as folder, patch('riftmetrics.live_stats.requests.get') as get:
            get.return_value = Mock(text=OP)
            result = fetch_one('OP.GG', 'Briar', 'Lillia', folder)
            self.assertIsNotNone(result['record'])
            second = fetch_one('OP.GG', 'Briar', 'Ekko', folder)
            self.assertEqual(second['record']['win_rate_pct'], 51)
            self.assertEqual(get.call_count, 1)

    def test_failure_preserves_stale_cache_and_check_date(self):
        with tempfile.TemporaryDirectory() as folder, patch('riftmetrics.live_stats.requests.get') as get:
            get.return_value = Mock(text=LOL)
            first = fetch_one('Lolalytics', 'Briar', 'Lillia', folder)
            path = next(Path(folder).glob('*.json'))
            cached = json.loads(path.read_text())
            cached['fetched_at'] = time.time() - 86400
            cached['attempted_at'] = cached['fetched_at']
            path.write_text(json.dumps(cached))
            get.side_effect = requests.ConnectionError('offline')
            result = fetch_one('Lolalytics', 'Briar', 'Lillia', folder)
            self.assertTrue(result['stale'])
            self.assertEqual(result['record']['win_rate_pct'], first['record']['win_rate_pct'])
            self.assertIn('offline', result['error'])
            fetch_one('Lolalytics', 'Briar', 'Lillia', folder)
            self.assertEqual(get.call_count, 2)  # failure backoff prevents repeated draft delays
