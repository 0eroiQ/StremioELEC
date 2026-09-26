#!/usr/bin/env python3
"""Build a portable Kodi 21 StremioELEC test repository.

No Kodi profile is modified. Output is an offline repository tree plus the
single repository ZIP a tester installs first.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEST_BRANCH = 'portable-repository-test'
TEST_BASE = 'https://raw.githubusercontent.com/0eroiQ/StremioELEC/' + TEST_BRANCH + '/'
PORTABLE_THIRD_PARTY = ()
OWN = ('plugin.video.stremioelec', 'skin.stremioelec', 'service.stremioelec.portable')
KODI_BUILTINS = {'kodi.resource', 'script.module.pil'}


def digest(path, algorithm='sha256'):
    result = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def download(url, path, expected):
    if not url.startswith('https://') or not re.fullmatch(r'[a-f0-9]{64}', expected):
        raise ValueError('Unpinned or insecure portable dependency')
    request = urllib.request.Request(url, headers={'User-Agent': 'StremioELEC-portable/0.1'})
    with urllib.request.urlopen(request, timeout=120) as response, path.open('wb') as output:
        if not response.url.startswith('https://'):
            raise ValueError('Insecure dependency redirect')
        shutil.copyfileobj(response, output)
    if digest(path) != expected:
        raise ValueError('Dependency checksum mismatch: ' + path.name)


def zip_manifest(path, identity=None, version=None):
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if not members or sum(i.file_size for i in members) > 512 * 1024 * 1024:
            raise ValueError('Invalid addon archive size')
        roots = {PurePosixPath(i.filename).parts[0] for i in members if PurePosixPath(i.filename).parts}
        if len(roots) != 1:
            raise ValueError('Addon ZIP must contain one root directory')
        root = next(iter(roots))
        for item in members:
            p = PurePosixPath(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe addon ZIP')
        node = ET.fromstring(archive.read(root + '/addon.xml'))
        if identity and node.get('id') != identity:
            raise ValueError('Dependency addon ID mismatch')
        if version and node.get('version') != version:
            raise ValueError('Dependency version mismatch')
        if archive.testzip():
            raise ValueError('Corrupt addon ZIP')
        return node


def copy_tree(source, target, skin=False):
    target.mkdir(parents=True)
    skin_allowed = {'1080i', 'colors', 'extras', 'fonts', 'language', 'media',
                    'resources', 'shortcuts', 'addon.xml', 'LICENSE'}
    for path in sorted(source.rglob('*')):
        rel = path.relative_to(source)
        if (any(part.startswith('.') or part in ('__pycache__', 'vendor') for part in rel.parts)
                or path.suffix == '.pyc' or (skin and rel.parts[0] not in skin_allowed)):
            continue
        if path.is_symlink():
            raise ValueError('Symlink in portable source: ' + str(rel))
        if path.is_file():
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def package_folder(source, repo_root):
    manifest = ET.parse(source / 'addon.xml').getroot()
    identity, version = manifest.get('id'), manifest.get('version')
    if not identity or not version:
        raise ValueError('Portable addon identity/version missing')
    dest = repo_root / identity / (identity + '-' + version + '.zip')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                archive.write(path, str(Path(identity) / path.relative_to(source)))
    parsed = zip_manifest(dest, identity, version)
    return parsed, dest


def build_own(stage):
    plugin = stage / 'plugin.video.stremioelec'
    copy_tree(ROOT / 'skin.stremioelec/integration/plugin.video.stremioelec', plugin)
    shutil.copy2(HERE / 'portable/plugin.video.stremioelec/addon.xml', plugin / 'addon.xml')
    shutil.copy2(ROOT / 'skin.stremioelec/LICENSE', plugin / 'LICENSE')

    skin = stage / 'skin.stremioelec'
    copy_tree(ROOT / 'skin.stremioelec', skin, skin=True)

    portable = stage / 'service.stremioelec.portable'
    copy_tree(HERE / 'portable/service.stremioelec.portable', portable)
    shutil.copy2(ROOT / 'skin.stremioelec/LICENSE', portable / 'LICENSE')


def dependency_closure(index):
    identities = set(index)
    missing = set()
    for node in index.values():
        for dep in node.findall('requires/import'):
            if dep.get('optional', 'false') == 'true':
                continue
            identity = dep.get('addon', '')
            if identity.startswith('xbmc.') or identity in KODI_BUILTINS:
                continue
            if identity not in identities:
                missing.add(identity)
    return sorted(missing)


def repository_addon(output):
    source = output / 'repository.stremioelec.test'
    source.mkdir()
    (source / 'addon.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<addon id="repository.stremioelec.test" name="StremioELEC Test Repository" '
        'version="0.2.0" provider-name="0eroiQ">\n'
        '  <extension point="xbmc.addon.repository" name="StremioELEC Test">\n'
        '    <dir>\n'
        '      <info compressed="false">' + TEST_BASE + 'addons.xml</info>\n'
        '      <checksum>' + TEST_BASE + 'addons.xml.md5</checksum>\n'
        '      <datadir>' + TEST_BASE + '</datadir>\n'
        '    </dir>\n'
        '  </extension>\n'
        '  <extension point="xbmc.addon.metadata">\n'
        '    <summary lang="en_GB">Test repository for StremioELEC for Kodi</summary>\n'
        '    <description lang="en_GB">Portable Kodi 21 pilot. Not the StremioELEC OS update channel.</description>\n'
        '    <platform>all</platform><license>GPL-2.0-or-later</license>\n'
        '    <source>https://github.com/0eroiQ/StremioELEC</source>\n'
        '  </extension>\n'
        '</addon>\n')
    shutil.copy2(ROOT / 'skin.stremioelec/LICENSE', source / 'LICENSE')
    manifest, archive = package_folder(source, output)
    top = output / archive.name
    shutil.copy2(archive, top)
    return top


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Portable output already exists')
    args.output.mkdir(parents=True)
    repo_root = args.output / 'repository'
    repo_root.mkdir()

    lock = json.loads((HERE / 'image.lock.json').read_text())
    if lock.get('kodi_major') != 21:
        raise ValueError('Portable pilot currently targets Kodi 21 only')

    index = {}
    with tempfile.TemporaryDirectory(prefix='stremio-portable-') as tmp:
        scratch = Path(tmp)
        own_stage = scratch / 'own'
        own_stage.mkdir()
        build_own(own_stage)
        for identity in OWN:
            node, _ = package_folder(own_stage / identity, repo_root)
            index[identity] = node

        # Portable StremioELEC is self-contained. Kodi provides only its built-in APIs.
        # No Bingie/TMDb-helper/Skin-Shortcuts package is mirrored into this repository.

    missing = dependency_closure(index)
    if missing:
        raise ValueError('Portable repository dependency closure incomplete: ' + ', '.join(missing))

    root = ET.Element('addons')
    for identity in sorted(index):
        root.append(index[identity])
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    (repo_root / 'addons.xml').write_bytes(data)
    (repo_root / 'addons.xml.md5').write_text(hashlib.md5(data).hexdigest())

    bootstrap = repository_addon(args.output)
    info = {
        'schema': 1,
        'kodi_major': 21,
        'mode': 'portable',
        'repository_branch': TEST_BRANCH,
        'install_first': bootstrap.name,
        'addons': {identity: index[identity].get('version') for identity in OWN},
        'third_party_addons': list(PORTABLE_THIRD_PARTY),
    }
    (args.output / 'portable-manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    hashes = ''.join(digest(p) + '  ' + str(p.relative_to(args.output)) + '\n'
                     for p in sorted(args.output.rglob('*')) if p.is_file())
    (args.output / 'SHA256SUMS').write_text(hashes)
    print('Portable Kodi repository ready:', bootstrap, flush=True)


if __name__ == '__main__':
    main()
