import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / 'publish_prerelease.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.lock = dict(version='0.1.0-test.2', target='Generic.x86_64')
        self.prefix = 'StremioELEC-Generic.x86_64-' + self.lock['version']
        for name in ('README.md', 'addon-repository.zip', self.prefix + '.img.gz', self.prefix + '.tar', self.prefix + '-addons.zip'):
            (self.folder / name).write_bytes(b'synthetic test data')
        (self.folder / 'provenance.json').write_text(json.dumps(dict(self.lock, build_commit='a' * 40)))
        candidate = dict(expires=0, target=self.lock['target'])
        for kind, suffix in [('os', '.tar'), ('addons', '-addons.zip')]:
            name = self.prefix + suffix
            data = (self.folder / name).read_bytes()
            candidate[kind] = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                url='https://github.com/0eroiQ/StremioELEC/releases/download/v0.1.0-test.2/' + name)
        (self.folder / 'update-candidate.json').write_text(json.dumps(candidate))
        self.rehash()

    def tearDown(self):
        self.temp.cleanup()

    def rehash(self):
        (self.folder / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
            for p in sorted(self.folder.iterdir()) if p.name != 'SHA256SUMS'))

    def test_valid_same_revision(self):
        self.assertEqual(publisher.check_assets(self.folder, self.lock, 'a' * 40), 'v0.1.0-test.2')

    def test_wrong_revision(self):
        with self.assertRaises(ValueError):
            publisher.check_assets(self.folder, self.lock, 'b' * 40)

    def test_changed_asset(self):
        (self.folder / 'README.md').write_text('tampered')
        with self.assertRaises(ValueError):
            publisher.check_assets(self.folder, self.lock, 'a' * 40)

    def test_unexpected_asset(self):
        (self.folder / 'account.json').write_text('synthetic, never published')
        with self.assertRaises(ValueError):
            publisher.check_assets(self.folder, self.lock, 'a' * 40)

    def test_stable_version_rejected(self):
        with self.assertRaises(ValueError):
            publisher.check_assets(self.folder, dict(self.lock, version='1.0.0'), 'a' * 40)

    def test_active_manifest_rejected(self):
        path = self.folder / 'update-candidate.json'
        candidate = json.loads(path.read_text())
        candidate['expires'] = 9999999999
        path.write_text(json.dumps(candidate))
        self.rehash()
        with self.assertRaises(ValueError):
            publisher.check_assets(self.folder, self.lock, 'a' * 40)
