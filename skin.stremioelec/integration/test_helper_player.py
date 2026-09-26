import pathlib
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, parse_qs
from unittest.mock import Mock

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from helper_player import stream_identity, resolve


class HelperPlayerTest(unittest.TestCase):
    def test_installed_player_templates_and_trial_rows(self):
        root = pathlib.Path(__file__).parent
        player = json.loads((root / 'helper-players/stremioelec.json').read_text())
        for mode, values, expected in [
            ('play_movie', {'imdb': 'tt0133093'}, ('movie', 'tt0133093')),
            ('play_episode', {'imdb': 'tt123', 'season': '2', 'episode': '3'}, ('series', 'tt123:2:3'))
        ]:
            url = player[mode].format(**values)
            params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
            self.assertEqual(params['action'], 'helper_play')
            self.assertEqual(stream_identity(params), expected)
        rows = ET.parse(root / 'trial-home.xml').getroot().findall('shortcut')
        self.assertEqual(len(rows), 4)
        self.assertIn('action=continue', rows[0].findtext('action'))
        self.assertTrue(all('plugin.video.tmdb.bingie.helper' in r.findtext('action') for r in rows[1:]))

    def test_movie(self):
        self.assertEqual(stream_identity({'kind': 'movie', 'imdb': 'tt0133093'}), ('movie', 'tt0133093'))

    def test_episode_and_special(self):
        self.assertEqual(stream_identity({'kind': 'series', 'imdb': 'tt123', 'season': '00', 'episode': '02'}), ('series', 'tt123:0:2'))

    def test_invalid_id_or_episode(self):
        for values in ({'kind': 'movie', 'imdb': '{imdb}'}, {'kind': 'movie', 'imdb': '603'},
                       {'kind': 'series', 'imdb': 'tt123'},
                       {'kind': 'series', 'imdb': 'tt123', 'season': '1', 'episode': '0'}):
            with self.assertRaises(ValueError):
                stream_identity(values)

    def test_resolve_cancel_empty_and_selection(self):
        for streams, selection, success in [([], 0, False), ([{'label': 'A', 'url': 'https://example.org/a'}], -1, False),
                                            ([{'label': 'A', 'url': 'https://example.org/a'}], 0, True)]:
            collector, dialog, plugin, gui = Mock(), Mock(), Mock(), Mock()
            collector.return_value = streams, 0, 0
            dialog.select.return_value = selection
            resolve({'kind': 'movie', 'imdb': 'tt123'}, [{'manifest': {}}], collector, dialog, plugin, gui, 7)
            self.assertEqual(plugin.setResolvedUrl.call_args.args[:2], (7, success))
            collector.assert_called_once_with([{'manifest': {}}], 'movie', 'tt123')

    def test_no_account(self):
        collector, dialog, plugin, gui = Mock(), Mock(), Mock(), Mock()
        resolve({'kind': 'movie', 'imdb': 'tt123'}, [], collector, dialog, plugin, gui, 7)
        collector.assert_not_called()
        self.assertFalse(plugin.setResolvedUrl.call_args.args[1])
