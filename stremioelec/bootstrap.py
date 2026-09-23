#!/usr/bin/python3
"""Seed safe update defaults before Kodi starts; never copy an account/profile.

Runs once per new installation. Existing profiles are not silently migrated.
"""
from pathlib import Path
import xml.etree.ElementTree as ET


def seed(storage):
    storage = Path(storage)
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
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.xml.new')
    tree.write(temporary, encoding='utf-8', xml_declaration=True)
    temporary.chmod(0o600)
    temporary.replace(target)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('1\n')


if __name__ == '__main__':
    seed('/storage')
