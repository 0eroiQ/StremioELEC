"""Reversible StremioELEC portable-mode control."""
import json
import os
from pathlib import Path
import tempfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon('service.stremioelec.portable')
PROFILE = Path(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')))
STATE = PROFILE / 'state.json'


def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        payload['params'] = params
    data = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    if data.get('error'):
        raise RuntimeError('Kodi rejected the settings change')
    return data.get('result')


def load():
    if not STATE.exists():
        return {}
    try:
        value = json.loads(STATE.read_text())
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def save(value):
    PROFILE.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=PROFILE, prefix='.portable-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, STATE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def current_skin():
    result = rpc('Settings.GetSettingValue', {'setting': 'lookandfeel.skin'}) or {}
    return result.get('value') or 'skin.estuary'


def set_skin(identity):
    if not xbmc.getCondVisibility('System.HasAddon(' + identity + ')'):
        raise RuntimeError('Required skin is not installed: ' + identity)
    result = rpc('Settings.SetSettingValue', {'setting': 'lookandfeel.skin', 'value': identity})
    if result not in ('OK', True, None):
        raise RuntimeError('Kodi did not accept the skin change')
    xbmc.executebuiltin('ReloadSkin()')


def enable():
    state = load()
    previous = state.get('previous_skin')
    active = current_skin()
    if active != 'skin.stremio':
        previous = active
    state.update({'initialized': True, 'enabled': True,
                  'previous_skin': previous or 'skin.estuary'})
    save(state)
    set_skin('skin.stremio')


def restore():
    state = load()
    target = state.get('previous_skin') or 'skin.estuary'
    if target == 'skin.stremio' or not xbmc.getCondVisibility('System.HasAddon(' + target + ')'):
        target = 'skin.estuary'
    state.update({'initialized': True, 'enabled': False})
    save(state)
    set_skin(target)


def status():
    state = load()
    return {'enabled': bool(state.get('enabled')),
            'previous_skin': state.get('previous_skin') or 'skin.estuary',
            'current_skin': current_skin()}


def menu():
    info = status()
    dialog = xbmcgui.Dialog()
    options = ['Enable StremioELEC Mode', 'Restore Kodi UI']
    choice = dialog.select('StremioELEC for Kodi', options)
    if choice == 0:
        if dialog.yesno('Enable StremioELEC Mode?',
                'StremioELEC will become the Kodi interface. Your current skin is remembered and can be restored later.'):
            enable()
    elif choice == 1:
        if dialog.yesno('Restore Kodi UI?',
                'Restore the skin that was active before StremioELEC Mode?'):
            restore()
