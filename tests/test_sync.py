import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from riftmetrics import sync
from riftmetrics.storage import connect


class SyncTests(unittest.TestCase):
    def test_both_queues_refresh_details_exports_and_skip_duplicates(self):
        client = Mock()
        client.account.return_value = {'puuid': 'player'}
        client.match_ids.side_effect = lambda puuid, start, count, queue: [f'NA1_{queue}']

        def match(match_id):
            return {'metadata': {'matchId': match_id}, 'info': {
                'queueId': int(match_id.split('_')[1]),
                'gameStartTimestamp': 1794490000000, 'gameDuration': 1800,
                'participants': [dict(puuid='player', teamId=100, championName='Warwick',
                                      teamPosition='JUNGLE', win=True, kills=4, deaths=2,
                                      assists=8, goldEarned=10000,
                                      totalDamageDealtToChampions=12000)], 'teams': []}}

        client.match.side_effect = match
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(sync, 'RiotClient', return_value=client), \
             patch.object(sync, 'load_dotenv'), \
             patch('main.time.sleep'), contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory) / 'data' / 'riftmetrics.db'
            counts, detailed, failed = sync.sync_recent_games(path, 20)
            self.assertEqual(counts, {420: 1, 400: 1})
            self.assertEqual((detailed, failed), (2, []))
            self.assertEqual(sync.sync_recent_games(path, 20)[0], {420: 0, 400: 0})
            self.assertEqual(client.match.call_count, 2)
            with contextlib.closing(connect(path)) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM match_details').fetchone()[0], 2)
            for queue in (400, 420):
                self.assertIn('Warwick', (path.parent / f'champion_stats_{queue}.csv').read_text(encoding='utf-8-sig'))
        self.assertEqual(client.session.close.call_count, 2)

    def test_api_failure_closes_client(self):
        client = Mock()
        client.account.side_effect = ValueError('Unavailable')
        with patch.object(sync, 'RiotClient', return_value=client), patch.object(sync, 'load_dotenv'):
            with self.assertRaisesRegex(ValueError, 'Unavailable'):
                sync.sync_recent_games('data/riftmetrics.db')
        client.session.close.assert_called_once()
