"""Guard the reversible Home-view split without requiring Kodi."""
import pathlib
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HomeViewsTest(unittest.TestCase):
    def test_card_secondary_text_can_be_hidden_independently(self):
        root = ET.parse(ROOT / '1080i/IncludesHomeWidgets.xml').getroot()
        labels = [c for c in root.findall('.//control') if c.findtext('label') == '$VAR[ThumbListDetails_3]']
        self.assertEqual(len(labels), 3)
        for control in labels:
            self.assertIn('!Skin.HasSetting(StremioHideCardLabels) + !Skin.HasSetting(StremioHideCardGenres)', [v.text for v in control.findall('visible')])
        titles = [c for c in root.findall('.//control') if c.findtext('label') == '[B]$VAR[ThumbListDetails_2][/B]']
        for control in titles:
            self.assertFalse(any('StremioHideCardGenres' in (v.text or '') for v in control.findall('visible')))

    def test_continue_play_button_uses_exact_saved_route(self):
        root = ET.parse(ROOT / '1080i/IncludesDialogVideoInfo.xml').getroot()
        button = root.find("include[@name='StremioContinuePlayButton']/control")
        self.assertEqual(button.findtext('visible'), '!String.IsEmpty(ListItem.Property(StremioContinuePath))')
        actions = [node.text for node in button.findall('onclick')]
        self.assertIn('ActivateWindow(Videos,$INFO[Window(Home).Property(StremioContinueTarget)],return)', actions)
        self.assertEqual(sum(node.text == 'StremioContinuePlayButton' for node in root.findall('.//include')), 2)

    def test_more_episodes_uses_stremio_native_bingie_episode_view(self):
        info = (ROOT / '1080i/IncludesDialogVideoInfo.xml').read_text()
        self.assertIn('ListItem.Property(StremioMoreEpisodesPath)', info)
        self.assertIn('ActivateWindow(Videos,$ESCINFO[ListItem.Property(StremioMoreEpisodesPath)],return)', info)

        episodes = (ROOT / '1080i/View_525_Bingie_Episodes.xml').read_text()
        self.assertIn('plugin://plugin.video.stremioelec/?action=seasons&amp;kind=series&amp;id=', episodes)
        self.assertIn('ListItem.Property(StremioSeriesID)', episodes)

        core = (ROOT / 'integration/plugin.video.stremioelec/default.py').read_text()
        self.assertIn("BASE = 'plugin://plugin.video.stremioelec/'", core)
        self.assertIn("action in ('episodes', 'more_episodes')", core)
        self.assertIn("Container.SetViewMode(525)", core)

    def test_bingie_episode_airdate_layout_is_restored(self):
        episodes = (ROOT / '1080i/View_525_Bingie_Episodes.xml').read_text()
        self.assertIn(
            '<include condition="Skin.HasSetting(View525_EnableAirDate)">View_525_Details_Defs_2</include>',
            episodes)
        self.assertIn(
            '<include condition="Skin.HasSetting(View525_EnableAirDate)">View_525_Details_Defs_Focus_2</include>',
            episodes)
        defaults = (ROOT / '1080i/IncludesDefaultSkinSettings.xml').read_text()
        self.assertIn('Skin.SetBool(View525_EnableAirDate)', defaults)
        self.assertIn('StremioEpisodeAirDateDefault', defaults)

    def test_stremio_widget_picker_is_browsable_and_optional(self):
        root = ET.parse(ROOT / 'shortcuts/overrides.xml').getroot()
        node = root.find("widget-groupings/shortcut[@label='Stremio catalogs']")
        self.assertEqual(node.text, '||BROWSE||plugin.video.stremioelec/?action=widgets')
        self.assertEqual(node.get('condition'), 'System.HasAddon(plugin.video.stremioelec)')

    def test_stremio_forces_moving_focus_and_hides_owned_options(self):
        root = ET.parse(ROOT / '1080i/Includes.xml').getroot()
        self.assertEqual(root.find("expression[@name='UseOriginalFixedFocus']").text,
                         '!Skin.HasSetting(StremioView) + Skin.HasSetting(EnableFixedFrameWidgets)')
        settings = ET.parse(ROOT / '1080i/IncludesSkinSettings.xml').getroot()
        for identity in ('31123', '31297', '23002', '31169'):
            control = settings.find(".//control[@id='%s']" % identity)
            self.assertIn('!Skin.HasSetting(StremioView)',
                          [node.text for node in control.findall('visible')])

    def test_row_position_is_scoped_to_stremio(self):
        root = ET.parse(ROOT / '1080i/IncludesHomeBingie.xml').getroot()
        self.assertEqual(root.find("include[@name='StremioNormalHomeRowPosition']/top").text, '649')
        self.assertEqual(root.find("include[@name='StremioCompactHomeRowPosition']/top").text, '739')
        self.assertEqual(root.find("include[@name='OriginalBingieHomeRowPosition']/top").text, '564')
        rows = root.find(".//control[@id='77777']")
        includes = {node.text: node.get('condition') for node in rows.findall('include')}
        self.assertEqual(includes['StremioHomeRowPosition'], 'Skin.HasSetting(StremioView)')
        self.assertEqual(includes['OriginalBingieHomeRowPosition'], '!Skin.HasSetting(StremioView)')

    def test_selector_preserves_original_spotlight_preference(self):
        settings = ET.parse(ROOT / '1080i/IncludesSkinSettings.xml').getroot()
        selector = settings.find("include[@name='Stremio_View_Settings']")
        actions = [node.text for node in selector.findall('.//onclick')]
        self.assertIn('Skin.SetBool(StremioView)', actions)
        self.assertIn('Skin.Reset(StremioView)', actions)
        self.assertFalse(any('DisableSpotlightContent' in action for action in actions))

    def test_spotlight_is_override_not_a_saved_preference_change(self):
        root = ET.parse(ROOT / '1080i/Includes.xml').getroot()
        expression = root.find("expression[@name='StremioSpotlightEnabled']").text
        self.assertEqual(expression,
                         '!Skin.HasSetting(StremioView) + !Skin.HasSetting(DisableSpotlightContent)')

    def test_default_only_applies_to_new_profiles(self):
        root = ET.parse(ROOT / '1080i/IncludesDefaultSkinSettings.xml').getroot()
        actions = [node for node in root.findall('.//onload')
                   if node.text == 'Skin.SetBool(StremioView)']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].get('condition'), '!Skin.HasSetting(HomeMenuDefaults46)')


if __name__ == '__main__':
    unittest.main()
