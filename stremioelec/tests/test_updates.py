"""Synthetic upgrade/recovery tests; never touch real storage or accounts."""
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('updates', HERE / 'service.stremioelec.updates/engine.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.release = dict(target='Generic.x86_64', sequence=1, addons_sequence=1, kodi_major=21, libreelec_major=12)
        self.updater = engine.Updater(self.base / 'storage', self.release, self.base / 'system')
        for identity in engine.IDS:
            folder = self.updater.system_addons / identity
            folder.mkdir(parents=True)
            (folder / 'addon.xml').write_text('<addon id="' + identity + '" version="1.0.0"/>')
        self.profile = self.updater.storage / '.kodi/userdata/addon_data/plugin.video.stremioelec/account.json'
        self.profile.parent.mkdir(parents=True)
        self.profile.write_text('synthetic-account-sentinel')
        self.settings = self.updater.storage / '.kodi/userdata/guisettings.xml'
        self.settings.write_text('synthetic-settings-sentinel')

    def tearDown(self):
        self.temp.cleanup()

    def bundle(self, kind='addons', extra=None):
        meta = dict(kind=kind, target='Generic.x86_64', sequence=2, version='0.2.0', kodi_major=21, libreelec_major=12)
        data = io.BytesIO()
        if kind == 'addons':
            meta['addons'] = {i: '1.1.0' for i in engine.IDS}
            with zipfile.ZipFile(data, 'w') as archive:
                archive.writestr('update.json', json.dumps(meta))
                for identity in engine.IDS:
                    archive.writestr(identity + '/addon.xml', '<addon id="' + identity + '" version="1.1.0"/>')
                    archive.writestr(identity + '/code.py', 'new code')
                if extra:
                    archive.writestr(*extra)
        else:
            with tarfile.open(fileobj=data, mode='w') as archive:
                for name, value in [('update.json', json.dumps(meta).encode()), ('target/SYSTEM', b'hsqs-test'), ('target/KERNEL', b'kernel')]:
                    header = tarfile.TarInfo('release/' + name)
                    header.size = len(value)
                    archive.addfile(header, io.BytesIO(value))
        payload = data.getvalue()
        entry = dict(meta, minimum_sequence=1, size=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                     url='https://github.com/0eroiQ/StremioELEC/releases/download/v0.2.0/test.' + ('tar' if kind == 'os' else 'zip'))
        return entry, payload

    def fetch(self, kind='addons', extra=None):
        entry, payload = self.bundle(kind, extra)
        self.updater.fetch(entry, opener=lambda _: io.BytesIO(payload))
        return entry

    def test_independent_preferences_persist(self):
        self.updater.toggle('auto_os')
        self.assertTrue(self.updater.state()['auto_os'])
        self.assertFalse(self.updater.state()['auto_addons'])
        other = engine.Updater(self.updater.storage, self.release, self.updater.system_addons)
        self.assertTrue(other.state()['auto_os'])

    def test_wrong_origin_target_major_size_rejected(self):
        entry, _ = self.bundle()
        for key, value in [('url', 'https://evil.invalid/a.zip'), ('target', 'ARM'), ('kodi_major', 22),
                           ('libreelec_major', 13), ('size', 2**40), ('minimum_sequence', 100), ('sha256', 'bad')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.updater.record(dict(entry, **{key: value}), 'addons')

    def test_old_sequence_rejected(self):
        entry, _ = self.bundle()
        with self.assertRaises(ValueError):
            self.updater.fetch(dict(entry, sequence=1))

    def test_expired_feed_rejected(self):
        feed = dict(schema=1, target='Generic.x86_64', expires=1, os=None, addons=None)
        with self.assertRaises(ValueError):
            self.updater.check(opener=lambda _: io.BytesIO(json.dumps(feed).encode()), now=2)

    def test_empty_feed_and_fixed_endpoint(self):
        feed = dict(schema=1, target='Generic.x86_64', expires=100, os=None, addons=None)
        def opener(url):
            self.assertEqual(url, engine.FEED)
            return io.BytesIO(json.dumps(feed).encode())
        self.assertEqual(self.updater.check(opener=opener, now=2), {})

    def test_partial_or_bad_hash_never_ready(self):
        entry, payload = self.bundle()
        for damaged in (payload[:-1], b'X' + payload[1:], payload + b'extra'):
            with self.assertRaises(ValueError):
                self.updater.fetch(entry, opener=lambda _: io.BytesIO(damaged))
            self.assertFalse(self.updater.package('addons').exists())
            self.assertEqual(self.updater.ready(), {})
            self.assertFalse(list(self.updater.root.glob('*.part')))

    def test_cancelled_download_removed(self):
        entry, payload = self.bundle()
        with self.assertRaises(RuntimeError):
            self.updater.fetch(entry, opener=lambda _: io.BytesIO(payload), cancelled=lambda: True)
        self.assertFalse(list(self.updater.root.glob('*.part')))

    def test_traversal_and_profile_paths_rejected(self):
        for path in ('../account.json', 'skin.stremio/../../account.json', 'userdata/account.json', '/root/file'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.fetch(extra=(path, 'bad'))

    def test_symlink_zip_rejected(self):
        item = zipfile.ZipInfo('skin.stremio/link')
        item.create_system = 3
        item.external_attr = 0o120777 << 16
        with self.assertRaises(ValueError):
            self.fetch(extra=(item, '/storage/.kodi/userdata'))

    def test_os_staging_only_after_validation(self):
        entry = self.fetch('os')
        self.assertFalse((self.updater.storage / '.update').exists())
        self.updater.stage(entry)
        staged = list((self.updater.storage / '.update').iterdir())
        self.assertEqual(len(staged), 1)
        self.assertEqual(engine.sha(staged[0]), entry['sha256'])
        with self.assertRaises(ValueError):
            self.updater.stage(entry)

    def test_tampered_ready_package_not_staged(self):
        entry = self.fetch('os')
        self.updater.package('os').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            self.updater.stage(entry)
        self.assertFalse((self.updater.storage / '.update').exists())

    def test_two_channels_cannot_be_staged_together(self):
        apps = self.fetch()
        system = self.fetch('os')
        self.updater.stage(apps)
        with self.assertRaises(ValueError):
            self.updater.stage(system)
        (self.updater.root / 'pending-addons.json').unlink()
        self.updater.stage(system)
        with self.assertRaises(ValueError):
            self.updater.stage(apps)

    def test_trial_addon_upgrade_retains_account_settings_and_preferences(self):
        self.updater.toggle('auto_addons')
        entry = self.fetch()
        self.updater.stage(entry)
        self.assertFalse(self.updater.addons.exists())
        self.updater.apply_pending()
        for identity in engine.IDS:
            self.assertEqual((self.updater.addons / identity / 'code.py').read_text(), 'new code')
        self.assertEqual(self.profile.read_text(), 'synthetic-account-sentinel')
        self.assertEqual(self.settings.read_text(), 'synthetic-settings-sentinel')
        self.assertTrue(self.updater.state()['auto_addons'])
        self.assertEqual(self.updater.installed('addons'), 2)
        self.updater.apply_pending()  # Subsequent boots are idempotent.
        self.assertEqual(self.updater.ready(), {})

    def test_failed_second_addon_rolls_back_first(self):
        for identity in engine.IDS:
            folder = self.updater.addons / identity
            folder.mkdir(parents=True)
            (folder / 'addon.xml').write_text('<addon id="' + identity + '" version="1.0.0"/>')
            (folder / 'code.py').write_text('old code')
        entry = self.fetch()
        self.updater.stage(entry)
        original = Path.rename
        def rename(path, target):
            if path.name == engine.IDS[1] and path.parent.name.startswith('prepared-'):
                raise OSError('simulated power/storage failure')
            return original(path, target)
        with patch.object(Path, 'rename', rename), self.assertRaises(OSError):
            self.updater.apply_pending()
        for identity in engine.IDS:
            self.assertEqual((self.updater.addons / identity / 'code.py').read_text(), 'old code')
        self.assertEqual(self.updater.installed('addons'), 1)
        self.assertEqual(self.profile.read_text(), 'synthetic-account-sentinel')
        self.updater.recover()

    def test_lock_excludes_simultaneous_operation(self):
        with self.updater.locked(), self.assertRaises(RuntimeError):
            with self.updater.locked():
                pass

    def ui(self, action, playing=False):
        kodi, gui = MagicMock(), MagicMock()
        kodi.Player.return_value.isPlaying.return_value = playing
        dialog = gui.Dialog.return_value
        dialog.yesno.return_value = False
        module_spec = importlib.util.spec_from_file_location('update_ui', HERE / 'service.stremioelec.updates/ui.py')
        module = importlib.util.module_from_spec(module_spec)
        with patch.dict(sys.modules, {'xbmc': kodi, 'xbmcgui': gui, 'engine': engine}):
            module_spec.loader.exec_module(module)
        with patch.object(module, 'device', return_value=self.updater):
            module.main(action)
        return kodi

    def test_ui_switch_does_not_install_or_restart(self):
        kodi = self.ui('toggle_os')
        self.assertTrue(self.updater.state()['auto_os'])
        kodi.executebuiltin.assert_not_called()

    def test_ui_install_blocked_during_playback(self):
        kodi = self.ui('install', playing=True)
        kodi.executebuiltin.assert_not_called()

    def test_ui_cancel_install_does_not_stage(self):
        self.fetch()
        kodi = self.ui('install')
        kodi.executebuiltin.assert_not_called()
        self.assertFalse((self.updater.root / 'pending-addons.json').exists())


if __name__ == '__main__':
    unittest.main()
