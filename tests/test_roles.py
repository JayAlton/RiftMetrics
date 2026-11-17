import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from riftmetrics.roles import ROLES
from riftmetrics.draft_scoring import score_pool
from riftmetrics.external_stats import save_record, read_records
from riftmetrics.live_stats import page, parse_opgg, parse_lolalytics, record


def draft_app():
    from riftmetrics.draft_assistant import render_live_draft
    render_live_draft([], '16.22', stats_rank='Iron')


class RoleTests(unittest.TestCase):
    def test_history_and_opponents_are_role_specific(self):
        rows = [dict(role=r, queue_id=420, champion='Lux', win=r == 'MIDDLE',
                     enemy_jungler='Lillia', details={'enemy_draft': {'by_role':
                     {r: 'Annie'}}}) for r in ROLES]
        for role in ROLES:
            result = score_pool(rows, ['Lux'], 'Annie', role=role)[0]
            self.assertEqual(result['games'], 1)
            self.assertEqual(result['matchup_games'], 1)
            self.assertEqual(result['wins'], int(role == 'MIDDLE'))

    def test_sources_verify_role_and_separate_urls(self):
        for role, (_, lane, _) in ROLES.items():
            with self.subTest(role=role):
                url = page('Lolalytics', 'Lux', 'Annie', role=role)
                self.assertIn('lane=' + lane, url)
                html = (f'IRON Patch 16.22 Lux {lane} vs Annie {lane} Build &amp; Runes '
                        'Lux wins against Annie 51% of the time. 51% Win Rate 100 Games')
                self.assertEqual(parse_lolalytics(html, 'Lux', 'Annie', url, role=role)[0]['role'], role)
                op = ('<select id="selectTier"><option value="iron" selected="">Iron</option></select>'
                      f'Lux Counters for {lane.title()}, Patch 16.22 '
                      'Search a champion Win rate Games Annie 51% 100')
                self.assertEqual(parse_opgg(op, 'Lux', 'Annie', url, role=role)[0]['role'], role)
                other = 'TOP' if role != 'TOP' else 'JUNGLE'
                with self.assertRaises(ValueError):
                    parse_lolalytics(html, 'Lux', 'Annie', url, role=other)
        self.assertIn('/mid?', page('OP.GG', 'Lux', 'Annie', role='MIDDLE'))
        self.assertIn('/adc?', page('OP.GG', 'Lux', 'Annie', role='BOTTOM'))

    def test_saving_role_preserves_other_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'priors.csv'
            for role in ROLES:
                save_record(path, record('Lux', 'Annie', 51, 100, '16.22', 'OP.GG', 'https://example.com', role=role))
            for role in ROLES:
                self.assertEqual([r['role'] for r in read_records(path, role=role)], [role])

    def test_every_role_page_renders(self):
        with patch('riftmetrics.static_data.champion_catalog', return_value={}), \
             patch('riftmetrics.draft_assistant.champion_catalog', return_value={}):
            app = AppTest.from_function(draft_app).run()
            for role in ROLES:
                app.radio[0].set_value(role).run()
                self.assertFalse(app.exception)
                self.assertIn(ROLES[role][0], app.subheader[0].value)
