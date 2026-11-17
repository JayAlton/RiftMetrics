import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from riftmetrics.opgg_items import parse_items, fetch_items

HTML = '''<h1>Warwick Items for Jungle, Patch 16.22</h1>
<select id="selectTier"><option value="iron" selected="">Iron</option></select>
<h2>Items</h2><table><tr><td><img src="https://cdn/item/3153.png" alt="">Blade of The Ruined King</td>
<td>80.41% 36,290 Games</td><td>51.34%</td></tr></table>
<h2>Core builds</h2><table><tr><td><img src="https://cdn/item/6631.png" alt="Stridebreaker">
<img src="https://cdn/item/3153.png" alt="Blade of The Ruined King"></td>
<td>10.45% 2,677 Games</td><td>54.80%</td></tr></table>
<script>Items 99% 999999 Games</script>'''


class OpggItemsTests(unittest.TestCase):
    def test_tables_keep_combination_stats_and_names(self):
        data = parse_items(HTML, 'Warwick', 'JUNGLE', 'Iron')
        self.assertEqual(data['patch'], '16.22')
        item, combo = data['rows']
        self.assertEqual(item['items'][0]['name'], 'Blade of The Ruined King')
        self.assertEqual((item['games'], item['pick_rate_pct'], item['win_rate_pct']), (36290, 80.41, 51.34))
        self.assertEqual(len(combo['items']), 2)
        self.assertEqual(combo['win_rate_pct'], 54.8)
        self.assertNotIn('win_rate_pct', combo['items'][0])

    def test_wrong_identity_role_rank_and_missing_tables_rejected(self):
        for champion, role, rank in [('Jax', 'JUNGLE', 'Iron'), ('Warwick', 'TOP', 'Iron'), ('Warwick', 'JUNGLE', 'Bronze')]:
            with self.assertRaises(ValueError):
                parse_items(HTML, champion, role, rank)
        with self.assertRaises(ValueError):
            parse_items(HTML.split('<h2>')[0], 'Warwick', 'JUNGLE', 'Iron')

    def test_cache_refresh_and_stale_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch('riftmetrics.opgg_items.requests.get') as get, patch('riftmetrics.opgg_items.time.time', return_value=100000):
            get.return_value = Mock(text=HTML)
            first = fetch_items('Warwick', cache_dir=directory)
            self.assertEqual(first['data']['rank'], 'Iron')
            fetch_items('Warwick', cache_dir=directory)
            self.assertEqual(get.call_count, 1)
            with patch('riftmetrics.opgg_items.time.time', return_value=200000):
                get.side_effect = requests.RequestException('offline')
                stale = fetch_items('Warwick', cache_dir=directory)
            self.assertTrue(stale['stale'])
            self.assertEqual(stale['error'], 'offline')
            self.assertEqual(stale['data'], first['data'])
            missing = fetch_items('Warwick', rank='Bronze', cache_dir=directory)
            self.assertIsNone(missing['data'])
