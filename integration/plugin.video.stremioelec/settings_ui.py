"""Curated appliance settings. Never opens the generic addon/settings browser."""
import sys
import ast
from decimal import Decimal
from pathlib import Path
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from account import Store
from setup_profile import rpc, get_setting, prepare, replace_backed_up, home_xml

ADDON = xbmcaddon.Addon('plugin.video.stremioelec')
PROFILE = Path(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')))
DIALOG = xbmcgui.Dialog()
HOME = 'special://profile/addon_data/script.skinshortcuts/skin.stremio-10000-1.DATA.xml'

COLORS = [('White', 'FFFFFFFF'), ('Yellow', 'FFFFFF00'), ('Light gray', 'FFCCCCCC'),
          ('Black', 'FF000000'), ('Cyan', 'FF00FFFF')]
APPEARANCE = [('PreferTvShowThumbWidget', 'Use show artwork for episodes'),
              ('EnableColorDetailsIcons', 'Colored detail icons'),
              ('EnableStudioLogo', 'Studio logos'),
              ('AutoCloseVideoOSD', 'Automatically hide playback controls'),
              ('ChapterMarks', 'Chapter markers'),
              ('EnableBufferingProgressOSD', 'Show buffering progress')]


def setting_options(setting):
    """Use device-provided choices, including list and numeric definitions."""
    options = setting.get('options') or setting.get('definition', {}).get('options', [])
    if options:
        return options
    if setting.get('id') in ('subtitles.colorpick', 'subtitles.bordercolorpick', 'subtitles.bgcolorpick'):
        return [{'label': label, 'value': value} for label, value in COLORS]
    if isinstance(setting.get('value'), (int, float)) and not isinstance(setting.get('value'), bool):
        if all(key in setting for key in ('minimum', 'maximum', 'step')):
            low, high, step = [Decimal(str(setting[k])) for k in ('minimum', 'maximum', 'step')]
            if step > 0 and high >= low and (high - low) / step <= 500:
                values = [low + step * i for i in range(int((high - low) / step) + 1)]
                return [{'label': format(v.normalize(), 'f'), 'value': int(v) if isinstance(setting['value'], int) else float(v)} for v in values]
    return []


def update_row_limit(row, limit):
    """Preserve all unrelated shortcut properties; never eval user data."""
    props = row.find('additional-properties')
    if props is None:
        props = ET.SubElement(row, 'additional-properties')
    pairs = ast.literal_eval(props.text) if props.text else []
    if not isinstance(pairs, list) or any(not isinstance(p, (tuple, list)) or len(p) != 2 for p in pairs):
        raise ValueError('Invalid shortcut properties')
    props.text = repr([(key, value) for key, value in pairs if key != 'widgetlimit'] + [('widgetlimit', str(limit))])


def choose(title, options):
    return DIALOG.select(title, options)


def edit_kodi(key, label):
    settings = rpc('Settings.GetSettings', {'level': 'expert'}).get('settings', [])
    setting = next((item for item in settings if item['id'] == key), None)
    if not setting or not setting.get('enabled', True):
        DIALOG.ok('StremioELEC', 'This option is not available on this device.')
        return
    value = setting.get('value')
    previous = value
    options = setting_options(setting)
    if isinstance(value, bool):
        value = not value
    elif options:
        if isinstance(value, list):
            selected = DIALOG.multiselect(label, [str(o['label']) for o in options],
                                          preselect=[i for i, o in enumerate(options) if o['value'] in value])
            if selected is None:
                return
            value = [options[i]['value'] for i in selected]
        else:
            index = DIALOG.select(label, [str(o['label']) for o in options],
                                  preselect=next((i for i, o in enumerate(options) if o['value'] == value), 0))
            if index < 0:
                return
            value = options[index]['value']
    else:
        DIALOG.ok('StremioELEC', 'No supported choices were reported by this device. Current value: ' + str(value))
        return
    if not rpc('Settings.SetSettingValue', {'setting': key, 'value': value}):
        raise RuntimeError('Setting was rejected')
    if key in ('videoscreen.resolution', 'videoscreen.screenmode'):
        if not DIALOG.yesno('Keep display mode?', 'Confirm within 15 seconds or the previous mode will be restored.', autoclose=15000):
            if not rpc('Settings.SetSettingValue', {'setting': key, 'value': previous}):
                raise RuntimeError('Could not restore previous display mode')


def kodi_menu(title, entries):
    while True:
        definitions = {s['id']: s for s in rpc('Settings.GetSettings', {'level': 'expert'}).get('settings', [])}
        available = [(key, name, definitions[key]) for key, name in entries if key in definitions and definitions[key].get('value') is not None]
        def summary(setting):
            value = setting['value']
            text = next((str(o['label']) for o in setting_options(setting) if o['value'] == value), display_value(value))
            return text + (' (unavailable)' if not setting.get('enabled', True) else '')
        if not available:
            DIALOG.ok(title, 'No supported settings were reported by this platform.')
            return
        index = choose(title, [name + ': ' + summary(setting) for key, name, setting in available])
        if index < 0:
            return
        key, name, _ = available[index]
        edit_kodi(key, name)


def display_value(value):
    if isinstance(value, bool):
        return 'On' if value else 'Off'
    if isinstance(value, list):
        return ', '.join(str(item) for item in value)
    return str(value)


def helper_menu():
    selection = choose('Catalogs and artwork', ['Catalog and artwork options', 'TMDb trailer API key'])
    if selection < 0:
        return
    if selection == 1:
        action = choose('TMDb trailer API key', ['Replace key (stored locally)', 'Remove key (use existing trailer list)'])
        if action == 0:
            value = DIALOG.input('TMDb API key', type=xbmcgui.INPUT_ALPHANUM,
                                 option=xbmcgui.ALPHANUM_HIDE_INPUT)
            if value.strip():
                ADDON.setSetting('tmdb_api_key', value.strip())
        elif action == 1:
            ADDON.setSetting('tmdb_api_key', '')
        return
    helper = xbmcaddon.Addon('plugin.video.tmdb.bingie.helper')
    allowed = {'language', 'artwork_quality', 'fanarttv_enfallback', 'hide_unaired_movies',
               'hide_unaired_episodes', 'flatten_seasons', 'fanarttv_lookup',
               'omdb_apikey', 'mdblist_apikey', 'fanarttv_clientkey'}
    schema = ET.parse(Path(xbmcvfs.translatePath(helper.getAddonInfo('path'))) / 'resources/settings.xml')
    items = [node for node in schema.findall('.//setting') if node.get('id') in allowed]
    while True:
        labels = [helper.getLocalizedString(int(n.get('label'))) for n in items]
        shown = [label + (': ' + display_value(helper.getSettingBool(n.get('id'))) if n.get('type') == 'boolean' else '') for label, n in zip(labels, items)]
        index = choose('Catalogs and artwork', shown)
        if index < 0:
            return
        node = items[index]
        key = node.get('id')
        if node.get('type') == 'boolean':
            helper.setSettingBool(key, not helper.getSettingBool(key))
        elif key in ('omdb_apikey', 'mdblist_apikey', 'fanarttv_clientkey'):
            action = choose(labels[index], ['Replace key (stored locally)', 'Remove key'])
            if action == 0:
                value = DIALOG.input('New API key', type=xbmcgui.INPUT_ALPHANUM,
                                     option=xbmcgui.ALPHANUM_HIDE_INPUT)
                if value.strip():
                    helper.setSetting(key, value.strip())
            elif action == 1 and DIALOG.yesno('Remove API key', 'Remove the stored key from this device?'):
                helper.setSetting(key, '')
        else:
            options = node.findall('./constraints/options/option')
            names = [helper.getLocalizedString(int(o.get('label'))) if o.get('label', '').isdigit()
                     else (o.get('label') or o.text or '') for o in options]
            selected = choose(labels[index], names)
            if selected >= 0:
                helper.setSetting(key, options[selected].text)


def home_menu():
    target = Path(xbmcvfs.translatePath(HOME))
    if not target.exists():
        DIALOG.ok('Home', 'Sign in first to prepare Home.')
        return
    tree = ET.parse(target)
    rows = list(tree.getroot())
    active = len(rows)
    # Keep disabled defaults available so users can add them back later.
    existing = {r.findtext('action') for r in rows}
    rows.extend(r for r in ET.fromstring(home_xml()) if r.findtext('action') not in existing)
    selected = DIALOG.multiselect('Visible Home rows', [r.findtext('label', '') for r in rows],
                                  preselect=list(range(active)))
    if selected is None or not selected:
        return
    limit = choose('Cards per row', ['10', '20', '30', '40'])
    if limit < 0:
        return
    ordered = [rows[i] for i in selected]
    while True:
        move = choose('Home order', ['Save changes', 'Cancel'] + [r.findtext('label', '') for r in ordered])
        if move < 0 or move == 1:
            return
        if move == 0:
            break
        move -= 2
        position = choose('New position', [str(i + 1) for i in range(len(ordered))])
        if position >= 0:
            ordered.insert(position, ordered.pop(move))
    root = ET.Element('shortcuts')
    for row in ordered:
        update_row_limit(row, [10, 20, 30, 40][limit])
        root.append(row)
    replace_backed_up(target, ET.tostring(root, encoding='utf-8', xml_declaration=True), PROFILE / 'setup-backup')
    xbmc.executebuiltin('ReloadSkin()')


def appearance_menu():
    while True:
        state = [xbmc.getCondVisibility('Skin.HasSetting(' + key + ')') for key, _ in APPEARANCE]
        index = choose('Appearance', [label + ': ' + display_value(value) for (_, label), value in zip(APPEARANCE, state)])
        if index < 0:
            return
        key = APPEARANCE[index][0]
        xbmc.executebuiltin(('Skin.Reset(' if state[index] else 'Skin.SetBool(') + key + ')')


def reset_account():
    if xbmc.Player().isPlaying():
        DIALOG.ok('Reset', 'Stop playback before resetting.')
        return
    if not DIALOG.yesno('Reset StremioELEC', 'Remove this device login and imported data, restore default Home and return to QR sign-in? Your online account, network and Bluetooth stay unchanged.'):
        return
    # Restore Home before removing credentials; failed setup must not log out.
    prepare(PROFILE, xbmcvfs.translatePath(ADDON.getAddonInfo('path')), force_home=True)
    for folder in ('', 'streams', 'playback', 'subtitle-results', 'setup'):
        Store(PROFILE / folder).forget()
    for flag in ('StremioOnboardingDone', 'StremioHomeDefaults', 'BingieFirstStartupDone', 'BingieSecondStartupDone'):
        xbmc.executebuiltin('Skin.Reset(' + flag + ')')
    xbmc.executebuiltin('ReplaceWindow(1102)')


def account_menu():
    index = choose('Stremio account', ['Connect with QR code', 'Refresh addons', 'Refresh library', 'Connected addons'])
    if index == 0:
        xbmc.executebuiltin('ActivateWindow(1102)')
    elif index in (1, 2):
        xbmc.executebuiltin('RunPlugin(plugin://plugin.video.stremioelec/?action=' + ['sync', 'sync_library'][index - 1] + ')')
    elif index == 3:
        providers = Store(PROFILE).load().get('addons', [])
        DIALOG.ok('Connected Stremio addons', '\n'.join(p.get('manifest', {}).get('name', 'Stremio addon') for p in providers) or 'No addons imported.')


def run(section):
    if section == 'account':
        account_menu()
    elif section == 'home':
        index = choose('Home and appearance', ['Choose and order Home rows', 'Appearance'])
        if index == 0:
            home_menu()
        elif index == 1:
            appearance_menu()
    elif section == 'catalogs':
        helper_menu()
    elif section == 'audio':
        kodi_menu('Audio', [('audiooutput.audiodevice', 'Output device'), ('audiooutput.channels', 'Channels'), ('locale.audiolanguage', 'Preferred language'), ('audiooutput.passthrough', 'Passthrough'), ('audiooutput.passthroughdevice', 'Passthrough device'), ('audiooutput.ac3passthrough', 'Dolby Digital capable receiver'), ('audiooutput.eac3passthrough', 'Dolby Digital Plus capable receiver'), ('audiooutput.dtspassthrough', 'DTS capable receiver'), ('audiooutput.truehdpassthrough', 'TrueHD capable receiver'), ('audiooutput.dtshdpassthrough', 'DTS-HD capable receiver')])
    elif section == 'video':
        kodi_menu('Video and display', [('videoscreen.resolution', 'Resolution'), ('videoscreen.screenmode', 'Display mode'), ('videoplayer.adjustrefreshrate', 'Match frame rate'), ('videoplayer.usedisplayasclock', 'Sync playback to display'), ('videoplayer.usevtb', 'VideoToolbox hardware decoding'), ('videoplayer.usemediacodec', 'MediaCodec hardware decoding'), ('videoplayer.usemediacodecsurface', 'MediaCodec surface'), ('videoplayer.usevaapi', 'VAAPI hardware decoding'), ('videoplayer.usedxva2', 'DXVA hardware decoding')])
    elif section == 'subtitles':
        kodi_menu('Subtitles', [('locale.subtitlelanguage', 'Preferred language'), ('subtitles.languages', 'Download languages'), ('subtitles.downloadfirst', 'Automatically download first subtitle'), ('subtitles.fontsize', 'Text size'), ('subtitles.fontname', 'Font'), ('subtitles.style', 'Text style'), ('subtitles.colorpick', 'Text color'), ('subtitles.align', 'Position'), ('subtitles.backgroundtype', 'Background style'), ('subtitles.bordercolorpick', 'Border color'), ('subtitles.overridestyles', 'Override subtitle styles')])
    elif section == 'system':
        index = choose('System', ['System information', 'Updates', 'Restart', 'Power off'])
        if index == 0:
            DIALOG.ok('StremioELEC', 'Kodi engine: ' + xbmc.getInfoLabel('System.BuildVersion') + '\nIP: ' + xbmc.getInfoLabel('Network.IPAddress'))
        elif index == 1:
            if xbmc.getCondVisibility('System.HasAddon(service.stremioelec.updates)'):
                xbmc.executebuiltin('RunScript(special://xbmc/addons/service.stremioelec.updates/ui.py)')
            else:
                DIALOG.ok('StremioELEC updates', 'Updates are available on the StremioELEC OS image. This development runtime has no system updater.')
        elif index > 1 and DIALOG.yesno('StremioELEC', 'This affects the whole device. Continue?'):
            xbmc.executebuiltin('Reboot' if index == 2 else 'Powerdown')
    elif section == 'maintenance':
        index = choose('Maintenance', ['Restore default Home (10 rows)', 'Reset login and Home / return to welcome'])
        if index == 0 and DIALOG.yesno('Restore Home', 'Replace your Home rows with the default ten rows?'):
            prepare(PROFILE, xbmcvfs.translatePath(ADDON.getAddonInfo('path')), force_home=True)
            xbmc.executebuiltin('ReloadSkin()')
        elif index == 1:
            reset_account()
    elif section == 'about':
        DIALOG.ok('About StremioELEC', 'StremioELEC test build\nPowered by Kodi, Bingie skin and TMDb Bingie Helper.\nOriginal component licences and credits remain included with their source.\nOS updates require our OS image. Music, Live TV and Weather integrations are not yet installed.')


if __name__ == '__main__':
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else 'account')
    except Exception:
        DIALOG.ok('StremioELEC', 'The change could not be completed. Your current setup has been kept where possible. Please retry.')
