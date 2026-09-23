"""One-time local setup. Never overwrite user customizations on reconnect."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

ROWS = [
    ('Popular Movies', 'popular', 'movie'),
    ('Top Rated Movies', 'top_rated', 'movie'),
    ('Popular TV Shows', 'popular', 'tv'),
    ('Top Rated TV Shows', 'top_rated', 'tv'),
    ('Trending Movies This Week', 'trending_week', 'movie'),
    ('Trending TV This Week', 'trending_week', 'tv'),
    ('Now Playing Movies', 'now_playing', 'movie'),
    ('Upcoming Movies', 'upcoming', 'movie'),
    ('TV On The Air', 'on_the_air', 'tv'),
]


def home_xml():
    root = ET.Element('shortcuts')
    targets = [('Continue Watching', 'plugin://plugin.video.stremioelec/?action=continue')]
    targets += [(name, 'plugin://plugin.video.tmdb.bingie.helper/?' + urlencode({
        'info': route, 'tmdb_type': kind, 'widget': 'true'})) for name, route, kind in ROWS]
    for name, route in targets:
        row = ET.SubElement(root, 'shortcut')
        for key, value in [('label', name), ('label2', ''), ('icon', 'DefaultShortcut.png'),
                           ('thumb', ''), ('action', route)]:
            ET.SubElement(row, key).text = value
        ET.SubElement(row, 'additional-properties').text = "[('widgetlimit', '20')]"
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(payload)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def replace_backed_up(path, payload, backups):
    path = Path(path)
    key = path.parent.name + '--' + path.name
    destination = Path(backups) / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not destination.exists():
        shutil.copy2(path, destination)
    atomic_write(path, payload)


def rpc(method, params=None):
    import xbmc
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
    if 'error' in response:
        raise RuntimeError('Kodi settings request failed')
    return response.get('result')


def get_setting(name, fallback=None):
    try:
        return rpc('Settings.GetSettingValue', {'setting': name}).get('value', fallback)
    except Exception:
        return fallback


def prepare(profile, addon_path, force_home=False):
    import xbmc
    import xbmcaddon
    import xbmcvfs
    from account import Store
    state_store = Store(Path(profile) / 'setup')
    state = state_store.load()
    if state.get('completed') and not force_home:
        return state
    if not xbmc.getCondVisibility('System.HasAddon(plugin.video.tmdb.bingie.helper)'):
        raise RuntimeError('TMDb Bingie Helper is required')
    if not xbmc.getCondVisibility('System.HasAddon(script.skinshortcuts)'):
        raise RuntimeError('Skin Shortcuts is required')
    backups = Path(profile) / 'setup-backup'
    target = Path(xbmcvfs.translatePath('special://profile/addon_data/script.skinshortcuts/skin.stremio-10000-1.DATA.xml'))
    # Record the original before touching any persistent setting.
    if not state:
        state = {'completed': False, 'device_policy': 'safe-unverified-hdmi', 'before': {}, 'applied': {}}
        for key in ('audiooutput.passthrough', 'videoplayer.adjustrefreshrate', 'videoplayer.usedisplayasclock', 'subtitles.movie', 'subtitles.tv'):
            state['before'][key] = get_setting(key)
        state_store.save(state)
    replace_backed_up(target, home_xml(), backups)
    helper = xbmcaddon.Addon('plugin.video.tmdb.bingie.helper')
    helper_profile = Path(xbmcvfs.translatePath(helper.getAddonInfo('profile')))
    player = Path(addon_path) / 'resources/stremioelec-player.json'
    replace_backed_up(helper_profile / 'players/stremioelec.json', player.read_bytes(), backups)
    for key, value in [('default_player_movies', 'stremioelec.json play_movie'),
                       ('default_player_episodes', 'stremioelec.json play_episode')]:
        state['before'].setdefault(key, helper.getSetting(key))
        state_store.save(state)
        helper.setSetting(key, value)
    # Existence of a codec setting is NOT proof of GPU or HDMI support.
    # Preserve platform decoder defaults, resolution and output device.
    # Until HDMI is verified use decoded audio and avoid automatic mode changes.
    if not state.get('completed'):
        for key, value in [('audiooutput.passthrough', False),
                           ('videoplayer.adjustrefreshrate', 0),
                           ('videoplayer.usedisplayasclock', False)]:
            if state['before'].get(key) is not None:
                try:
                    if rpc('Settings.SetSettingValue', {'setting': key, 'value': value}):
                        state['applied'][key] = value
                except Exception:
                    pass
    state['platform'] = next((name for name in ('linux', 'osx', 'android', 'windows')
                              if xbmc.getCondVisibility('System.Platform.' + name)), 'unknown')
    for key in ('subtitles.movie', 'subtitles.tv'):
        # Keep an existing user-selected subtitle service.
        if not get_setting(key, ''):
            state['before'].setdefault(key, '')
            state_store.save(state)
            try:
                if rpc('Settings.SetSettingValue', {'setting': key, 'value': 'plugin.video.stremioelec'}):
                    state['applied'][key] = 'plugin.video.stremioelec'
            except Exception:
                pass
    state['completed'] = True
    state_store.save(state)
    return state
