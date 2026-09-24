import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'


class FakeWindow:
    def __init__(self):
        self.values = {}
        self.focus = None
    def getProperty(self, key):
        return self.values.get(key, '')
    def setProperty(self, key, value):
        self.values[key] = value
    def setFocusId(self, value):
        self.focus = value


class AddonsUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.xbmc = MagicMock()
        self.gui = MagicMock()
        self.window = FakeWindow()
        self.gui.Window.return_value = self.window
        addon = MagicMock()
        addon.getAddonInfo.return_value = self.temp.name
        self.xbmcvfs = MagicMock()
        self.xbmcvfs.translatePath.side_effect = lambda value: value
        modules = {
            'xbmc': self.xbmc,
            'xbmcgui': self.gui,
            'xbmcaddon': MagicMock(),
            'xbmcvfs': self.xbmcvfs,
        }
        modules['xbmcaddon'].Addon.return_value = addon
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        sys.path.insert(0, str(ADDON))
        spec = importlib.util.spec_from_file_location('addons_ui_under_test', ADDON / 'addons_ui.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.patch.stop()
        if str(ADDON) in sys.path:
            sys.path.remove(str(ADDON))
        self.temp.cleanup()

    def test_community_filter_updates_visual_browser(self):
        self.window.values['StremioCommunity.Query'] = 'old'
        self.module.community_filter('subtitles')
        self.assertEqual(self.window.values['StremioCommunity.Category'], 'subtitles')
        self.assertEqual(self.window.values['StremioCommunity.Query'], '')
        self.assertEqual(self.window.focus, 50)
        self.xbmc.executebuiltin.assert_called_with('Container.Refresh')

    def test_community_search_updates_visual_browser(self):
        dialog = self.gui.Dialog.return_value
        dialog.input.return_value = 'anime'
        self.module.community_search(dialog)
        self.assertEqual(self.window.values['StremioCommunity.Category'], 'all')
        self.assertEqual(self.window.values['StremioCommunity.Query'], 'anime')
        self.assertEqual(self.window.focus, 50)

    def test_community_action_opens_native_window(self):
        self.module.main('community')
        self.xbmc.executebuiltin.assert_called_with('ActivateWindow(1194)')


if __name__ == '__main__':
    unittest.main()
