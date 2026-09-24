import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'


class EpisodeItemTests(unittest.TestCase):
    def setUp(self):
        self.modules = {name: MagicMock() for name in
                        ('xbmc', 'xbmcaddon', 'xbmcvfs', 'xbmcgui', 'xbmcplugin')}
        self.modules['xbmcvfs'].translatePath.return_value = '/unused-test-profile'
        self.modules['xbmcaddon'].Addon.return_value.getSetting.return_value =             'https://v3-cinemeta.strem.io/manifest.json'
        self.patch = patch.dict(sys.modules, self.modules)
        self.patch.start()
        self.argv = patch.object(sys, 'argv',
            ['plugin://plugin.video.stremioelec/', '1', ''])
        self.argv.start()
        self.path = patch.object(sys, 'path', [str(ADDON)] + sys.path)
        self.path.start()
        spec = importlib.util.spec_from_file_location('episode_item_test', ADDON / 'default.py')
        self.entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.entry)

    def tearDown(self):
        self.path.stop()
        self.argv.stop()
        self.patch.stop()

    def test_episode_metadata_and_artwork_are_populated(self):
        list_item = MagicMock()
        tag = list_item.getVideoInfoTag.return_value
        self.modules['xbmcgui'].ListItem.return_value = list_item
        result = self.entry.episode_item({
            'id': 'tt1234567:1:2',
            'season': 1,
            'episode': 2,
            'title': 'The Rising',
            'overview': 'Episode overview',
            'released': '2005-07-22T00:00:00.000Z',
            'thumbnail': 'https://example.com/e2.jpg',
        }, {'name': 'Stargate Atlantis',
            'background': 'https://example.com/show.jpg'})
        self.assertIs(result, list_item)
        self.modules['xbmcgui'].ListItem.assert_called_once_with(
            label='S1 E2 · The Rising')
        tag.setMediaType.assert_called_once_with('episode')
        tag.setTitle.assert_called_once_with('The Rising')
        tag.setSeason.assert_called_once_with(1)
        tag.setEpisode.assert_called_once_with(2)
        tag.setTvShowTitle.assert_called_once_with('Stargate Atlantis')
        tag.setPlot.assert_called_once_with('Episode overview')
        tag.setFirstAired.assert_called_once_with('2005-07-22')
        tag.setYear.assert_called_once_with(2005)
        list_item.setArt.assert_called_once_with({
            'thumb': 'https://example.com/e2.jpg',
            'landscape': 'https://example.com/e2.jpg',
            'poster': 'https://example.com/e2.jpg',
            'fanart': 'https://example.com/show.jpg',
        })

    def test_episode_has_human_fallback_instead_of_unknown(self):
        list_item = MagicMock()
        self.modules['xbmcgui'].ListItem.return_value = list_item
        self.entry.episode_item({'id': 'series:1:3', 'season': 1, 'episode': 3}, {})
        self.modules['xbmcgui'].ListItem.assert_called_once_with(
            label='S1 E3 · Episode 3')
        list_item.getVideoInfoTag.return_value.setTitle.assert_called_once_with(
            'Episode 3')


if __name__ == '__main__':
    unittest.main()
