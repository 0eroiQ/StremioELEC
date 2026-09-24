"""Safety and curated settings tests; no live account or Kodi changes."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'
sys.path.insert(0, str(ADDON))


class SettingsTests(unittest.TestCase):
    def test_subtitle_color_palette(self):
        for key in ('subtitles.colorpick', 'subtitles.bordercolorpick', 'subtitles.bgcolorpick', 'subtitles.shadowcolor'):
            options = self.module.setting_options({'id': key, 'value': 'FFFFFFFF'})
            self.assertEqual(len(options), 11)
            self.assertIn({'label': 'Yellow', 'value': 'FFFFFF00'}, options)
            for option in options:
                self.assertRegex(option['value'], r'^FF[0-9A-F]{6}$')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.xbmc = MagicMock()
        self.xbmc.Player.return_value.isPlaying.return_value = False
        self.gui = MagicMock()
        self.dialog = self.gui.Dialog.return_value
        addon = MagicMock()
        addon.getAddonInfo.return_value = self.temp.name
        modules = {'xbmc': self.xbmc, 'xbmcgui': self.gui,
                   'xbmcaddon': MagicMock(), 'xbmcvfs': MagicMock()}
        modules['xbmcaddon'].Addon.return_value = addon
        modules['xbmcvfs'].translatePath.side_effect = lambda p: p
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        spec = importlib.util.spec_from_file_location('settings_under_test', ADDON / 'settings_ui.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_reset_cancel_keeps_account(self):
        self.dialog.yesno.return_value = False
        with patch.object(self.module, 'prepare') as prepare, patch.object(self.module, 'Store') as store:
            self.module.reset_account()
            prepare.assert_not_called()
            store.assert_not_called()

    def test_cec_opens_device_settings_without_restarting(self):
        with patch.object(self.module, 'choose', return_value=4):
            self.module.run('system')
        self.xbmc.executebuiltin.assert_called_once_with('ActivateWindow(peripherals)')

    def test_navigation_sounds_toggle(self):
        for current, expected in ((0, 1), (1, 0), (2, 0)):
            with patch.object(self.module, 'choose', side_effect=[0, -1]), patch.object(self.module, 'get_setting', return_value=current), patch.object(self.module, 'rpc', return_value=True) as rpc:
                self.module.navigation_sounds_menu()
                rpc.assert_called_once_with('Settings.SetSettingValue', {'setting': 'audiooutput.guisoundmode', 'value': expected})

    def test_navigation_cancel_does_not_change_sound(self):
        with patch.object(self.module, 'choose', return_value=-1), patch.object(self.module, 'get_setting', return_value=1), patch.object(self.module, 'rpc') as rpc:
            self.module.navigation_sounds_menu()
            rpc.assert_not_called()

    def test_updates_open_only_our_updater(self):
        with patch.object(self.module, 'choose', return_value=1):
            self.xbmc.getCondVisibility.return_value = True
            self.module.run('system')
            self.xbmc.executebuiltin.assert_called_once_with('RunScript(special://xbmc/addons/service.stremioelec.updates/ui.py)')

    def test_missing_updater_does_not_install_or_restart(self):
        with patch.object(self.module, 'choose', return_value=1):
            self.xbmc.getCondVisibility.return_value = False
            self.module.run('system')
            self.xbmc.executebuiltin.assert_not_called()

    def test_reset_blocked_during_playback(self):
        self.xbmc.Player.return_value.isPlaying.return_value = True
        with patch.object(self.module, 'prepare') as prepare:
            self.module.reset_account()
            prepare.assert_not_called()

    def test_setup_failure_preserves_login(self):
        self.dialog.yesno.return_value = True
        with patch.object(self.module, 'prepare', side_effect=RuntimeError), patch.object(self.module, 'Store') as store:
            with self.assertRaises(RuntimeError):
                self.module.reset_account()
            store.assert_not_called()

    def test_reset_only_named_local_stores(self):
        self.dialog.yesno.return_value = True
        with patch.object(self.module, 'prepare'), patch.object(self.module, 'Store') as store:
            self.module.reset_account()
            self.assertEqual([call.args[0].relative_to(self.module.PROFILE).as_posix()
                              for call in store.call_args_list],
                             ['.', 'streams', 'playback', 'subtitle-results', 'setup'])
            self.xbmc.executebuiltin.assert_called_with('ReplaceWindow(1102)')

    def test_three_layer_settings_architecture(self):
        skin = ADDON.parent.parent / '1080i'
        top = ET.parse(skin / 'Settings.xml')
        actions = [(n.text or '') for n in top.findall('.//onclick')]
        joined = '\n'.join(actions).lower()
        self.assertIn('activatewindow(1198)', joined)
        self.assertIn('service.libreelec.settings/default.py', joined)
        self.assertIn('activatewindow(1199)', joined)
        self.assertEqual(len(top.findall('.//content/item')), 3)

        stremio = (skin / 'Custom_1198_StremioSettings.xml').read_text()
        for section in ('account', 'home', 'catalogs', 'subtitles', 'weather', 'maintenance', 'about'):
            self.assertIn('settings_ui.py,' + section, stremio)
        self.assertNotIn('settings_ui.py,system', stremio)
        self.assertNotIn('settings_ui.py,audio', stremio)
        self.assertNotIn('settings_ui.py,video', stremio)

        kodi = (skin / 'Custom_1199_KodiSettings.xml').read_text().lower()
        for window in ('playersettings', 'mediasettings', 'pvrsettings', 'servicesettings',
                       'interfacesettings', 'systemsettings', 'skinsettings',
                       'addonbrowser', 'filemanager'):
            self.assertIn(window, kodi)

        system = (skin / 'service-LibreELEC-Settings-mainWindow.xml').read_text()
        self.assertIn('StremioELEC System', system)
        self.assertIn('System Updates', system)
        self.assertIn('ActivateWindow(1197)', system)
        self.assertNotIn('openelec_logo.png', system)
        updates = (skin / 'Custom_1197_StremioUpdates.xml').read_text()
        self.assertIn('Current version', updates)
        self.assertIn('Update channel', updates)
        self.assertIn('Automatic system downloads', updates)
        self.assertIn('Install downloaded update &amp; restart', updates)
        self.assertIn('service.stremioelec.updates/ui.py,check', updates)
        self.assertIn('<label>Advanced</label>', (skin / 'Settings.xml').read_text())


    def test_rejected_setting_is_not_reported_success(self):
        with patch.object(self.module, 'rpc', side_effect=[{'settings': [
                {'id': 'subtitles.downloadfirst', 'value': False}]}, False]):
            with self.assertRaises(RuntimeError):
                self.module.edit_kodi('subtitles.downloadfirst', 'Auto subtitle')

    def test_list_options_use_kodi_element_definition(self):
        self.dialog.multiselect.return_value = [0]
        with patch.object(self.module, 'rpc', side_effect=[{'settings': [
                {'id': 'subtitles.languages', 'value': ['English'], 'definition': {
                    'options': [{'label': 'Croatian', 'value': 'Croatian'},
                                {'label': 'English', 'value': 'English'}]}}]}, True]) as rpc:
            self.module.edit_kodi('subtitles.languages', 'Languages')
            rpc.assert_called_with('Settings.SetSettingValue', {'setting': 'subtitles.languages', 'value': ['Croatian']})

    def test_numeric_range_is_bounded_and_no_scientific_labels(self):
        options = self.module.setting_options({'value': 20, 'minimum': 12, 'maximum': 74, 'step': 2})
        self.assertEqual(options[4], {'label': '20', 'value': 20})
        self.assertEqual(options[-1]['value'], 74)
        self.assertEqual(self.module.setting_options({'value': 1, 'minimum': 0, 'maximum': 10000, 'step': 1}), [])
        self.assertEqual(self.module.setting_options({'value': 1, 'minimum': 0, 'maximum': 10, 'step': 0}), [])

    def test_fractional_steps(self):
        options = self.module.setting_options({'value': 0.2, 'minimum': 0, 'maximum': 0.3, 'step': 0.1})
        self.assertEqual([o['value'] for o in options], [0.0, 0.1, 0.2, 0.3])

    def test_row_limit_preserves_other_properties(self):
        row = ET.fromstring('<shortcut><additional-properties>[("widgetlimit", "20"), ("widgetstyle", "landscape"), ("other", "x")]</additional-properties></shortcut>')
        self.module.update_row_limit(row, 30)
        import ast
        props = dict(ast.literal_eval(row.findtext('additional-properties')))
        self.assertEqual(props, {'widgetlimit': '30', 'widgetstyle': 'landscape', 'other': 'x'})

    def test_malformed_row_properties_fail_without_replacement(self):
        row = ET.fromstring('<shortcut><additional-properties>not python</additional-properties></shortcut>')
        with self.assertRaises((ValueError, SyntaxError)):
            self.module.update_row_limit(row, 10)
        self.assertEqual(row.findtext('additional-properties'), 'not python')

    def test_color_palette_not_exposed_to_other_settings(self):
        self.assertTrue(self.module.setting_options({'id': 'subtitles.colorpick', 'value': 'FFFFFFFF'}))
        self.assertFalse(self.module.setting_options({'id': 'secret', 'value': 'FFFFFFFF'}))

    def test_display_timeout_restores_previous_mode(self):
        self.dialog.select.return_value = 1
        self.dialog.yesno.return_value = False
        with patch.object(self.module, 'rpc', side_effect=[{'settings': [
                {'id': 'videoscreen.screenmode', 'value': 'old', 'options': [
                    {'label': 'Old', 'value': 'old'}, {'label': 'New', 'value': 'new'}]}]}, True, True]) as rpc:
            self.module.edit_kodi('videoscreen.screenmode', 'Mode')
            rpc.assert_called_with('Settings.SetSettingValue', {'setting': 'videoscreen.screenmode', 'value': 'old'})

    def test_disabled_setting_does_not_write(self):
        with patch.object(self.module, 'rpc', return_value={'settings': [
                {'id': 'audiooutput.passthrough', 'value': False, 'enabled': False}]}) as rpc:
            self.module.edit_kodi('audiooutput.passthrough', 'Passthrough')
            self.assertEqual(rpc.call_count, 1)

    def test_home_cancel_at_order_stage_does_not_write(self):
        target = Path(self.temp.name) / 'home.xml'
        target.write_text('<shortcuts><shortcut><label>Existing</label><action>plugin://existing</action></shortcut></shortcuts>')
        self.module.HOME = str(target)
        self.dialog.multiselect.return_value = [0]
        self.dialog.select.side_effect = [1, -1]
        with patch.object(self.module, 'replace_backed_up') as write:
            self.module.home_menu()
            write.assert_not_called()

    def test_original_categories_redirect_to_our_settings(self):
        tree = ET.parse(ADDON.parent.parent / '1080i/SettingsCategory.xml')
        self.assertIn('ReplaceWindow(Settings)', [n.text for n in tree.findall('onload')])


if __name__ == '__main__':
    unittest.main()
