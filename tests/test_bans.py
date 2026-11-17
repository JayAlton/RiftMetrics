import unittest
from riftmetrics.ban_assistant import recommend_bans, parse_counter_table
from riftmetrics.draft_scoring import norm


def game(champion, enemy, win, role='TOP'):
    return dict(champion=champion, role=role, queue_id=420, win=win,
                details={'enemy_draft': {'by_role': {role: enemy}}})


class BanTests(unittest.TestCase):
    def test_aliases_produce_one_ban_and_combine_personal_results(self):
        rows = [game('Garen', 'Belveth', False), game('Garen', "Bel'Veth", False),
                game('Garen', 'Chogath', False), game('Garen', "Cho'Gath", False)]
        priors = {}
        for enemy in ["Bel’Veth", "Cho'Gath"]:
            priors[(norm('Garen'), norm(enemy))] = dict(
                rate=.4, sample=1000, records=[{'enemy_jungler': enemy}])
        bans, _, _ = recommend_bans(rows, ['Garen'], 'Garen', 'TOP', priors)
        self.assertEqual({b['enemy'] for b in bans}, {"Bel'Veth", "Cho'Gath"})
        self.assertEqual(len(bans), 2)
        self.assertTrue(all(b['games'] == 2 and b['encounters'] == 2 and b['prior'] for b in bans))

    def test_intended_pick_changes_ban_and_role_history_isolated(self):
        rows = ([game('Garen', 'Darius', False)] * 8 + [game('Garen', 'Teemo', True)] * 8
                + [game('Jax', 'Darius', True)] * 8 + [game('Jax', 'Teemo', False)] * 8
                + [game('Garen', 'Annie', False, 'MIDDLE')] * 100)
        a, _, _ = recommend_bans(rows, ['Garen', 'Jax'], 'Garen', 'TOP')
        b, _, _ = recommend_bans(rows, ['Garen', 'Jax'], 'Jax', 'TOP')
        self.assertEqual(a[0]['enemy'], 'Darius')
        self.assertEqual(b[0]['enemy'], 'Teemo')
        self.assertNotIn('Annie', [r['enemy'] for r in a])

    def test_pool_protected_and_missing_evidence_not_invented(self):
        rows = [game('Garen', 'Jax', False)] * 10
        self.assertEqual(recommend_bans(rows, ['Garen', 'Jax'], 'Garen', 'TOP')[0], [])
        self.assertEqual(recommend_bans([], ['Garen'], 'Garen', 'TOP')[0], [])

    def test_external_counter_and_backup_selection(self):
        rows = [game('Jax', 'Teemo', True)] * 20 + [game('Warwick', 'Teemo', False)] * 20
        prior = dict(rate=.4, sample=1000, patch='16.22', updated_at='2026-11-17',
                     records=[{'enemy_jungler': 'Darius'}])
        bans, backups, _ = recommend_bans(rows, ['Garen','Jax','Warwick'], 'Garen', 'TOP',
                                         {(norm('Garen'), norm('Darius')): prior})
        self.assertEqual(bans[0]['enemy'], 'Darius')
        self.assertEqual(backups[0], 'Jax')
        self.assertEqual(bans[0]['games'], 0)

    def test_counter_table_identity_and_requested_role_verified(self):
        html = ('<select id="selectTier"><option value="iron" selected="">Iron</option></select>'
                'Garen Counters for Top, Patch 16.22 Search a champion Win rate Games '
                'Darius 44.5% 1,234 Teemo 49.0% 200')
        records = parse_counter_table(html, 'Garen', 'TOP', 'Iron')
        self.assertEqual(records[0]['enemy_jungler'], 'Darius')
        self.assertEqual(records[0]['win_rate_pct'], 44.5)
        self.assertEqual(records[0]['sample_size'], 1234)
        with self.assertRaises(ValueError):
            parse_counter_table(html, 'Garen', 'JUNGLE', 'Iron')
