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
        self.assertIn('skin.stremio', deps)
        self.assertIn('plugin.video.stremioelec', deps)
        points = {ext.get('point') for ext in node.findall('extension')}
        self.assertIn('xbmc.service', points)
        self.assertIn('xbmc.python.script', points)

    def test_portable_mode_is_reversible(self):
        source = (HERE / 'portable/service.stremioelec.portable/portable_mode.py').read_text()
        self.assertIn('previous_skin', source)
        self.assertIn("def begin_onboarding():", source)
        self.assertIn("AlarmClock(StremioWelcome,ReplaceWindow(1101)", source)
        self.assertIn("def restore():", source)
        self.assertIn("skin.estuary", source)
        self.assertIn("lookandfeel.skin", source)

    def test_builder_excludes_os_specific_packages(self):
        spec = importlib.util.spec_from_file_location('portable_builder', HERE / 'build_portable.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn('inputstream.adaptive', module.EXCLUDE)
        self.assertIn('slyguy.trailers', module.EXCLUDE)
        self.assertEqual(module.OWN,
                         ('plugin.video.stremioelec', 'skin.stremio',
                          'service.stremioelec.portable'))
        self.assertIn('portable-repository-test', module.TEST_BASE)

    def test_cosmetic_studio_pack_is_optional(self):
        node = ET.parse(ROOT / 'skin.stremio/addon.xml').getroot()
        dep = next(item for item in node.findall('requires/import')
                   if item.get('addon') == 'resource.images.studios.coloured')
        self.assertEqual(dep.get('optional'), 'true')

    def test_skin_xml_declaration_is_standard(self):
        first = (ROOT / 'skin.stremio/addon.xml').read_text().splitlines()[0]
        self.assertEqual(first, '<?xml version="1.0" encoding="utf-8"?>')
        ET.parse(ROOT / 'skin.stremio/addon.xml')

    def test_maintenance_has_restore_entry_only_for_portable(self):
        source = (ROOT / 'skin.stremio/integration/plugin.video.stremioelec/settings_ui.py').read_text()
        self.assertIn('System.HasAddon(service.stremioelec.portable)', source)
        self.assertIn('Restore previous interface', source)
        self.assertIn('service.stremioelec.portable/control.py', source)

    def test_portable_service_enters_welcome_flow_without_native_prompt(self):
        source = (HERE / 'portable/service.stremioelec.portable/service.py').read_text()
        self.assertIn('begin_onboarding()', source)
        self.assertNotIn("yesno('StremioELEC for Kodi'", source)


if __name__ == '__main__':
    unittest.main()
