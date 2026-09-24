"""TV-friendly Stremio addon manager. Kodi addons remain internal."""
import html
import re
import sys
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from account import Store, pull_addons
from addons_core import (account_addons, active_addons, community_catalog, configure_url,
                         configuration_state, filter_community, install_descriptor_local,
                         install_local, mark_account, merge_account, push_account,
                         remove_local, set_enabled)

WINDOW_ID = 1196
CONFIG_WINDOW_ID = 1195
ADDON = xbmcaddon.Addon('plugin.video.stremioelec')
PROFILE = Path(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')))
STORE = Store(PROFILE)


def publish(status=None):
    state = STORE.load()
    total = len(state.get('addons', []))
    enabled = len(active_addons(state))
    window = xbmcgui.Window(WINDOW_ID)
    window.setProperty('StremioAddons.Count', str(total))
    window.setProperty('StremioAddons.Enabled', str(enabled))
    window.setProperty('StremioAddons.Status', status or
                       ('Connected to Stremio account' if state.get('token') else 'Local device only'))




def plain(value, limit=900):
    value = re.sub(r'<[^>]*>', ' ', str(value or ''))
    value = html.unescape(value)
    return re.sub(r'\s+', ' ', value).strip()[:limit]


def finish_install(state, descriptor, dialog):
    manifest = descriptor['manifest']
    config = configuration_state(manifest)
    if config['required']:
        show_config(manifest, descriptor['transportUrl'], dialog)
        return False
    if not dialog.yesno('Install Stremio addon?',
            manifest.get('name', 'Stremio addon') + '\n\n' +
            plain(manifest.get('description', ''), 500) +
            '\n\nInstall on this StremioELEC device?'):
        return False
    STORE.save(state)
    if state.get('token') and dialog.yesno('Sync to Stremio account?',
            'Also install this addon in your Stremio account so it appears on your other Stremio devices?'):
        try:
            remote = account_addons(state) + [descriptor]
            push_account(state['token'], remote)
            mark_account(state, descriptor['id'], True)
            STORE.save(state)
        except Exception:
            dialog.ok('Stremio Addons', 'Installed on this device, but the Stremio account update failed.')
    publish('Installed ' + manifest.get('name', 'addon'))
    return True


def community_addons(dialog):
    choices = [
        ('all', 'Browse all'),
        ('search', 'Search'),
        ('movies', 'Movies & Series'),
        ('streams', 'Streams'),
        ('subtitles', 'Subtitles'),
        ('catalogs', 'Catalogs'),
        ('live', 'Live TV & Channels'),
    ]
    selection = dialog.select('Community Addons', [label for _, label in choices])
    if selection < 0:
        return
    category = choices[selection][0]
    query = ''
    if category == 'search':
        query = dialog.input('Search Community Addons', type=xbmcgui.INPUT_ALPHANUM).strip()
        if not query:
            return
        category = 'all'
    progress = xbmcgui.DialogProgress()
    progress.create('Community Addons', 'Loading the Stremio Community catalog…')
    try:
        rows = filter_community(community_catalog(), category, query)
    except Exception:
        dialog.ok('Community Addons', 'The Stremio Community catalog is unavailable. Try again later.')
        return
    finally:
        progress.close()
    if not rows:
        dialog.ok('Community Addons', 'No addons match this filter.')
        return

    state = STORE.load()
    installed_ids = {item.get('manifest', {}).get('id') for item in state.get('addons', [])}
    selected = dialog.select('Community Addons', [
        ('Installed · ' if row['manifest'].get('id') in installed_ids else '') +
        row['manifest'].get('name', 'Stremio addon')
        for row in rows
    ])
    if selected < 0:
        return
    row = rows[selected]
    manifest = row['manifest']
    config = configuration_state(manifest)
    resources = []
    for resource in manifest.get('resources', []):
        name = resource.get('name') if isinstance(resource, dict) else resource
        if isinstance(name, str) and name not in resources:
            resources.append(name)
    installed = manifest.get('id') in installed_ids

    actions = []
    if config['required']:
        actions.append(('configure', 'Configure'))
    else:
        actions.append(('install', 'Replace / install' if installed else 'Install'))
        if config['configurable']:
            actions.append(('configure', 'Configure'))
    actions.append(('info', 'Addon information'))
    action = dialog.select(manifest.get('name', 'Stremio addon'), [label for _, label in actions])
    if action < 0:
        return
    action = actions[action][0]
    if action == 'configure':
        show_config(manifest, row['transportUrl'], dialog)
        return
    if action == 'info':
        dialog.ok(manifest.get('name', 'Stremio addon'),
                  'Version: ' + str(manifest.get('version', '')) +
                  '\nTypes: ' + ', '.join(str(v) for v in manifest.get('types', [])) +
                  '\nResources: ' + ', '.join(resources) +
                  '\n\n' + plain(manifest.get('description', '')))
        return
    try:
        descriptor = install_descriptor_local(state, row['transportUrl'], manifest)
    except Exception:
        dialog.ok('Community Addons', 'This catalog entry is not a supported Stremio addon.')
        return
    finish_install(state, descriptor, dialog)


def show_config(manifest, transport_url, dialog):
    url = configure_url(transport_url)
    try:
        import qrcode
        PROFILE.mkdir(parents=True, exist_ok=True)
        path = PROFILE / 'addon-configure-qr.png'
        qrcode.make(url).save(str(path))
        window = xbmcgui.Window(CONFIG_WINDOW_ID)
        window.setProperty('StremioAddonConfig.Name', manifest.get('name', 'Stremio addon'))
        window.setProperty('StremioAddonConfig.URL', url)
        window.setProperty('StremioAddonConfig.QR', str(path))
        xbmc.executebuiltin('ActivateWindow(' + str(CONFIG_WINDOW_ID) + ')')
    except Exception:
        dialog.ok('Configure ' + manifest.get('name', 'addon'),
                  'Open this address on your phone/computer, finish setup, then install the configured manifest URL:\n\n' + url)


def sync_account(dialog):
    state = STORE.load()
    token = state.get('token')
    if not token:
        dialog.ok('Stremio Addons', 'Connect your Stremio account first.')
        return
    addons, skipped = pull_addons(token)
    state['addons'] = merge_account(state, addons)
    # Disabled-on-this-device state and local-only installs survive account sync.
    STORE.save(state)
    publish('Synced {} addons from Stremio'.format(len(addons)))
    dialog.notification('Stremio Addons', '{} addons synced; {} unsupported skipped.'.format(len(addons), skipped))


def install_url(dialog):
    value = dialog.input('Stremio addon manifest URL', type=xbmcgui.INPUT_ALPHANUM)
    if not value.strip():
        return
    state = STORE.load()
    try:
        descriptor = install_local(state, value.strip())
    except Exception:
        dialog.ok('Stremio Addons', 'Unable to read this manifest. Use an HTTPS URL ending in /manifest.json.')
        return
    finish_install(state, descriptor, dialog)


def addon_actions(dialog):
    state = STORE.load()
    addons = list(state.get('addons', []))
    if not addons:
        dialog.ok('My Addons', 'No Stremio addons are installed on this device.')
        return
    disabled = set(state.get('disabledAddons', []))
    labels = []
    for item in addons:
        name = item.get('manifest', {}).get('name', 'Stremio addon')
        labels.append(('Disabled · ' if item.get('id') in disabled else '') + name)
    selected = dialog.select('My Stremio Addons', labels)
    if selected < 0:
        return
    item = addons[selected]
    identity = item['id']
    manifest = item.get('manifest', {})
    enabled = identity not in disabled
    config = configuration_state(manifest)
    actions = [('disable' if enabled else 'enable', 'Disable on this device' if enabled else 'Enable on this device')]
    if config['configurable']:
        actions.append(('configure', 'Configure'))
    actions += [('remove_local', 'Remove from this device')]
    if state.get('token') and item.get('account') is True:
        actions.append(('remove_account', 'Remove from Stremio account'))
    actions.append(('info', 'Addon information'))
    choice = dialog.select(manifest.get('name', 'Stremio addon'), [label for _, label in actions])
    if choice < 0:
        return
    action = actions[choice][0]
    if action in ('enable', 'disable'):
        set_enabled(state, identity, action == 'enable')
        STORE.save(state)
        publish(('Enabled ' if action == 'enable' else 'Disabled ') + manifest.get('name', 'addon'))
    elif action == 'configure':
        show_config(manifest, item['transportUrl'], dialog)
    elif action == 'remove_local':
        if dialog.yesno('Remove from this device?',
                'This does not change your Stremio account or other devices.'):
            remove_local(state, identity)
            STORE.save(state)
            publish('Removed from this device')
    elif action == 'remove_account':
        if not dialog.yesno('Remove from Stremio account?',
                'This changes your Stremio addon collection and can affect your other Stremio devices. Continue?'):
            return
        remote = [row for row in account_addons(state) if row.get('id') != identity]
        try:
            push_account(state['token'], remote)
        except Exception:
            dialog.ok('Stremio Addons', 'Stremio account was not changed.')
            return
        state['addons'] = merge_account(state, remote)
        state['disabledAddons'] = sorted(set(state.get('disabledAddons', [])) - {identity})
        STORE.save(state)
        publish('Removed from Stremio account')
    else:
        resources = manifest.get('resources', [])
        dialog.ok(manifest.get('name', 'Stremio addon'),
                  'Version: ' + str(manifest.get('version', '')) +
                  '\nResources: ' + ', '.join(str(r.get('name') if isinstance(r, dict) else r) for r in resources) +
                  '\n\n' + str(manifest.get('description', ''))[:900])


def main(action='open'):
    dialog = xbmcgui.Dialog()
    if action == 'open':
        xbmc.executebuiltin('ActivateWindow(' + str(WINDOW_ID) + ')')
    elif action == 'refresh':
        publish()
    elif action == 'my':
        addon_actions(dialog)
        publish()
    elif action == 'install':
        install_url(dialog)
    elif action == 'sync':
        sync_account(dialog)
    elif action == 'community':
        community_addons(dialog)
        publish()
    else:
        dialog.ok('Stremio Addons', 'Unknown addon manager action.')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'open')
