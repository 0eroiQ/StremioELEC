#!/usr/bin/python3
"""Seed safe defaults and migrate the StremioELEC skin ID before Kodi starts."""
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

OLD_SKIN = 'skin.stremio'
NEW_SKIN = 'skin.stremioelec'


def write_xml(tree, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.new')
    tree.write(temporary, encoding='utf-8', xml_declaration=True)
    temporary.chmod(0o600)
    temporary.replace(target)


def migrate_skin_id(storage):
    """Migrate an existing test.7-era profile without touching media/account data."""
    storage = Path(storage)
    marker = storage / '.config/stremioelec/skin-id-v2'
    if marker.exists():
        return

    kodi = storage / '.kodi'
    userdata = kodi / 'userdata'
    gui = userdata / 'guisettings.xml'

    if gui.exists():
        tree = ET.parse(gui)
        active = tree.find("setting[@id='lookandfeel.skin']")
        if active is not None and active.text == OLD_SKIN:
            active.text = NEW_SKIN
            write_xml(tree, gui)

    old_profile = userdata / 'addon_data' / OLD_SKIN
    new_profile = userdata / 'addon_data' / NEW_SKIN
    if old_profile.is_dir() and not new_profile.exists():
        new_profile.parent.mkdir(parents=True, exist_ok=True)
        old_profile.rename(new_profile)

    shortcuts = userdata / 'addon_data/script.skinshortcuts'
    if shortcuts.is_dir():
        for source in shortcuts.glob(OLD_SKIN + '*'):
            if not source.is_file():
                continue
            target = source.with_name(
                source.name.replace(OLD_SKIN, NEW_SKIN, 1))
            if not target.exists():
                shutil.copy2(source, target)

    # Old code overrides must not remain as a second selectable skin.
    old_addon = kodi / 'addons' / OLD_SKIN
    if old_addon.is_dir():
        backup_root = storage / '.config/stremioelec/legacy-addons'
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / OLD_SKIN
        if backup.exists():
            shutil.rmtree(old_addon)
        else:
            shutil.move(str(old_addon), str(backup))

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('1\n')


def seed(storage):
    storage = Path(storage)

    # This migration is independent of the original seed marker, so upgrades
    # from test.7 are repaired even when safe defaults were already seeded.
    migrate_skin_id(storage)

    marker = storage / '.config/stremioelec/seed-v1'
    if marker.exists():
        return

    target = storage / '.kodi/userdata/addon_data/service.libreelec.settings/oe_settings.xml'
    tree = ET.parse(target) if target.exists() else ET.ElementTree(ET.Element('libreelec'))
    root = tree.getroot()
    if root.tag != 'libreelec':
        raise ValueError('Unexpected LibreELEC settings schema')
    settings = root.find('settings')
    if settings is None:
        settings = ET.SubElement(root, 'settings')
    updates = settings.find('updates')
    if updates is None:
        updates = ET.SubElement(settings, 'updates')
    for key, value in [('AutoUpdate', 'manual'), ('UpdateNotify', '0'), ('SubmitStats', '0')]:
        node = updates.find(key)
        if node is None:
            node = ET.SubElement(updates, key)
        node.text = value
    write_xml(tree, target)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('1\n')


if __name__ == '__main__':
    seed('/storage')
