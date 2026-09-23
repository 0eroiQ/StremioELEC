"""GPL-2.0-or-later. Fixed-origin, bounded StremioELEC update transport.

Trust anchor: HTTPS and write access to the project GitHub account. SHA256 is
integrity, not a signature. No arbitrary URL entry and no addon_data extraction.
The updater itself and dependency changes travel in the OS channel.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

FEED = 'https://raw.githubusercontent.com/0eroiQ/StremioELEC/update-channel/stable.json'
ASSET = r'https://github\.com/0eroiQ/StremioELEC/releases/download/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+'
IDS = ('skin.stremio', 'plugin.video.stremioelec')
MAX_SIZE = {'os': 1536 * 1024 * 1024, 'addons': 128 * 1024 * 1024}
DEFAULTS = {'auto_os': False, 'auto_addons': False, 'installed_addons': 0}


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.update-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read(path, default=None):
    if not path.exists():
        return {} if default is None else default
    if path.is_symlink() or path.stat().st_size > 256 * 1024:
        raise ValueError('Unsafe update state')
    return json.loads(path.read_text())


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(data)
    return result.hexdigest()


def network(url):
    response = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'StremioELEC-updater/1'}), timeout=20)
    if not response.url.startswith('https://'):
        response.close()
        raise ValueError('Insecure update redirect')
    return response


def version(value):
    if not re.fullmatch(r'\d+(?:\.\d+)*(?:[+~-][A-Za-z0-9.]+)?', value):
        raise ValueError('Unsupported addon version')
    return tuple(int(x) for x in re.findall(r'\d+', value))


class Updater:
    def __init__(self, storage, release, system_addons):
        self.storage = Path(storage)
        self.root = self.storage / '.config/stremioelec/updates'
        self.root.mkdir(parents=True, exist_ok=True)
        self.release = release
        self.system_addons = Path(system_addons)
        self.addons = self.storage / '.kodi/addons'

    @contextlib.contextmanager
    def locked(self):
        with (self.root / 'lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('An update operation is already running') from None
            yield

    def state(self):
        return dict(DEFAULTS, **read(self.root / 'state.json'))

    def save(self, **values):
        atomic(self.root / 'state.json', dict(self.state(), **values))

    def toggle(self, key):
        if key not in ('auto_os', 'auto_addons'):
            raise ValueError('Unknown update preference')
        self.save(**{key: not self.state()[key]})

    def installed(self, kind):
        if kind == 'os':
            return self.release['sequence']
        return max(self.release['addons_sequence'], self.state()['installed_addons'])

    def record(self, value, kind):
        if not isinstance(value, dict):
            raise ValueError('Invalid release record')
        if value.get('kind') != kind or value.get('target') != self.release['target']:
            raise ValueError('Update is for a different device target')
        if (value.get('kodi_major') != self.release['kodi_major'] or
                value.get('libreelec_major') != self.release['libreelec_major']):
            raise ValueError('Major system changes require a reviewed migration')
        for key in ('sequence', 'size', 'minimum_sequence'):
            if type(value.get(key)) is not int or value[key] < 0:
                raise ValueError('Invalid numeric release field')
        if not 0 < value['size'] <= MAX_SIZE[kind]:
            raise ValueError('Update size is outside allowed bounds')
        if value['minimum_sequence'] > self.installed(kind):
            raise ValueError('An intermediate update is required')
        if not re.fullmatch(r'[a-f0-9]{64}', value.get('sha256', '')):
            raise ValueError('Missing update checksum')
        if not re.fullmatch(ASSET, value.get('url', '')):
            raise ValueError('Update must come from our GitHub release assets')
        suffix = '.tar' if kind == 'os' else '.zip'
        if not value['url'].endswith(suffix):
            raise ValueError('Wrong update package format')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', value.get('version', '')):
            raise ValueError('Invalid release version')
        return value

    def check(self, opener=network, now=None):
        with opener(FEED) as stream:
            raw = stream.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError('Oversized update feed')
        feed = json.loads(raw)
        now = int(time.time() if now is None else now)
        if feed.get('schema') != 1 or feed.get('target') != self.release['target']:
            raise ValueError('Unknown update feed')
        if type(feed.get('expires')) is not int or feed['expires'] < now:
            raise ValueError('Update feed expired; installed system remains unchanged')
        result = {}
        for kind in ('os', 'addons'):
            if feed.get(kind) is not None:
                candidate = self.record(feed[kind], kind)
                if candidate['sequence'] > self.installed(kind):
                    result[kind] = candidate
        self.save(last_check=now, last_error='')
        return result

    def package(self, kind):
        return self.root / ('download-' + kind + ('.tar' if kind == 'os' else '.zip'))

    def fetch(self, entry, opener=network, cancelled=lambda: False):
        kind = entry['kind']
        self.record(entry, kind)
        if entry['sequence'] <= self.installed(kind):
            raise ValueError('Refusing an old update')
        if shutil.disk_usage(self.root).free < entry['size'] * 2 + 128 * 1024 * 1024:
            raise ValueError('Not enough free storage for a safe update')
        path = self.package(kind)
        temporary = path.with_suffix('.part')
        count, checksum = 0, hashlib.sha256()
        try:
            with opener(entry['url']) as source, temporary.open('wb') as dest:
                temporary.chmod(0o600)
                while True:
                    if cancelled():
                        raise RuntimeError('Update download cancelled')
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > entry['size']:
                        raise ValueError('Update exceeds declared size')
                    checksum.update(chunk)
                    dest.write(chunk)
                dest.flush()
                os.fsync(dest.fileno())
            if count != entry['size'] or checksum.hexdigest() != entry['sha256']:
                raise ValueError('Update integrity check failed')
            self.validate_package(temporary, entry)
            temporary.replace(path)
            atomic(self.root / (kind + '.json'), entry)
        finally:
            temporary.unlink(missing_ok=True)

    def validate_package(self, path, entry):
        kind = entry['kind']
        if kind == 'os':
            with tarfile.open(path, 'r:') as archive:
                members = archive.getmembers()
                names = [m.name for m in members]
                if len(members) > 10000 or len(names) != len(set(names)) or sum(m.size for m in members) > MAX_SIZE['os']:
                    raise ValueError('System archive exceeds limits or has duplicate paths')
                for item in members:
                    p = PurePosixPath(item.name)
                    if p.is_absolute() or '..' in p.parts or not (item.isfile() or item.isdir()):
                        raise ValueError('Unsafe system update archive')
                metadata = [m for m in members if m.name.endswith('/update.json')]
                systems = [m for m in members if m.name.endswith('/target/SYSTEM')]
                kernels = [m for m in members if m.name.endswith('/target/KERNEL')]
                if len(metadata) != 1 or len(systems) != 1 or len(kernels) != 1 or metadata[0].size > 16384:
                    raise ValueError('System update payload is incomplete')
                prefix = metadata[0].name.removesuffix('/update.json')
                if '/' in prefix or any(PurePosixPath(m.name).parts[0] != prefix for m in members):
                    raise ValueError('System update must have one top-level directory')
                if systems[0].name != prefix + '/target/SYSTEM' or kernels[0].name != prefix + '/target/KERNEL':
                    raise ValueError('Ambiguous system update archive')
                with archive.extractfile(metadata[0]) as stream:
                    info = json.load(stream)
                with archive.extractfile(systems[0]) as stream:
                    if stream.read(4) != b'hsqs':
                        raise ValueError('Not a SquashFS system image')
        else:
            with zipfile.ZipFile(path) as archive:
                items = archive.infolist()
                if sum(i.file_size for i in items) > 256 * 1024 * 1024 or len(items) > 10000:
                    raise ValueError('Addon update expansion exceeds limits')
                names = [i.filename for i in items]
                if len(names) != len(set(names)):
                    raise ValueError('Duplicate update archive paths')
                for item in items:
                    p = PurePosixPath(item.filename)
                    if (p.is_absolute() or '..' in p.parts or '\\' in item.filename or not p.parts
                            or stat.S_ISLNK(item.external_attr >> 16)
                            or (p.parts[0] not in IDS and item.filename != 'update.json')):
                        raise ValueError('Unsafe addon update archive')
                if archive.getinfo('update.json').file_size > 16384:
                    raise ValueError('Oversized package metadata')
                info = json.loads(archive.read('update.json'))
                if set(info.get('addons', {})) != set(IDS):
                    raise ValueError('Addon bundle must contain our skin and bridge only')
                manifests = {identity: ET.fromstring(archive.read(identity + '/addon.xml')) for identity in IDS}
                for identity, node in manifests.items():
                    if node.get('id') != identity or node.get('version') != info['addons'][identity]:
                        raise ValueError('Addon identity/version mismatch')
                    current = self.addons / identity / 'addon.xml'
                    if not current.exists():
                        current = self.system_addons / identity / 'addon.xml'
                    if version(node.get('version')) < version(ET.parse(current).getroot().get('version')):
                        raise ValueError('Addon downgrade rejected')
                    for dep in node.findall('requires/import'):
                        if dep.get('optional', 'false') == 'true':
                            continue
                        name = dep.get('addon', '')
                        if not re.fullmatch(r'[a-z0-9_.-]+', name):
                            raise ValueError('Invalid dependency identity')
                        if name in manifests:
                            available = manifests[name]
                        else:
                            file = self.addons / name / 'addon.xml'
                            if not file.exists():
                                file = self.system_addons / name / 'addon.xml'
                            available = ET.parse(file).getroot()
                        if version(available.get('version')) < version(dep.get('version', '0')):
                            raise ValueError('Addon update needs a system/dependency update first')
        for key in ('kind', 'target', 'sequence', 'version', 'kodi_major', 'libreelec_major'):
            if info.get(key) != entry.get(key):
                raise ValueError('Package does not match its release manifest')

    def ready(self):
        result = {}
        for kind in ('os', 'addons'):
            entry = read(self.root / (kind + '.json'))
            if entry and entry['sequence'] > self.installed(kind):
                result[kind] = self.record(entry, kind)
        return result

    def stage(self, entry):
        kind = entry['kind']
        self.record(entry, kind)
        if entry['sequence'] <= self.installed(kind):
            raise ValueError('Update is already installed')
        path = self.package(kind)
        if path.stat().st_size != entry['size'] or sha(path) != entry['sha256']:
            raise ValueError('Downloaded update changed; download it again')
        self.validate_package(path, entry)
        if kind == 'addons':
            system_stage = self.storage / '.update'
            if system_stage.exists() and any(system_stage.iterdir()):
                raise ValueError('Restart to finish the staged system update first')
            atomic(self.root / 'pending-addons.json', entry)
        else:
            if read(self.root / 'pending-addons.json'):
                raise ValueError('Restart to finish the staged addon update first')
            target = self.storage / '.update'
            target.mkdir(exist_ok=True)
            if any(target.iterdir()):
                raise ValueError('Another system update is already staged')
            # Only put a complete, verified tar in LibreELEC's watched directory.
            # Hardlink is atomic and avoids a second 400+ MB copy on /storage.
            os.link(path, target / ('StremioELEC-' + entry['version'] + '.tar'))
            directory = os.open(target, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def recover(self):
        journal = read(self.root / 'transaction.json')
        if not journal or journal.get('phase') != 'applying':
            return
        if self.state()['installed_addons'] >= journal['sequence']:
            atomic(self.root / 'transaction.json', dict(journal, phase='committed'))
            return
        backup = self.root / 'rollback'
        for identity in IDS:
            target, old = self.addons / identity, backup / identity
            if old.exists():
                if target.exists():
                    target.rename(backup / ('failed-' + identity))
                old.rename(target)
            elif not journal['old'][identity] and target.exists():
                target.rename(backup / ('failed-' + identity))
        atomic(self.root / 'transaction.json', dict(journal, phase='rolled-back'))
        (self.root / 'pending-addons.json').unlink(missing_ok=True)
        self.save(last_error='Interrupted addon update was rolled back; download and confirm again.')

    def apply_pending(self):
        """Called before Kodi starts, never against live imported Python modules."""
        self.recover()
        entry = read(self.root / 'pending-addons.json')
        if not entry or entry['sequence'] <= self.installed('addons'):
            return
        self.record(entry, 'addons')
        path = self.package('addons')
        if sha(path) != entry['sha256'] or path.stat().st_size != entry['size']:
            raise ValueError('Pending addon bundle changed')
        self.validate_package(path, entry)
        if shutil.disk_usage(self.root).free < 384 * 1024 * 1024:
            raise ValueError('Not enough space for addon rollback')
        backup = self.root / 'rollback'
        if backup.exists():
            backup.rename(self.root / ('rollback-' + str(time.time_ns())))
        backup.mkdir()
        self.addons.mkdir(parents=True, exist_ok=True)
        old = {i: (self.addons / i).exists() for i in IDS}
        if any((self.addons / i).is_symlink() for i in IDS):
            raise ValueError('Refusing a symlinked addon installation')
        with tempfile.TemporaryDirectory(prefix='prepared-', dir=self.root) as tmp:
            with zipfile.ZipFile(path) as archive:
                archive.extractall(tmp)
            atomic(self.root / 'transaction.json', {'phase': 'applying', 'sequence': entry['sequence'], 'old': old})
            try:
                for identity in IDS:
                    target = self.addons / identity
                    if old[identity]:
                        target.rename(backup / identity)
                    (Path(tmp) / identity).rename(target)
                self.save(installed_addons=entry['sequence'], last_error='')
                atomic(self.root / 'transaction.json', {'phase': 'committed', 'sequence': entry['sequence'], 'old': old})
                (self.root / 'pending-addons.json').unlink(missing_ok=True)
            except Exception:
                self.recover()
                raise


def device():
    path = Path('/etc/stremioelec-release.json')
    if not path.is_file():
        raise RuntimeError('Updates are available on the StremioELEC OS image only')
    release = read(path)
    if release.get('update_schema') != 1:
        raise RuntimeError('This image does not support this updater')
    return Updater('/storage', release, '/usr/share/kodi/addons')


if __name__ == '__main__':
    updater = device()
    with updater.locked():
        try:
            updater.apply_pending()
        except Exception:
            updater.save(last_error='Addon update failed. Existing profile was not changed; recovery may be required.')
            raise
