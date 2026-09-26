import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


class DispatchTests(unittest.TestCase):
    def test_resolves_both_install_locations(self):
        for location in ('usr/share/kodi/addons', 'storage/.kodi/addons'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp) / location / 'plugin.video.stremioelec'
                directory.mkdir(parents=True)
                (directory / 'settings_ui.py').touch()
                addon, vfs = MagicMock(), MagicMock()
                addon.Addon.return_value.getAddonInfo.return_value = str(directory)
                vfs.translatePath.side_effect = lambda path: path
                with patch.dict(sys.modules, {'xbmcaddon': addon, 'xbmcgui': MagicMock(), 'xbmcvfs': vfs}):
                    spec = importlib.util.spec_from_file_location('dispatch_test', ROOT / 'extras/stremio_dispatch.py')
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                args = ['dispatch.py', 'settings_ui.py', 'account']
                with patch.object(sys, 'argv', args), patch.object(module.runpy, 'run_path') as run:
                    def verify(path, run_name):
                        self.assertEqual(path, str(directory / 'settings_ui.py'))
                        self.assertEqual(sys.argv, [path, 'account'])
                        self.assertEqual(sys.path[0], str(directory))
                        self.assertEqual(run_name, '__main__')
                    run.side_effect = verify
                    previous_path = sys.path[:]
                    module.main()
                    self.assertEqual(sys.argv, args)
                    self.assertEqual(sys.path, previous_path)
                    run.assert_called_once()

    def test_weather_is_allowed(self):
        with patch.dict(sys.modules, {'xbmcaddon': MagicMock(), 'xbmcgui': MagicMock(), 'xbmcvfs': MagicMock()}):
            spec = importlib.util.spec_from_file_location('dispatch_weather_test', ROOT / 'extras/stremio_dispatch.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        self.assertIn('weather.py', module.SCRIPTS)

    def test_system_core_uses_explicit_addon_identity(self):
        source = (ROOT / 'integration/plugin.video.stremioelec/default.py').read_text()
        self.assertIn("xbmcaddon.Addon('plugin.video.stremioelec')", source)
        self.assertNotIn('xbmcaddon.Addon()', source)

    def test_skin_has_no_assumed_bridge_directory(self):
        for path in (ROOT / '1080i').glob('*.xml'):
            self.assertNotIn('special://home/addons/plugin.video.stremioelec/', path.read_text(), path.name)
