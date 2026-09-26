"""Native StremioELEC System Updates screen controller."""
import sys
import time
import xbmc
import xbmcgui
from engine import device

WINDOW_ID = 1197

def _window():
    return xbmcgui.Window(WINDOW_ID)

def _set(name, value):
    _window().setProperty('StremioUpdate.' + name, '' if value is None else str(value))

def _last_check(value):
    if not value:
        return 'Not checked yet'
    try:
        return time.strftime('%d %b %Y · %H:%M', time.localtime(int(value)))
    except Exception:
        return 'Unknown'

def publish(updater, status=None):
    state = updater.state()
    ready = updater.ready()
    _set('Version', updater.release.get('version', 'Unknown'))
    _set('Channel', 'Stable')
    _set('AutoSystem', 'ON' if state['auto_os'] else 'OFF')
    _set('AutoInterface', 'ON' if state['auto_addons'] else 'OFF')
    _set('LastCheck', _last_check(state.get('last_check')))
    labels = []
    if ready.get('os'):
        labels.append('System ' + ready['os']['version'] + ' ready')
    if ready.get('addons'):
        labels.append('Interface ' + ready['addons']['version'] + ' ready')
    _set('Ready', ' · '.join(labels) if labels else 'Nothing downloaded')
    if status is not None:
        _set('Status', status)
    elif state.get('last_error'):
        _set('Status', state['last_error'])
    elif ready:
        _set('Status', 'Verified update ready to install')
    else:
        _set('Status', 'System is running normally')

def _download_candidates(updater, dialog):
    candidates = updater.check()
    if not candidates:
        publish(updater, 'No newer approved updates are available')
        dialog.notification('StremioELEC', 'No newer approved updates are available.')
        return
    downloaded = False
    for kind, entry in candidates.items():
        if updater.ready().get(kind) == entry:
            continue
        title = 'System update' if kind == 'os' else 'Interface update'
        if not dialog.yesno(title, 'Download StremioELEC ' + entry['version'] +
                '? The package will be verified before it can be installed.'):
            continue
        progress = xbmcgui.DialogProgress()
        progress.create('StremioELEC', 'Downloading and verifying ' + title.lower() + '…')
        try:
            updater.fetch(entry, cancelled=progress.iscanceled)
            downloaded = True
        finally:
            progress.close()
    publish(updater, 'Verified update downloaded' if downloaded else 'Update check completed')
    if downloaded:
        dialog.notification('StremioELEC',
            'Verified update ready. Install when you are ready to restart.', time=7000)

def _install(updater, dialog):
    if xbmc.Player().isPlaying():
        dialog.ok('StremioELEC', 'Stop playback before installing updates.')
        return
    ready = updater.ready()
    if not ready:
        dialog.ok('StremioELEC', 'No downloaded updates are ready.')
        publish(updater)
        return
    kinds = list(ready)
    if len(kinds) == 1:
        entry = ready[kinds[0]]
    else:
        labels = [('System' if k == 'os' else 'Interface') + ': ' + ready[k]['version'] for k in kinds]
        selected = dialog.select('Select update to install', labels)
        if selected < 0:
            return
        entry = ready[kinds[selected]]
    label = 'System' if entry['kind'] == 'os' else 'Interface'
    if not dialog.yesno('Install & restart?',
            'Install ' + label + ' ' + entry['version'] +
            ' and restart now? Your Stremio account and settings are retained.'):
        return
    updater.stage(entry)
    publish(updater, 'Restarting to install ' + entry['version'])
    xbmc.executebuiltin('Reboot')

def main(action='open'):
    dialog = xbmcgui.Dialog()
    try:
        updater = device()
    except RuntimeError as error:
        dialog.ok('StremioELEC updates', str(error))
        return
    try:
        if action == 'open':
            xbmc.executebuiltin('ActivateWindow(' + str(WINDOW_ID) + ')')
        elif action == 'refresh':
            publish(updater)
        elif action in ('toggle_os', 'toggle_addons'):
            with updater.locked():
                updater.toggle('auto_os' if action == 'toggle_os' else 'auto_addons')
            publish(updater)
        elif action == 'check':
            with updater.locked():
                publish(updater, 'Checking for approved updates…')
                _download_candidates(updater, dialog)
        elif action == 'install':
            with updater.locked():
                _install(updater, dialog)
        else:
            raise ValueError('Unknown update action')
    except Exception as error:
        try:
            updater.save(last_error='Update not installed: ' + str(error))
            publish(updater)
        except Exception:
            pass
        dialog.ok('StremioELEC updates', 'Update not installed: ' + str(error))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'open')
