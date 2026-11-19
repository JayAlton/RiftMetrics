import tempfile
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest
from riftmetrics.live_stats import page, fetch_one
from riftmetrics.opgg_items import fetch_items
from test_live_stats import LOL
from test_opgg_items import HTML


class PatchTests(unittest.TestCase):
    def test_patch_urls_and_matchup_cache_isolation(self):
        for source in ['OP.GG', 'Lolalytics']:
            self.assertIn('&patch=16.22', page(source, 'Warwick', 'Fizz', patch='16.22'))
        with tempfile.TemporaryDirectory() as folder, patch('riftmetrics.live_stats.requests.get') as get:
            get.return_value = Mock(text=LOL)
            old = fetch_one('Lolalytics', 'Briar', 'Lillia', folder, patch='16.22')
            self.assertEqual(old['record']['patch'], '16.22')
            get.return_value = Mock(text=LOL.replace('16.22', '16.23'))
            new = fetch_one('Lolalytics', 'Briar', 'Lillia', folder, patch='16.23')
            self.assertEqual(new['record']['patch'], '16.23')
            self.assertEqual(fetch_one('Lolalytics', 'Briar', 'Lillia', folder, patch='16.22')['record']['patch'], '16.22')
            self.assertEqual(get.call_count, 2)
            wrong = fetch_one('Lolalytics', 'Briar', 'Lillia', folder, patch='16.21')
            self.assertIsNone(wrong['record'])
            self.assertIn('instead of requested', wrong['error'])

    def test_items_obey_patch_and_reject_source_default(self):
        with tempfile.TemporaryDirectory() as folder, patch('riftmetrics.opgg_items.requests.get') as get:
            get.return_value = Mock(text=HTML)
            result = fetch_items('Warwick', cache_dir=folder, patch='16.22')
            self.assertEqual(result['data']['patch'], '16.22')
            self.assertIn('&patch=16.22', get.call_args.args[0])
            wrong = fetch_items('Warwick', cache_dir=folder, patch='16.23')
            self.assertIsNone(wrong['data'])
            self.assertIn('instead of requested', wrong['error'])

    def test_sidebar_selection_reaches_draft_and_items(self):
        script = '''import streamlit as st
from riftmetrics.patch_ui import select_stats_patch
from riftmetrics.theme_preview import render_theme_preview
selected = select_stats_patch()
draft, settings = st.tabs(['Draft', 'Weights and Settings'])
with draft:
    render_theme_preview([], '16.23.1', settings_container=settings, stats_patch=selected)
'''
        with patch('riftmetrics.patch_ui.available_patches', return_value=['16.23', '16.22']), \
             patch('riftmetrics.static_data.champion_catalog', return_value={}), \
             patch('riftmetrics.theme_preview.render_external_stats', return_value=({}, [])) as sources, \
             patch('riftmetrics.theme_preview.render_opgg_items') as items:
            app = AppTest.from_string(script).run()
            self.assertFalse(app.exception)
            app.selectbox(key='stats_patch').set_value('16.22').run()
            self.assertFalse(app.exception)
            self.assertEqual(sources.call_args.kwargs['patch'], '16.22')
            self.assertEqual(items.call_args.kwargs['patch'], '16.22')
            app.selectbox(key='stats_patch').set_value('16.23').run()
            self.assertFalse(app.exception)
            self.assertEqual(sources.call_args.kwargs['patch'], '16.23')
            self.assertEqual(items.call_args.kwargs['patch'], '16.23')
