"""TV-friendly Stremio addon manager. Kodi addons remain internal."""
import sys
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from account import Store, pull_addons
from addons_core import (active_addons, configure_url, configuration_state,
                         install_local, push_account, remove_local, set_enabled)

WINDOW_ID = 1196
ADDON = xbmcaddon.Addon('plugin.video.stremioelec')
STORE = Store(Path(xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))))


def publish(status=None):
    state = STORE.load()
    total = len(state.get('addons', []))
    enabled = len(active_addons(state))
    window = xbmcgui.Window(WINDOW_ID)
    window.setProperty('StremioAddons.Count', str(total))
    window.setProperty('StremioAddons.Enabled', str(enabled))
    window.setProperty('StremioAddons.Status', status or
                       ('Connected to Stremio account' if state.get('token') else 'Local device only'))


def sync_account(dialog):
    state = STORE.load()
    token = state.get('token')
    if not token:
        dialog.ok('Stremio Addons', 'Connect your Stremio account first.')
        return
    addons, skipped = pull_addons(token)
    state['addons'] = addons
    # Disabled-on-this-device state intentionally survives account sync.
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
    manifest = descriptor['manifest']
    config = configuration_state(manifest)
    if config['required']:
        dialog.ok('Configure ' + manifest.get('name', 'addon'),
                  'This addon requires configuration first. Open this address on your phone/computer, finish setup, then install the configured manifest URL:\n\n' +
                  configure_url(descriptor['transportUrl']))
        return
    if not dialog.yesno('Install Stremio addon?',
            manifest.get('name', 'Stremio addon') + '\n\n' +
            str(manifest.get('description', ''))[:500] +
            '\n\nInstall on this StremioELEC device?'):
        return
    STORE.save(state)
    if state.get('token') and dialog.yesno('Sync to Stremio account?',
            'Also install this addon in your Stremio account so it appears on your other Stremio devices?'):
        try:
            push_account(state['token'], state['addons'])
        except Exception:
            dialog.ok('Stremio Addons', 'Installed on this device, but the Stremio account update failed.')
    publish('Installed ' + manifest.get('name', 'addon'))


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
    if state.get('token'):
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
        dialog.ok('Configure ' + manifest.get('name', 'addon'),
                  'Open this address on your phone/computer. After configuration, install the resulting manifest URL in StremioELEC:\n\n' +
                  configure_url(item['transportUrl']))
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
        remote = [row for row in state.get('addons', []) if row.get('id') != identity]
        try:
            push_account(state['token'], remote)
        except Exception:
            dialog.ok('Stremio Addons', 'Stremio account was not changed.')
            return
        state['addons'] = remote
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
    else:
        dialog.ok('Stremio Addons', 'Unknown addon manager action.')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'open')
