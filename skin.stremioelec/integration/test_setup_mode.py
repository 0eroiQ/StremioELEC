import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'


class SetupModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.xbmc = MagicMock()
        addon = MagicMock()
        addon.getAddonInfo.return_value = self.temp.name
        modules = {'xbmc': self.xbmc, 'xbmcaddon': MagicMock(), 'xbmcvfs': MagicMock()}
        modules['xbmcaddon'].Addon.return_value = addon
        modules['xbmcvfs'].translatePath.side_effect = lambda p: p
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        sys.path.insert(0, str(ADDON))
        spec = importlib.util.spec_from_file_location('setup_mode_under_test', ADDON / 'setup_mode.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        if str(ADDON) in sys.path:
            sys.path.remove(str(ADDON))
        self.patch.stop()
        self.temp.cleanup()

    def test_keep_does_not_clear_stremio_state(self):
        with patch.object(self.module, 'Store') as store:
            self.module.apply('keep')
            store.assert_not_called()
        calls = [call.args[0] for call in self.xbmc.executebuiltin.call_args_list]
        self.assertIn('Skin.SetString(StremioSetupMode,keep)', calls)
        self.assertIn('ReplaceWindow(1193)', calls)

    def test_clean_only_clears_owned_stremio_stores(self):
        with patch.object(self.module, 'Store') as store:
            self.module.apply('clean')
        paths = [call.args[0].relative_to(self.module.PROFILE).as_posix()
                 for call in store.call_args_list]
        self.assertEqual(paths, ['.', 'streams', 'playback', 'subtitle-results', 'community', 'setup'])

    def test_developer_mode_unlocks_advanced_playback(self):
        self.module.apply('developer')
        calls = [call.args[0] for call in self.xbmc.executebuiltin.call_args_list]
        self.assertIn('Skin.SetBool(StremioAdvancedPlayback)', calls)
        self.assertIn('Skin.SetBool(StremioDeveloperMode)', calls)

    def test_unknown_mode_fails_before_writes(self):
        with patch.object(self.module, 'Store') as store:
            with self.assertRaises(ValueError):
                self.module.apply('invalid')
            store.assert_not_called()


if __name__ == '__main__':
    unittest.main()
