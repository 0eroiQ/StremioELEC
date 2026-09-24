import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

UI = Path(__file__).parents[1] / 'service.stremioelec.updates' / 'ui.py'


class FakeWindow:
    def __init__(self):
        self.values = {}
    def setProperty(self, key, value):
        self.values[key] = value


class FakeUpdater:
    def __init__(self):
        self.release = {'version': '0.2.0-test.2'}
    def state(self):
        return {'auto_os': True, 'auto_addons': False, 'installed_addons': 0,
                'last_check': 0, 'last_error': ''}
    def ready(self):
        return {'os': {'version': '0.2.0-test.3'}}


class UpdateUiTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        self.xbmc = MagicMock()
        self.gui = MagicMock()
        self.gui.Window.return_value = self.window
        engine = MagicMock()
        engine.device.return_value = FakeUpdater()
        self.patch = patch.dict(sys.modules, {'xbmc': self.xbmc, 'xbmcgui': self.gui, 'engine': engine})
        self.patch.start()
        spec = importlib.util.spec_from_file_location('update_ui_under_test', UI)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.patch.stop()

    def test_publish_exposes_native_screen_state(self):
        self.module.publish(FakeUpdater())
        self.assertEqual(self.window.values['StremioUpdate.Version'], '0.2.0-test.2')
        self.assertEqual(self.window.values['StremioUpdate.Channel'], 'Stable')
        self.assertEqual(self.window.values['StremioUpdate.AutoSystem'], 'ON')
        self.assertEqual(self.window.values['StremioUpdate.AutoInterface'], 'OFF')
        self.assertEqual(self.window.values['StremioUpdate.Ready'], 'System 0.2.0-test.3 ready')

    def test_default_action_opens_native_window(self):
        self.module.main('open')
        self.xbmc.executebuiltin.assert_called_once_with('ActivateWindow(1197)')


if __name__ == '__main__':
    unittest.main()
