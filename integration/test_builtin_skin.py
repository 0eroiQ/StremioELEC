import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from install_builtin_skin import closure


class BuiltinSkinTests(unittest.TestCase):
    def test_source_identity(self):
        root = Path(__file__).resolve().parents[1]
        addon = ET.parse(root / 'addon.xml').getroot()
        self.assertEqual(addon.get('id'), 'skin.stremio')
        self.assertEqual(addon.get('name'), 'StremioELEC')

    def test_missing_dependency_fails_before_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Missing dependency'):
                closure(Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_transitive_dependencies_and_optional_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for identity, imports in [('skin.stremio', '<import addon="script.helper"/><import addon="optional.missing" optional="true"/>'),
                                      ('plugin.video.stremioelec', ''), ('script.helper', '')]:
                folder = root / 'portable_data/addons' / identity
                folder.mkdir(parents=True)
                (folder / 'addon.xml').write_text('<addon id="' + identity + '"><requires>' + imports + '</requires></addon>')
            self.assertEqual(set(closure(root)), {'skin.stremio', 'plugin.video.stremioelec', 'script.helper'})


if __name__ == '__main__':
    unittest.main()
