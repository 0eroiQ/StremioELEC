"""Build a reviewable offline pilot bundle, never install or enable addons."""
import argparse
import gzip
import hashlib
import json
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


def version(value):
    return tuple(int(v) if v.isdigit() else v for v in re.findall(r'\d+|[a-z]+', value.lower()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=True)
    builtins = {node.attrib['id']: node for p in (args.inputs / 'builtins').glob('*/addon.xml')
                for node in [ET.parse(p).getroot()]}
    available = {}
    for name, data, base in [
        ('Kodi', gzip.decompress((args.inputs / 'kodi.xml.gz').read_bytes()), 'https://mirrors.kodi.tv/addons/omega/'),
        ('Bingie', (args.inputs / 'bingie.xml').read_bytes(), 'https://raw.githubusercontent.com/matke-84/repository.bingie/main/omega/')
    ]:
        for node in ET.fromstring(data):
            available[node.attrib['id']] = (node, name, base)
    sources = {'skin.stremio': root, 'plugin.video.stremioelec': root / 'integration/plugin.video.stremioelec'}
    pending = [(key, '0') for key in sources]
    resolved, records, dependencies = {}, [], {}
    while pending:
        identity, minimum = pending.pop(0)
        if identity in resolved:
            if version(resolved[identity]) < version(minimum):
                raise ValueError('Dependency version conflict: ' + identity)
            continue
        if identity in builtins:
            node = builtins[identity]
            if version(node.attrib['version']) < version(minimum):
                raise ValueError('Built-in version too old: ' + identity)
            resolved[identity] = node.attrib['version']
            records.append({'id': identity, 'version': resolved[identity], 'source': 'LibreELEC image'})
            continue
        if identity in sources:
            node = ET.parse(sources[identity] / 'addon.xml').getroot()
            source, base = 'local source', None
        else:
            if identity.startswith('repository.'):
                raise ValueError('Repository dependency requires review: ' + identity)
            node, source, base = available[identity]
        current = node.attrib['version']
        if version(current) < version(minimum):
            raise ValueError('Repository version too old: ' + identity)
        filename = identity + '-' + current + '.zip'
        dest = args.output / filename
        url = None
        if base:
            url = base + identity + '/' + filename
            if not dest.exists():
                with urllib.request.urlopen(url, timeout=45) as response:
                    payload = response.read()
                dest.write_bytes(payload)
        else:
            with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(sources[identity].rglob('*')):
                    relative = path.relative_to(sources[identity])
                    if path.is_file() and not any(part.startswith('.') or part == '__pycache__'
                                                  for part in relative.parts):
                        if identity == 'skin.stremio' and relative.parts[0] in ('integration', 'README.md'):
                            continue
                        archive.write(path, identity + '/' + str(relative))
        with zipfile.ZipFile(dest) as archive:
            if archive.testzip():
                raise ValueError('Corrupt ZIP: ' + filename)
            for entry in archive.namelist():
                parts = pathlib.PurePosixPath(entry).parts
                if entry.startswith('/') or '..' in parts or not parts or parts[0] != identity:
                    raise ValueError('Unsafe ZIP layout: ' + filename)
            actual = ET.fromstring(archive.read(identity + '/addon.xml'))
            if actual.attrib['id'] != identity or actual.attrib['version'] != current:
                raise ValueError('Manifest mismatch: ' + identity)
        # Resolve actual ZIP requirements, not just the repository index.
        dependencies[identity] = []
        for dep in actual.findall('requires/import'):
            if dep.attrib.get('optional', 'false') != 'true':
                pending.append((dep.attrib['addon'], dep.attrib.get('version', '0')))
                dependencies[identity].append(dep.attrib['addon'])
        resolved[identity] = current
        records.append({'id': identity, 'version': current, 'source': source, 'url': url,
                        'file': filename, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
        print(identity, current, flush=True)
    ordered, visiting, visited = [], set(), set()
    by_id = {r['id']: r for r in records}

    def visit(identity):
        if identity in visited:
            return
        if identity in visiting:
            raise ValueError('Dependency cycle: ' + identity)
        visiting.add(identity)
        for dependency in dependencies.get(identity, []):
            visit(dependency)
        visiting.remove(identity)
        visited.add(identity)
        if 'file' in by_id[identity]:
            ordered.append(by_id[identity]['file'])

    for identity in sources:
        visit(identity)
    (args.output / 'INSTALL.md').write_text(
        '# Stremio skin offline pilot\n\n'
        'Target: LibreELEC Generic 12.2.1 / Kodi 21.3. Not a bootable image.\n\n'
        'Use a separate test installation and back up its Kodi profile first. '
        'Do not overwrite the working Android disk. Verify SHA256SUMS before use. '
        'These hashes detect changes; they are not upstream signatures.\n\n'
        'In Kodi, allow installation from ZIP only for this reviewed test, then '
        'install the following ZIPs individually in this dependency-first order. '
        'No third-party update repository is included. Decline switching skins '
        'until all packages are installed. Disable unknown sources afterwards.\n\n'
        + ''.join(f'{i}. `{name}`\n' for i, name in enumerate(ordered, 1))
        + '\nSelect Stremio skin in Interface settings. The internal ID is still '
        'skin.stremio: this replaces an existing Bingie installation. '
        'Open Videos / Add-ons / StremioELEC catalogs to test the bridge.\n\n'
        'Cinemeta supplies metadata, not playable streams. QR login, account sync '
        'and cross-addon aggregation are not implemented. Legacy Bingie/TMDB '
        'dependencies remain temporarily. No physical playback, remote, HDR or '
        'audio-format validation has been performed.\n')
    (args.output / 'bundle-lock.json').write_text(json.dumps(records, indent=2) + '\n')
    (args.output / 'SHA256SUMS').write_text(''.join(r['sha256'] + '  ' + r['file'] + '\n'
                                               for r in records if 'file' in r))
    print('Complete:', len(records), 'resolved packages, including image built-ins.')


if __name__ == '__main__':
    main()
