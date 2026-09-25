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

    def test_python_property_windows_use_runtime_custom_ids(self):
        self.assertEqual(self.module.WINDOW_ID, 1196)
        self.assertEqual(self.module.WINDOW_RUNTIME_ID, 11196)
        self.assertEqual(self.module.CONFIG_WINDOW_ID, 1195)
        self.assertEqual(self.module.CONFIG_WINDOW_RUNTIME_ID, 11195)
        self.assertEqual(self.module.COMMUNITY_WINDOW_ID, 1194)
        self.assertEqual(self.module.COMMUNITY_WINDOW_RUNTIME_ID, 11194)
        self.module.publish()
        self.gui.Window.assert_called_with(11196)
        self.gui.Window.reset_mock()
        self.module.community_init()
        self.gui.Window.assert_called_with(11194)

    def test_duplicate_community_custom_window_is_removed(self):
        skin = ADDON.parent.parent / '1080i'
        self.assertFalse((skin / 'Custom_1194_CommunityAddons.xml').exists())
        self.assertTrue((skin / 'Custom_1194_StremioCommunityAddons.xml').exists())

    def test_community_catalog_route_uses_runtime_window_id(self):
        source = (ADDON / 'default.py').read_text()
        self.assertIn('COMMUNITY_RUNTIME_WINDOW_ID = 11194', source)
        self.assertNotIn('xbmcgui.Window(1194)', source)


if __name__ == '__main__':
    unittest.main()
