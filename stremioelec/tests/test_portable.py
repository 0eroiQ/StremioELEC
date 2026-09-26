import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).parents[1]
ROOT = HERE.parent


class PortableKodiTests(unittest.TestCase):
    def test_portable_core_manifest_is_full_kodi_extension(self):
        node = ET.parse(HERE / 'portable/plugin.video.stremioelec/addon.xml').getroot()
        self.assertEqual(node.get('id'), 'plugin.video.stremioelec')
        points = {ext.get('point') for ext in node.findall('extension')}
        self.assertIn('xbmc.python.pluginsource', points)
        self.assertIn('xbmc.subtitle.module', points)

    def test_portable_service_depends_on_skin_and_core(self):
        node = ET.parse(HERE / 'portable/service.stremioelec.portable/addon.xml').getroot()
        deps = {item.get('addon') for item in node.findall('requires/import')}
        self.assertIn('skin.stremioelec', deps)
        self.assertIn('plugin.video.stremioelec', deps)
        points = {ext.get('point') for ext in node.findall('extension')}
        self.assertIn('xbmc.service', points)
        self.assertIn('xbmc.python.script', points)

    def test_portable_mode_is_manual_and_reversible(self):
        source = (HERE / 'portable/service.stremioelec.portable/portable_mode.py').read_text()
        self.assertIn("NEW_SKIN = 'skin.stremioelec'", source)
        self.assertIn("LEGACY_SKIN = 'skin.stremio'", source)
        self.assertIn('previous_skin', source)
        self.assertIn("def begin_onboarding():", source)
        self.assertIn("active == LEGACY_SKIN", source)
        self.assertIn("def enable():", source)
        self.assertIn("def restore():", source)
        self.assertIn("skin.estuary", source)
        self.assertIn("lookandfeel.skin", source)
        self.assertNotIn("AlarmClock(StremioWelcome", source)

    def test_portable_repository_is_self_contained(self):
        spec = importlib.util.spec_from_file_location('portable_builder', HERE / 'build_portable.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.PORTABLE_THIRD_PARTY, ())
        self.assertEqual(module.OWN,
                         ('plugin.video.stremioelec', 'skin.stremioelec',
                          'service.stremioelec.portable'))
        self.assertIn('portable-repository-test', module.TEST_BASE)

    def test_skin_runtime_depends_only_on_our_core(self):
        node = ET.parse(ROOT / 'skin.stremioelec/addon.xml').getroot()
        deps = [item.get('addon') for item in node.findall('requires/import')
                if not item.get('addon', '').startswith('xbmc.')]
        self.assertEqual(deps, ['plugin.video.stremioelec'])
        self.assertEqual(node.get('version'), '3.2.0')

    def test_skin_xml_declaration_is_standard(self):
        first = (ROOT / 'skin.stremioelec/addon.xml').read_text().splitlines()[0]
        self.assertEqual(first, '<?xml version="1.0" encoding="utf-8"?>')
        ET.parse(ROOT / 'skin.stremioelec/addon.xml')

    def test_maintenance_has_restore_entry_only_for_portable(self):
        source = (ROOT / 'skin.stremioelec/integration/plugin.video.stremioelec/settings_ui.py').read_text()
        self.assertIn('System.HasAddon(service.stremioelec.portable)', source)
        self.assertIn('Restore previous interface', source)
        self.assertIn('service.stremioelec.portable/control.py', source)

    def test_portable_service_initializes_without_forcing_skin(self):
        source = (HERE / 'portable/service.stremioelec.portable/service.py').read_text()
        self.assertIn('begin_onboarding()', source)
        self.assertNotIn('enable()', source)
        self.assertNotIn('ReloadSkin()', source)

    def test_portable_service_versions_match_optional_skin_bundle(self):
        node = ET.parse(HERE / 'portable/service.stremioelec.portable/addon.xml').getroot()
        deps = {item.get('addon'): item.get('version') for item in node.findall('requires/import')}
        self.assertEqual(deps['skin.stremioelec'], '3.2.0')
        self.assertEqual(deps['plugin.video.stremioelec'], '0.9.5')


if __name__ == '__main__':
    unittest.main()
