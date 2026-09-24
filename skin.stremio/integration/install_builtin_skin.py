"""Replace packaged Estuary with StremioELEC in an explicitly selected test tree.

No profile/account files are copied. Default is a read-only dependency audit.
Retains the portable skin as a development override; new profiles use the bundle.
"""
import argparse
import shutil
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET


def closure(root):
    system, portable = root / 'addons', root / 'portable_data/addons'
    pending = ['skin.stremio', 'plugin.video.stremioelec']
    selected = {}
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        if '/' in identity or '..' in identity:
            raise ValueError('Unsafe addon ID')
        path = system / identity
        if not (path / 'addon.xml').is_file():
            path = portable / identity
        if not (path / 'addon.xml').is_file():
            raise ValueError('Missing dependency: ' + identity)
        node = ET.parse(path / 'addon.xml').getroot()
        if node.get('id') != identity:
            raise ValueError('Addon identity mismatch: ' + identity)
        selected[identity] = path
        pending.extend(n.get('addon') for n in node.findall('requires/import')
                       if n.get('optional', 'false') != 'true')
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kodi-root', type=Path, required=True)
    parser.add_argument('--backup-parent', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.kodi_root.resolve()
    if not (root / 'portable_data').is_dir():
        raise ValueError('Only an isolated portable test tree is supported')
    settings = root / 'system/settings/settings.xml'
    manifest = root / 'system/addon-manifest.xml'
    nodes = ET.parse(settings)
    skin = nodes.find(".//setting[@id='lookandfeel.skin']/default")
    if skin is None or skin.text != 'skin.estuary':
        raise ValueError('Expected original Estuary default; refusing a repeat/unknown install')
    addons = ET.parse(manifest)
    old = next((n for n in addons.getroot() if n.text == 'skin.estuary'), None)
    if old is None or not (root / 'addons/skin.estuary/addon.xml').is_file():
        raise ValueError('Expected packaged Estuary')
    selected = closure(root)
    copies = {key: path for key, path in selected.items() if path.parent != root / 'addons'}
    for identity in sorted(copies):
        if (root / 'addons' / identity).exists():
            raise ValueError('Destination already exists: ' + identity)
        print('Bundle:', identity)
    print('Default and required skin: skin.stremio')
    if not args.apply:
        return
    if args.backup_parent is None:
        raise ValueError('--backup-parent is required when applying')
    args.backup_parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='builtin-skin-', dir=args.backup_parent))
    shutil.copy2(settings, backup / 'settings.xml')
    shutil.copy2(manifest, backup / 'addon-manifest.xml')
    copied = []
    try:
        for identity, path in copies.items():
            destination = root / 'addons' / identity
            copied.append(destination)
            shutil.copytree(path, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
        skin.text = 'skin.stremio'
        old.text = 'skin.stremio'
        if not any(n.text == 'plugin.video.stremioelec' for n in addons.getroot()):
            ET.SubElement(addons.getroot(), 'addon').text = 'plugin.video.stremioelec'
        nodes.write(settings, encoding='utf-8', xml_declaration=True)
        addons.write(manifest, encoding='utf-8', xml_declaration=True)
        shutil.move(str(root / 'addons/skin.estuary'), backup / 'skin.estuary')
    except Exception:
        shutil.copy2(backup / 'settings.xml', settings)
        shutil.copy2(backup / 'addon-manifest.xml', manifest)
        # Retain partial copies for recovery instead of recursively deleting data.
        for path in copied:
            if path.exists():
                shutil.move(str(path), backup / path.name)
        raise
    print('Backup:', backup)
    print('Packaged Estuary moved outside Kodi. Portable account data untouched.')


if __name__ == '__main__':
    main()
