"""One-time skin-ID migration. Run with Kodi stopped, before bundling."""
import argparse
import shutil
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

NEW_ID = 'skin.stremioelec'
LEGACY_IDS = ('skin.stremio', 'skin.bingie')


def legacy_identity(data, active):
    for identity in LEGACY_IDS:
        if active == identity and (data / 'addons' / identity).is_dir():
            return identity
    for identity in LEGACY_IDS:
        if (data / 'addons' / identity).is_dir():
            return identity
    raise ValueError('Expected an installed legacy StremioELEC/Bingie skin')


def migrate(root, source, backup_parent):
    root, source = Path(root).resolve(), Path(source).resolve()
    data = root / 'portable_data'
    gui = data / 'userdata/guisettings.xml'
    shortcuts = data / 'userdata/addon_data/script.skinshortcuts'

    if ET.parse(source / 'addon.xml').getroot().get('id') != NEW_ID:
        raise ValueError('Expected renamed StremioELEC Skin source')

    settings = ET.parse(gui)
    active = settings.find("setting[@id='lookandfeel.skin']")
    if active is None:
        raise ValueError('Missing active skin setting')

    old_id = legacy_identity(data, active.text)
    old = data / 'addons' / old_id
    new = data / 'addons' / NEW_ID
    old_profile = data / 'userdata/addon_data' / old_id
    new_profile = data / 'userdata/addon_data' / NEW_ID

    if new.exists() or new_profile.exists():
        raise ValueError('New StremioELEC Skin identity already exists')
    if active.text != old_id:
        raise ValueError('Expected active legacy StremioELEC/Bingie skin')

    pairs = [
        (p, p.with_name(p.name.replace(old_id, NEW_ID, 1)))
        for p in shortcuts.glob(old_id + '*') if p.is_file()
    ]
    if any(dest.exists() for _, dest in pairs):
        raise ValueError('New shortcut files already exist')

    backup_parent = Path(backup_parent)
    backup_parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='skin-id-', dir=backup_parent))
    shutil.copy2(gui, backup / 'guisettings.xml')

    shutil.copytree(old, new)
    shutil.copy2(source / 'addon.xml', new / 'addon.xml')
    if old_profile.exists():
        shutil.copytree(old_profile, new_profile)
    for src, dest in pairs:
        shutil.copy2(src, dest)

    # These modules use the skin-specific shortcut prefix, not account data.
    bridge = data / 'addons/plugin.video.stremioelec'
    for name in ('settings_ui.py', 'setup_profile.py'):
        if (bridge / name).is_file():
            shutil.copy2(bridge / name, backup / name)
            shutil.copy2(
                source / 'integration/plugin.video.stremioelec' / name,
                bridge / name)

    active.text = NEW_ID
    settings.write(gui, encoding='utf-8', xml_declaration=True)

    # Keep the old addon/preferences outside scanned Kodi folders, recoverably.
    shutil.move(str(old), backup / old_id)
    if old_profile.exists():
        shutil.move(str(old_profile), backup / 'old-skin-preferences')

    print('Migrated', old_id, 'to', NEW_ID, 'and copied', len(pairs), 'shortcut files.')
    print('Backup:', backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kodi-root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--backup-parent', type=Path, required=True)
    args = parser.parse_args()
    migrate(args.kodi_root, args.source, args.backup_parent)
