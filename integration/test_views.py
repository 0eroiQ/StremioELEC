"""Guard the reversible Home-view split without requiring Kodi."""
import pathlib
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]


class HomeViewsTest(unittest.TestCase):
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
        self.assertEqual(root.find("include[@name='StremioHomeRowPosition']/top").text, '649')
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
