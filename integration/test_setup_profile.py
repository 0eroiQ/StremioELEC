import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from setup_profile import home_xml, replace_backed_up, prepare
from account import Store


class SetupTest(unittest.TestCase):
    def test_completed_setup_never_overwrites_on_reconnect(self):
        with tempfile.TemporaryDirectory() as folder:
            Store(pathlib.Path(folder) / 'setup').save({'completed': True})
            with patch.dict(sys.modules, {'xbmc': Mock(), 'xbmcaddon': Mock(), 'xbmcvfs': Mock()}), \
                 patch('setup_profile.replace_backed_up') as replace:
                self.assertTrue(prepare(folder, '/unused')['completed'])
                replace.assert_not_called()

    def test_ten_distinct_rows_with_limits(self):
        rows = ET.fromstring(home_xml()).findall('shortcut')
        self.assertEqual(len(rows), 10)
        urls = [row.findtext('action') for row in rows]
        self.assertEqual(len(set(urls)), 10)
        self.assertIn('action=continue', urls[0])
        self.assertTrue(all('plugin.video.tmdb.bingie.helper' in url for url in urls[1:]))
        self.assertTrue(all("'20'" in row.findtext('additional-properties') for row in rows))

    def test_original_backup_survives_reapply(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'shortcuts' / 'home.xml'
            path.parent.mkdir()
            path.write_bytes(b'original')
            backups = pathlib.Path(folder) / 'backup'
            replace_backed_up(path, b'first', backups)
            replace_backed_up(path, b'second', backups)
            self.assertEqual(path.read_bytes(), b'second')
            self.assertEqual((backups / 'shortcuts--home.xml').read_bytes(), b'original')
