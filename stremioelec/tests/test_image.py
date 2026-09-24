import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load('build_image')
bootstrap = load('bootstrap')


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def addon(self, identity, version='1.0.0', requires=''):
        path = self.root / identity
        path.mkdir()
        (path / 'addon.xml').write_text('<addon id="' + identity + '" version="' + version + '"><requires>' + requires + '</requires></addon>')
        return path

    def test_dependency_closure(self):
        self.addon('skin.stremio', requires='<import addon="xbmc.gui" version="5.17.0"/>')
        self.addon('xbmc.gui', '5.17.0')
        self.assertEqual(build.validate_closure(self.root, ['skin.stremio']), {'skin.stremio': '1.0.0', 'xbmc.gui': '5.17.0'})

    def test_missing_dependency_fails(self):
        self.addon('skin.stremio', requires='<import addon="xbmc.gui" version="5.17.0"/>')
        with self.assertRaises(FileNotFoundError):
            build.validate_closure(self.root, ['skin.stremio'])

    def test_old_dependency_fails(self):
        self.addon('skin.stremio', requires='<import addon="xbmc.gui" version="5.17.0"/>')
        self.addon('xbmc.gui', '5.16.0')
        with self.assertRaises(ValueError):
            build.validate_closure(self.root, ['skin.stremio'])

    def archive(self, entries):
        path = self.root / 'addon.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
        return path

    def test_zip_traversal_rejected_before_extract(self):
        path = self.archive({'demo/addon.xml': '<addon id="demo" version="1"/>', 'demo/../../escape': 'bad'})
        with self.assertRaises(ValueError):
            build.extract_addon(path, self.root, 'demo', '1')
        self.assertFalse((self.root / 'demo').exists())

    def test_wrong_zip_version_rejected(self):
        path = self.archive({'demo/addon.xml': '<addon id="demo" version="2"/>'})
        with self.assertRaises(ValueError):
            build.extract_addon(path, self.root, 'demo', '1')

    def test_pinned_zip_extraction(self):
        path = self.archive({'demo/addon.xml': '<addon id="demo" version="1"/>'})
        build.extract_addon(path, self.root, 'demo', '1')
        self.assertTrue((self.root / 'demo/addon.xml').is_file())
        with self.assertRaises(ValueError):
            build.extract_addon(path, self.root, 'demo', '1')

    def test_source_rejects_profile(self):
        source = self.addon('demo')
        (source / 'account.json').write_text('{}')
        with self.assertRaises(ValueError):
            build.copy_source(source, self.root / 'copy')

    def test_source_excludes_vendor_and_git(self):
        source = self.addon('demo')
        for folder in ('.git', '__pycache__', 'vendor'):
            (source / folder).mkdir()
            (source / folder / 'ignored').write_text('ignored')
        build.copy_source(source, self.root / 'copy')
        self.assertEqual([p.name for p in (self.root / 'copy').iterdir()], ['addon.xml'])

    def test_no_unpinned_or_http_downloads(self):
        for url, sha in [('http://example.com/a', 'a' * 64), ('https://example.com/a', '')]:
            with self.assertRaises(ValueError):
                build.download(url, self.root / 'download', sha)

    def test_seed_manual_updates_only_once(self):
        bootstrap.seed(self.root)
        file = self.root / '.kodi/userdata/addon_data/service.libreelec.settings/oe_settings.xml'
        tree = ET.parse(file)
        self.assertEqual(tree.find('settings/updates/AutoUpdate').text, 'manual')
        self.assertEqual(tree.find('settings/updates/UpdateNotify').text, '0')
        tree.find('settings/updates/AutoUpdate').text = 'test-preserved'
        tree.write(file)
        bootstrap.seed(self.root)
        self.assertEqual(ET.parse(file).find('settings/updates/AutoUpdate').text, 'test-preserved')

    def test_bootstrap_preserves_network_settings(self):
        file = self.root / '.kodi/userdata/addon_data/service.libreelec.settings/oe_settings.xml'
        file.parent.mkdir(parents=True)
        file.write_text('<libreelec><settings><system><hostname>test-box</hostname></system></settings></libreelec>')
        bootstrap.seed(self.root)
        self.assertEqual(ET.parse(file).find('settings/system/hostname').text, 'test-box')

    def test_repository_layout(self):
        for identity in build.OWN_IDS:
            self.addon(identity)
        output = self.root / 'repository.zip'
        build.repository_zip(self.root, output)
        with zipfile.ZipFile(output) as archive:
            self.assertIn('skin.stremio/skin.stremio-1.0.0.zip', archive.namelist())
            self.assertEqual(len(ET.fromstring(archive.read('addons.xml'))), 3)
            import hashlib
            self.assertEqual(archive.read('addons.xml.md5').decode(), hashlib.md5(archive.read('addons.xml')).hexdigest())

    def test_lock_is_immutable_and_targeted(self):
        lock = json.loads((BASE / 'image.lock.json').read_text())
        self.assertEqual(lock['target'], 'Generic.x86_64')
        self.assertRegex(lock['skin']['commit'], r'^[a-f0-9]{40}$')
        self.assertRegex(lock['libreelec']['sha256'], r'^[a-f0-9]{64}$')
        ids = [a['id'] for a in lock['addons']]
        self.assertEqual(len(ids), len(set(ids)))
        for item in lock['addons']:
            self.assertRegex(item['sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(item['url'].startswith('https://'))

    def test_base_identity_uses_libreelec_os_release(self):
        (self.root / 'etc').mkdir()
        file = self.root / 'etc/os-release'
        lock = {'target': 'Generic.x86_64', 'libreelec': {'version': '12.2.1'}}
        file.write_text('ID="libreelec"\nVERSION="12.2.1"\nLIBREELEC_ARCH="Generic.x86_64"\n')
        build.validate_base(self.root, lock)
        for bad in ('RPi4.aarch64', 'Generic-legacy.x86_64'):
            file.write_text('ID="libreelec"\nVERSION="12.2.1"\nLIBREELEC_ARCH="' + bad + '"\n')
            with self.assertRaises(ValueError):
                build.validate_base(self.root, lock)

    def test_patch_root_defaults_and_closure(self):
        root = self.root / 'rootfs'
        kodi = root / 'usr/share/kodi'
        for folder in ('system/settings', 'config', 'addons/skin.estuary'):
            (kodi / folder).mkdir(parents=True, exist_ok=True)
        (root / 'etc').mkdir()
        (kodi / 'addons/skin.estuary/addon.xml').write_text('<addon id="skin.estuary" version="1"/>')
        (kodi / 'system/addon-manifest.xml').write_text('<addons><addon>skin.estuary</addon></addons>')
        (kodi / 'system/settings/settings.xml').write_text('<settings><setting id="lookandfeel.skin"><default>skin.estuary</default></setting></settings>')
        (kodi / 'config/guisettings.xml').write_text('<settings><setting id="test.preserved">yes</setting></settings>')
        source = self.root / 'source'
        bridge = source / 'integration/plugin.video.stremioelec'
        bridge.mkdir(parents=True)
        (source / 'addon.xml').write_text('<addon id="skin.stremio" version="1"/>')
        (source / 'LICENSE').write_text('test fixture')
        (bridge / 'addon.xml').write_text('<addon id="plugin.video.stremioelec" version="1"/>')
        python = kodi / 'addons/xbmc.python'
        python.mkdir()
        (python / 'addon.xml').write_text('<addon id="xbmc.python" version="3.0.0"/>')
        trailers = kodi / 'addons/slyguy.trailers'
        trailers.mkdir()
        (trailers / 'addon.xml').write_text('<addon id="slyguy.trailers" version="0.2.0"/>')
        adaptive = kodi / 'addons/inputstream.adaptive'
        adaptive.mkdir()
        (adaptive / 'addon.xml').write_text('<addon id="inputstream.adaptive" version="21.5.24.1"/>')
        result = build.patch_kodi(root, source, {'addons': []}, self.root)
        self.assertEqual(set(result['dependency_closure']), set(build.IMAGE_IDS) | {'xbmc.python'})
        self.assertFalse((kodi / 'addons/skin.estuary').exists())
        self.assertEqual(ET.parse(kodi / 'system/settings/settings.xml').find(".//default").text, 'skin.stremio')
        config = ET.parse(kodi / 'config/guisettings.xml')
        self.assertEqual(config.find("setting[@id='general.addonupdates']").text, '2')
        self.assertEqual(config.find("setting[@id='test.preserved']").text, 'yes')
        self.assertTrue((root / 'usr/lib/systemd/system/kodi.service.d/stremioelec.conf').is_file())


if __name__ == '__main__':
    unittest.main()
