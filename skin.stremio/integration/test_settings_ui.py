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

    def test_cec_does_not_open_native_backend_without_developer_mode(self):
        self.xbmc.getCondVisibility.return_value = False
        with patch.object(self.module, 'choose', side_effect=[2, -1]):
            self.module.remote_tv_menu()
        self.assertNotIn('ActivateWindow(peripherals)',
                         [call.args[0] for call in self.xbmc.executebuiltin.call_args_list])

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
        def visibility(expr):
            return expr == 'System.HasAddon(service.stremioelec.updates)'
        self.xbmc.getCondVisibility.side_effect = visibility
        with patch.object(self.module, 'choose', return_value=1):
            self.module.run('system')
        self.xbmc.executebuiltin.assert_called_once_with('RunScript(special://xbmc/addons/service.stremioelec.updates/ui.py)')

    def test_portable_component_update_uses_hidden_engine_builtins(self):
        self.xbmc.getCondVisibility.return_value = False
        with patch.object(self.module, 'choose', return_value=1):
            self.module.run('system')
        calls = [call.args[0] for call in self.xbmc.executebuiltin.call_args_list]
        self.assertEqual(calls, ['UpdateAddonRepos', 'UpdateLocalAddons'])

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
            self.xbmc.executebuiltin.assert_called_with('ReplaceWindow(1101)')

    def test_stremio_first_settings_architecture(self):
        skin = ADDON.parent.parent / '1080i'
        top = (skin / 'Settings.xml').read_text()
        self.assertIn('ReplaceWindow(1198)', top)
        self.assertNotIn('service.libreelec.settings', top)
        self.assertNotIn('ActivateWindow(1199)', top)

        stremio = (skin / 'Custom_1198_StremioSettings.xml').read_text()
        for label in ('Account', 'Region &amp; Language', 'Stremio Addons', 'Playback',
                      'Audio', 'Subtitles', 'Display &amp; TV', 'Remote &amp; TV',
                      'Home &amp; Interface', 'Catalogs &amp; Artwork',
                      'Weather location', 'System &amp; Updates', 'Advanced',
                      'About StremioELEC'):
            self.assertIn(label, stremio)
        for section in ('account', 'playback', 'audio', 'subtitles',
                        'remote', 'home_rows', 'card_layout', 'appearance',
                        'catalogs', 'weather', 'diagnostics', 'power', 'system',
                        'advanced', 'about'):
            self.assertIn('settings_ui.py,' + section, stremio)
        for category in ('account', 'region', 'playback', 'audio', 'subtitles',
                         'display', 'home', 'addons', 'system'):
            self.assertIn('SetProperty(SettingsSection,' + category + ')', stremio)
        self.assertIn('ActivateWindow(1196)', stremio)
        self.assertNotIn('Kodi Settings', stremio)
        self.assertNotIn('<label>Close</label>', stremio)
        self.assertIn('<left>0</left><top>0</top><width>1920</width><height>1080</height>', stremio)

        backend = (skin / 'Custom_1199_KodiSettings.xml').read_text()
        self.assertIn('!Skin.HasSetting(StremioDeveloperMode)', backend)
        self.assertIn('ReplaceWindow(1198)', backend)
        self.assertIn('Playback Engine Backend', backend)

        setup = (skin / 'Custom_1102_StartUp2.xml').read_text()
        self.assertIn('Clean StremioELEC Setup', setup)
        self.assertIn('Keep Existing Setup', setup)
        self.assertIn('Advanced Setup', setup)
        advanced = (skin / 'Custom_1192_StremioAdvancedSetup.xml').read_text()
        for label in ('Standard StremioELEC', 'Advanced Playback', 'Developer Mode'):
            self.assertIn(label, advanced)
        connect = (skin / 'Custom_1193_StremioConnect.xml').read_text()
        self.assertIn('onboarding.py', connect)
        self.assertIn('StremioOnboardingQR', connect)


    def test_appliance_navigation_blocks_kodi_management_routes(self):
        skin_root = ADDON.parent.parent
        skin = skin_root / '1080i'
        for name in ('AddonBrowser.xml', 'FileManager.xml', 'SettingsProfile.xml'):
            self.assertIn('ReplaceWindow(Settings)', (skin / name).read_text())
        for name in ('SkinSettings.xml', 'Custom_1105_SkinSettings.xml',
                     'Custom_1106_SkinShortcut.xml'):
            self.assertIn('ReplaceWindow(1198)', (skin / name).read_text())
        for name in ('MyPrograms.xml', 'MyGames.xml'):
            self.assertIn('ReplaceWindow(Home)', (skin / name).read_text())

        overrides = (skin_root / 'shortcuts/overrides.xml').read_text().lower()
        for blocked in ('activatewindow(videos,addons', 'activatewindow(musiclibrary,addons',
                        'activatewindow(pictures,addons', 'activatewindow(games',
                        'activatewindow(programs', 'favouritesbrowser',
                        'activatewindow(skinsettings)', 'addons://sources/executable'):
            self.assertNotIn(blocked, overrides)

        addon_info = (skin / 'DialogAddonInfo.xml').read_text()
        for identity in ('12', '9', '10', '14', '8', '13', '7', '6'):
            self.assertNotIn('Control.IsEnabled(' + identity + ')', addon_info)


    def test_visual_community_cache_keeps_full_catalog(self):
        default_py = (ADDON / 'default.py').read_text()
        self.assertIn("'catalog': catalog_rows, 'visible': rows", default_py)
        self.assertIn("saved.get('catalog')", default_py)
        self.assertIn("saved.get('visible', [])", default_py)
        self.assertNotIn("cache.save({'created': time.time(), 'rows': rows})", default_py)

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

    def test_home_card_layout_cancel_does_not_change_skin(self):
        self.xbmc.getInfoLabel.return_value = 'poster'
        self.dialog.select.return_value = -1
        self.module.card_layout_menu()
        calls = [call.args[0] for call in self.xbmc.executebuiltin.call_args_list]
        self.assertFalse(any(call.startswith('Skin.SetString(widgetstyle,') for call in calls))
        self.assertNotIn('ReloadSkin()', calls)

    def test_original_categories_redirect_to_our_settings(self):
        tree = ET.parse(ADDON.parent.parent / '1080i/SettingsCategory.xml')
        self.assertIn('ReplaceWindow(1198)', [n.text for n in tree.findall('onload')])

    def test_settings_properties_use_kodi_runtime_custom_window_id(self):
        self.assertEqual(self.module.SETTINGS_COMMAND_WINDOW_ID, 1198)
        self.assertEqual(self.module.SETTINGS_RUNTIME_WINDOW_ID, 11198)
        with patch.object(self.module, 'rpc', return_value={'settings': []}),              patch.object(self.module, 'Store') as store:
            store.return_value.load.return_value = {}
            self.module.sync_window()
        self.gui.Window.assert_called_with(11198)


if __name__ == '__main__':
    unittest.main()
