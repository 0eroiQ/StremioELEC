#!/usr/bin/env python3
"""Build only a temporary regular-file image in Linux CI. No device-write API."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
OWN_IDS = ('skin.stremio', 'plugin.video.stremioelec', 'repository.stremioelec')


def digest(path, algorithm='sha256'):
    result = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def download(url, path, expected):
    if not url.startswith('https://') or not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise ValueError('Unpinned or insecure download')
    request = urllib.request.Request(url, headers={'User-Agent': 'StremioELEC-image-pilot/0.1'})
    with urllib.request.urlopen(request, timeout=120) as response, path.open('wb') as output:
        if not response.url.startswith('https://'):
            raise ValueError('Insecure redirect')
        shutil.copyfileobj(response, output)
    if digest(path) != expected:
        raise ValueError('Checksum mismatch: ' + path.name)


def extract_addon(archive_path, destination, identity, version):
    if not re.fullmatch(r'[a-z0-9_.-]+', identity):
        raise ValueError('Invalid addon identity')
    if (destination / identity).exists():
        raise ValueError('Refusing to overwrite an image builtin: ' + identity)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if sum(i.file_size for i in members) > 512 * 1024 * 1024:
            raise ValueError('Unexpectedly large addon')
        for item in members:
            path = PurePosixPath(item.filename)
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] != identity or '\\' in item.filename
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Unsafe addon archive')
        node = ET.fromstring(archive.read(identity + '/addon.xml'))
        if node.get('id') != identity or node.get('version') != version:
            raise ValueError('Addon identity/version mismatch')
        if archive.testzip():
            raise ValueError('Corrupt addon archive')
        archive.extractall(destination)


def version_tuple(value):
    return tuple(int(x) for x in re.findall(r'\d+', value))


def validate_base(root, lock):
    # LibreELEC 12 records its target in os-release, not /etc/arch.
    values = {}
    for line in (root / 'etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = value.strip().strip('"')
    if (values.get('ID') != 'libreelec' or values.get('LIBREELEC_ARCH') != lock['target']
            or values.get('VERSION') != lock['libreelec']['version']):
        raise ValueError('Rootfs identity, version or architecture mismatch')


def validate_closure(addons, roots):
    pending, selected = list(roots), {}
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        node = ET.parse(addons / identity / 'addon.xml').getroot()
        if node.get('id') != identity:
            raise ValueError('Addon ID mismatch: ' + identity)
        selected[identity] = node.get('version')
        for dep in node.findall('requires/import'):
            if dep.get('optional', 'false') == 'true':
                continue
            name = dep.get('addon')
            required = dep.get('version', '0')
            if not name or not re.fullmatch(r'[a-z0-9_.-]+', name):
                raise ValueError('Invalid dependency')
            child = ET.parse(addons / name / 'addon.xml').getroot()
            if version_tuple(child.get('version', '0')) < version_tuple(required):
                raise ValueError('Dependency too old: ' + name)
            pending.append(name)
    return selected


def copy_source(source, target, skin=False):
    target.mkdir()
    allowed = {'1080i', 'colors', 'extras', 'fonts', 'language', 'media', 'resources', 'shortcuts', 'addon.xml', 'LICENSE'}
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if (any(p.startswith('.') or p in ('__pycache__', 'vendor') for p in relative.parts)
                or path.suffix == '.pyc' or (skin and relative.parts[0] not in allowed)):
            continue
        if path.is_symlink():
            raise ValueError('Symlink in source snapshot: ' + str(relative))
        if path.is_file():
            if path.name in ('account.json', 'guisettings.xml', 'profiles.xml') or path.suffix in ('.log', '.db'):
                raise ValueError('Profile/cache data in source')
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def patch_kodi(root, skin, lock, scratch):
    kodi = root / 'usr/share/kodi'
    addons = kodi / 'addons'
    for record in lock['addons']:
        dest = scratch / (record['id'] + '.zip')
        print('Dependency:', record['id'], record['version'], flush=True)
        download(record['url'], dest, record['sha256'])
        extract_addon(dest, addons, record['id'], record['version'])
    copy_source(skin, addons / 'skin.stremio', skin=True)
    copy_source(skin / 'integration/plugin.video.stremioelec', addons / 'plugin.video.stremioelec')
    shutil.copy2(skin / 'LICENSE', addons / 'plugin.video.stremioelec/LICENSE')
    shutil.copytree(HERE / 'repository.stremioelec', addons / 'repository.stremioelec')
    shutil.copy2(skin / 'LICENSE', addons / 'repository.stremioelec/LICENSE')
    closure = validate_closure(addons, OWN_IDS)

    settings = kodi / 'system/settings/settings.xml'
    tree = ET.parse(settings)
    default = tree.find(".//setting[@id='lookandfeel.skin']/default")
    if default is None or default.text != 'skin.estuary':
        raise ValueError('Unknown base skin defaults')
    default.text = 'skin.stremio'
    tree.write(settings, encoding='utf-8', xml_declaration=True)

    manifest_path = kodi / 'system/addon-manifest.xml'
    manifest = ET.parse(manifest_path)
    old = next((n for n in manifest.getroot() if n.text == 'skin.estuary'), None)
    if old is None:
        raise ValueError('Missing base skin manifest')
    old.text = 'skin.stremio'
    present = {n.text for n in manifest.getroot()}
    for identity in sorted(closure):
        if identity not in present:
            ET.SubElement(manifest.getroot(), 'addon').text = identity
    manifest.write(manifest_path, encoding='utf-8', xml_declaration=True)
    # This is a newly extracted, disposable CI rootfs, never a running installation.
    estuary = addons / 'skin.estuary'
    if estuary.is_symlink() or not (estuary / 'addon.xml').is_file():
        raise ValueError('Unexpected Estuary package layout')
    shutil.rmtree(estuary)

    config = kodi / 'config/guisettings.xml'
    defaults = ET.parse(config)
    for identity, value in [('lookandfeel.skin', 'skin.stremio'), ('general.addonupdates', '2')]:
        node = defaults.find("setting[@id='" + identity + "']")
        if node is None:
            node = ET.SubElement(defaults.getroot(), 'setting', id=identity)
        node.attrib.pop('default', None)
        node.text = value
    defaults.write(config, encoding='utf-8', xml_declaration=True)

    script_dir = root / 'usr/lib/stremioelec'
    script_dir.mkdir(parents=True)
    shutil.copy2(HERE / 'bootstrap.py', script_dir / 'bootstrap.py')
    unit = root / 'usr/lib/systemd/system/kodi.service.d'
    unit.mkdir(parents=True, exist_ok=True)
    (unit / 'stremioelec.conf').write_text('[Service]\nExecStartPre=/usr/bin/python3 /usr/lib/stremioelec/bootstrap.py\n')
    build = dict(lock, build_commit=os.environ.get('BUILD_COMMIT', ''), dependency_closure=closure,
                 acceptance='UNTESTED ON N60', upstream_autoupdates=False)
    (root / 'etc/stremioelec-release.json').write_text(json.dumps(build, indent=2) + '\n')
    return build


def repository_zip(addons, output):
    """Produce a staged Kodi repository with nested addon/version ZIP paths."""
    with tempfile.TemporaryDirectory(prefix='stremio-repo-') as tmp:
        stage = Path(tmp)
        index = ET.Element('addons')
        for identity in OWN_IDS:
            source = addons / identity
            node = ET.parse(source / 'addon.xml').getroot()
            index.append(node)
            package = stage / identity / (identity + '-' + node.get('version') + '.zip')
            package.parent.mkdir()
            with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(source.rglob('*')):
                    if path.is_file():
                        archive.write(path, str(path.relative_to(addons)))
        data = ET.tostring(index, encoding='utf-8', xml_declaration=True)
        (stage / 'addons.xml').write_bytes(data)
        (stage / 'addons.xml.md5').write_text(hashlib.md5(data).hexdigest())
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, str(path.relative_to(stage)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skin', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0:
        raise SystemExit('Image writes are restricted to a disposable Linux CI runner')
    lock = json.loads((HERE / 'image.lock.json').read_text())
    if lock['target'] != 'Generic.x86_64':
        raise ValueError('Only reviewed Generic x86-64 target is supported')
    actual = subprocess.check_output(['git', '-c', 'safe.directory=' + str(args.skin), '-C', str(args.skin), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != lock['skin']['commit']:
        raise ValueError('Skin revision differs from lock')
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    name = 'StremioELEC-Generic.x86_64-' + lock['version']
    with tempfile.TemporaryDirectory(prefix='stremio-image-') as tmp:
        scratch = Path(tmp)
        packed, image = scratch / 'base.img.gz', scratch / 'test.img'
        download(lock['libreelec']['url'], packed, lock['libreelec']['sha256'])
        with gzip.open(packed, 'rb') as source, image.open('wb') as dest:
            shutil.copyfileobj(source, dest)
        if not image.is_file() or image.is_symlink():
            raise ValueError('Image must be a regular temporary file')
        loop = subprocess.check_output(['losetup', '--find', '--show', '--partscan', str(image)], text=True).strip()
        mount = scratch / 'boot'
        mount.mkdir()
        mounted = False
        try:
            if not re.fullmatch(r'/dev/loop[0-9]+', loop):
                raise ValueError('Not a temporary loop device')
            run('udevadm', 'settle')
            run('mount', '-o', 'nosuid,nodev,noexec', loop + 'p1', mount)
            mounted = True
            if not (mount / 'SYSTEM').is_file() or not (mount / 'KERNEL').is_file():
                raise ValueError('Unexpected upstream boot partition')
            original_kernel = digest(mount / 'KERNEL')
            root = scratch / 'rootfs'
            run('unsquashfs', '-no-progress', '-d', root, mount / 'SYSTEM')
            validate_base(root, lock)
            build = patch_kodi(root, args.skin, lock, scratch)
            system = scratch / 'SYSTEM'
            run('mksquashfs', root, system, '-noappend', '-comp', 'gzip', '-b', '262144', '-no-progress')
            free = shutil.disk_usage(mount).free + (mount / 'SYSTEM').stat().st_size
            if free - system.stat().st_size < 10 * 1024 * 1024:
                raise ValueError('SYSTEM does not fit the upstream boot partition safely')
            shutil.copyfile(system, mount / 'SYSTEM')
            for file in ('SYSTEM', 'KERNEL'):
                (mount / (file + '.md5')).write_text(digest(mount / file, 'md5') + '  ' + file + '\n')
            if digest(mount / 'KERNEL') != original_kernel or digest(mount / 'SYSTEM') != digest(system):
                raise ValueError('Boot partition readback failed')

            release = scratch / name
            target = release / 'target'
            target.mkdir(parents=True)
            for file in ('SYSTEM', 'KERNEL'):
                shutil.copyfile(mount / file, target / file)
                (target / (file + '.md5')).write_text(digest(target / file, 'md5') + '  target/' + file + '\n')
            (release / 'RELEASE').write_text(lock['version'] + '\nLibreELEC base: ' + lock['libreelec']['version'] + '\n')
            shutil.copytree(HERE.parent / 'licenses', release / 'licenses')
            shutil.copy2(HERE / 'README.md', release / 'README.md')
            with tarfile.open(output / (name + '.tar'), 'w') as archive:
                archive.add(release, arcname=name)
            repository_zip(root / 'usr/share/kodi/addons', output / 'addon-repository.zip')
            (output / 'provenance.json').write_text(json.dumps(build, indent=2) + '\n')
            shutil.copy2(HERE / 'README.md', output / 'README.md')
            run('sync')
            run('umount', mount)
            mounted = False
            run('fsck.vfat', '-n', loop + 'p1')
        finally:
            if mounted:
                run('umount', mount)
            run('losetup', '--detach', loop)
        with image.open('rb') as source, gzip.open(output / (name + '.img.gz'), 'wb', compresslevel=6) as dest:
            shutil.copyfileobj(source, dest)
    hashes = ''.join(digest(p) + '  ' + p.name + '\n' for p in sorted(output.iterdir()) if p.is_file())
    (output / 'SHA256SUMS').write_text(hashes)
    print('Test artifacts ready. N60 boot and update acceptance still required.', flush=True)


if __name__ == '__main__':
    main()
