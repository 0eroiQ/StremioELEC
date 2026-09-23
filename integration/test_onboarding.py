import pathlib
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from account import create_link_details

ROOT = pathlib.Path(__file__).resolve().parents[1]


class OnboardingTest(unittest.TestCase):
    def test_welcome_does_not_mutate_device_settings(self):
        root = ET.parse(ROOT / '1080i/Custom_1101_StartUp.xml').getroot()
        actions = [node.text for node in root.findall('.//onclick')]
        self.assertIn('ReplaceWindow(1102)', actions)
        self.assertFalse(any('kodisetting' in action for action in actions))
        self.assertIn('Skin.SetBool(StremioOnboardingDone)', actions)

    def test_qr_and_ready_state_are_wired(self):
        root = ET.parse(ROOT / '1080i/Custom_1102_StartUp2.xml').getroot()
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
