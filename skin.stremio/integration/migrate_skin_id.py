"""One-time portable test migration. Run with Kodi stopped, before bundling."""
import argparse
import shutil
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET


def migrate(root, source, backup_parent):
    root, source = Path(root).resolve(), Path(source).resolve()
    data = root / 'portable_data'
    old = data / 'addons/skin.bingie'
    new = data / 'addons/skin.stremio'
    old_profile = data / 'userdata/addon_data/skin.bingie'
    new_profile = data / 'userdata/addon_data/skin.stremio'
    gui = data / 'userdata/guisettings.xml'
    shortcuts = data / 'userdata/addon_data/script.skinshortcuts'
    if not old.is_dir() or new.exists() or new_profile.exists():
        raise ValueError('Expected unmigrated portable test skin')
    if ET.parse(source / 'addon.xml').getroot().get('id') != 'skin.stremio':
        raise ValueError('Expected renamed source')
    settings = ET.parse(gui)
    active = settings.find("setting[@id='lookandfeel.skin']")
    if active is None or active.text != 'skin.bingie':
        raise ValueError('Expected active Bingie test skin')
    pairs = [(p, p.with_name(p.name.replace('skin.bingie', 'skin.stremio', 1)))
             for p in shortcuts.glob('skin.bingie*') if p.is_file()]
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
        shutil.copy2(bridge / name, backup / name)
        shutil.copy2(source / 'integration/plugin.video.stremioelec' / name, bridge / name)
    active.text = 'skin.stremio'
    settings.write(gui, encoding='utf-8', xml_declaration=True)
    # Keep old addon and preferences outside scanned Kodi folders, recoverably.
    shutil.move(str(old), backup / 'skin.bingie')
    if old_profile.exists():
        shutil.move(str(old_profile), backup / 'old-skin-preferences')
    print('Migrated skin ID and copied', len(pairs), 'shortcut files.')
    print('Backup:', backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kodi-root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--backup-parent', type=Path, required=True)
    args = parser.parse_args()
    migrate(args.kodi_root, args.source, args.backup_parent)
