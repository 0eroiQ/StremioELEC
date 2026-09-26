"""Optional StremioELEC Skin control for an existing Kodi installation."""
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
NEW_SKIN = 'skin.stremioelec'
LEGACY_SKIN = 'skin.stremio'


def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        payload['params'] = params
    data = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    if data.get('error'):
        raise RuntimeError('Playback engine rejected the settings change')
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
        raise RuntimeError('Required interface is not installed: ' + identity)
    result = rpc('Settings.SetSettingValue', {'setting': 'lookandfeel.skin', 'value': identity})
    if result not in ('OK', True, None):
        raise RuntimeError('Playback engine did not accept the interface change')
    xbmc.executebuiltin('ReloadSkin()')


def begin_onboarding():
    """Record installation state without changing the user's active Kodi skin.

    The only automatic switch is a legacy-ID migration when the user was
    already actively using the previous StremioELEC skin.
    """
    state = load()
    active = current_skin()
    previous = state.get('previous_skin')

    if active == LEGACY_SKIN and xbmc.getCondVisibility('System.HasAddon(' + NEW_SKIN + ')'):
        previous = previous or 'skin.estuary'
        set_skin(NEW_SKIN)
        active = NEW_SKIN
    elif active != NEW_SKIN:
        previous = active

    state.update({
        'initialized': True,
        'enabled': active == NEW_SKIN,
        'previous_skin': previous or 'skin.estuary',
    })
    save(state)


def enable():
    """Explicit user action: switch the current Kodi profile to StremioELEC Skin."""
    state = load()
    active = current_skin()
    previous = state.get('previous_skin')
    if active != NEW_SKIN:
        previous = active
    state.update({
        'initialized': True,
        'enabled': True,
        'previous_skin': previous or 'skin.estuary',
    })
    save(state)
    set_skin(NEW_SKIN)


def restore():
    state = load()
    target = state.get('previous_skin') or 'skin.estuary'
    if target in (NEW_SKIN, LEGACY_SKIN) or not xbmc.getCondVisibility('System.HasAddon(' + target + ')'):
        target = 'skin.estuary'
    state.update({'initialized': True, 'enabled': False})
    save(state)
    set_skin(target)


def status():
    state = load()
    return {
        'enabled': current_skin() == NEW_SKIN,
        'previous_skin': state.get('previous_skin') or 'skin.estuary',
        'current_skin': current_skin(),
    }


def menu():
    dialog = xbmcgui.Dialog()
    choice = dialog.select(
        'StremioELEC for Kodi',
        ['Use StremioELEC Skin', 'Restore previous interface'])
    if choice == 0:
        if dialog.yesno(
                'Use StremioELEC Skin?',
                'Switch this Kodi profile to the optional StremioELEC Skin?'):
            enable()
    elif choice == 1:
        if dialog.yesno(
                'Restore previous interface?',
                'Return to the interface that was active before StremioELEC Skin?'):
            restore()
