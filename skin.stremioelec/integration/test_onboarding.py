import pathlib
import importlib.util
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch, Mock
from account import create_link_details

ROOT = pathlib.Path(__file__).resolve().parents[1]


class OnboardingTest(unittest.TestCase):
    def test_linked_account_setup_precedes_home_and_failure_stays_in_setup(self):
        from account import Store
        for fails in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                Store(folder).save({'token': 'test-token', 'addons': []})
                props = {}
                home = Mock()
                home.getProperty.side_effect = lambda name: props.get(name, '')
                home.setProperty.side_effect = lambda name, value: props.__setitem__(name, value)
                home.clearProperty.side_effect = lambda name: props.pop(name, None)
                kodi, addon, gui, vfs = Mock(), Mock(), Mock(), Mock()
                kodi.Monitor.return_value.abortRequested.return_value = False
                gui.Window.return_value = home
                addon.Addon.return_value.getAddonInfo.return_value = folder
                vfs.translatePath.side_effect = lambda path: path
                with patch.dict(sys.modules, {'xbmc': kodi, 'xbmcaddon': addon, 'xbmcgui': gui, 'xbmcvfs': vfs}):
                    spec = importlib.util.spec_from_file_location('onboarding_under_test', ROOT / 'integration/plugin.video.stremioelec/onboarding.py')
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    with patch.object(module, 'pull_addons', return_value=([], 0)), \
                         patch.object(module, 'pull_library', return_value=[]), \
                         patch('setup_profile.prepare', side_effect=RuntimeError() if fails else None) as prepare:
                        module.run()
                        prepare.assert_called_once()
                    actions = [call.args[0] for call in kodi.executebuiltin.call_args_list]
                    self.assertEqual('ReplaceWindow(Home)' in actions, not fails)
                    self.assertEqual(bool(props.get('StremioOnboardingReady')), not fails)
                    self.assertNotIn('StremioOnboardingBusy', props)

    def test_fresh_install_opens_welcome(self):
        root = ET.parse(ROOT / '1080i/IncludesVariables.xml').getroot()
        self.assertEqual(root.find("variable[@name='StartUpWindow']/value").text, '1101')

    def test_welcome_does_not_mutate_device_settings(self):
        root = ET.parse(ROOT / '1080i/Custom_1101_StartUp.xml').getroot()
        actions = [node.text for node in root.findall('.//onclick')]
        self.assertIn('ReplaceWindow(1102)', actions)
        self.assertFalse(any('kodisetting' in action.lower() for action in actions))
        self.assertFalse(any('Settings.SetSettingValue' in action for action in actions))
        buttons = root.findall(".//control[@type='button']")
        self.assertEqual([b.findtext('label') for b in buttons], ['Start Setup', 'Exit Setup'])
        self.assertEqual(buttons[1].findtext('visible'),
                         'System.HasAddon(service.stremioelec.portable)')

    def test_qr_and_ready_state_are_wired(self):
        root = ET.parse(ROOT / '1080i/Custom_1193_StremioConnect.xml').getroot()
        self.assertIn('onboarding.py', root.find('onload').text)
        self.assertEqual(root.find(".//control[@id='101']/enable").text,
                         '!String.IsEmpty(Window(Home).Property(StremioOnboardingReady))')
        self.assertIn('StremioOnboardingCancel', root.find('onunload').text)

    def test_qr_origin_is_restricted(self):
        for qr, expected in [('https://link.stremio.com/qr?data=test', True),
                             ('https://untrusted.example/qr', False)]:
            with patch('account.request', return_value={'result': {
                    'code': 'test', 'link': 'https://link.stremio.com/test', 'qrcode': qr}}):
                self.assertEqual(bool(create_link_details()[2]), expected)
