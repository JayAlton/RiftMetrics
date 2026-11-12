import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch
from riftmetrics.storage import connect
from riftmetrics.detail_storage import backfill
import main as importer


class ImportDetailsTests(unittest.TestCase):
    def test_import_populates_details_and_repeat_import_does_not_duplicate(self):
        db = connect(':memory:')
        self.addCleanup(db.close)
        player = dict(puuid='player-id', teamId=100, championName='Warwick', teamPosition='JUNGLE',
                      win=True, kills=4, deaths=2, assists=8, goldEarned=10000,
                      totalDamageDealtToChampions=12000)
        enemy = dict(puuid='enemy-id', teamId=200, championName='Lillia', teamPosition='JUNGLE')
        match = dict(metadata=dict(matchId='NA1_TEST'), info=dict(
            gameStartTimestamp=1794490000000, gameDuration=1800, queueId=420,
            participants=[player, enemy], teams=[]))
        client = Mock()
        client.account.return_value = dict(puuid='player-id', gameName='Player', tagLine='NA1')
        client.match_ids.return_value = ['NA1_TEST']
        client.match.return_value = match
        client.ranked.return_value = []
        with patch.object(importer, 'connect', return_value=db), \
             patch.object(importer, 'RiotClient', return_value=client), \
             patch.object(importer, 'export_champions'), \
             patch.object(importer, 'load_dotenv'), \
             patch.object(importer.time, 'sleep'), \
             patch('sys.argv', ['main.py', '--games', '1', '--queue', '420']), \
             contextlib.redirect_stdout(io.StringIO()):
            importer.main()
            importer.main()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM matches').fetchone()[0], 1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM match_details').fetchone()[0], 1)
        details = json.loads(db.execute('SELECT details_json FROM match_details').fetchone()[0])
        self.assertEqual(details['enemy_jungler'], 'Lillia')
        self.assertEqual(details['kills'], 4)
        # PUUID resolves identity even when Riot ID fields are absent in cached JSON.
        self.assertEqual(details['champion'], 'Warwick')

    def test_malformed_cached_match_reports_failure(self):
        db = connect(':memory:')
        self.addCleanup(db.close)
        db.execute("INSERT INTO matches (match_id, played_at, champion, win, raw_json) VALUES ('BAD', 'today', 'Warwick', 1, '{}')")
        count, failed = backfill(db, 'Player', 'NA1')
        self.assertEqual(count, 0)
        self.assertEqual(failed[0][0], 'BAD')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM matches').fetchone()[0], 1)
