"""TV-friendly controls for the two independent StremioELEC channels."""
import xbmc
import xbmcgui
from engine import device


def main():
    dialog = xbmcgui.Dialog()
    try:
        updater = device()
    except RuntimeError as error:
        dialog.ok('StremioELEC updates', str(error))
        return
    while True:
        state = updater.state()
        choice = dialog.select('StremioELEC updates', [
            'Automatic system downloads: ' + ('ON' if state['auto_os'] else 'OFF'),
            'Automatic skin and bridge downloads: ' + ('ON' if state['auto_addons'] else 'OFF'),
            'Check and download updates',
            'Install downloaded updates and restart',
        ])
        if choice < 0:
            return
        try:
            with updater.locked():
                if choice in (0, 1):
                    updater.toggle(('auto_os', 'auto_addons')[choice])
                elif choice == 2:
                    candidates = updater.check()
                    if not candidates:
                        dialog.ok('StremioELEC', 'No newer approved updates are available.')
                    for kind, entry in candidates.items():
                        if updater.ready().get(kind) == entry:
                            continue
                        if dialog.yesno('StremioELEC', 'Download ' + kind + ' ' + entry['version'] + '? No restart will happen yet.'):
                            progress = xbmcgui.DialogProgress()
                            progress.create('StremioELEC', 'Downloading and verifying ' + kind + '…')
                            try:
                                updater.fetch(entry, cancelled=progress.iscanceled)
                            finally:
                                progress.close()
                            dialog.ok('StremioELEC', 'Verified download ready. Choose Install when you are ready to restart.')
                else:
                    if xbmc.Player().isPlaying():
                        dialog.ok('StremioELEC', 'Stop playback before installing updates.')
                        continue
                    ready = updater.ready()
                    if not ready:
                        dialog.ok('StremioELEC', 'No downloaded updates are ready.')
                        continue
                    # Separate OS and addon upgrades: a dependency/major migration
                    # must not apply a pending addon bundle against an older OS.
                    kinds = list(ready)
                    selected = dialog.select('Select update to install', [k + ': ' + ready[k]['version'] for k in kinds])
                    if selected < 0:
                        continue
                    entry = ready[kinds[selected]]
                    if dialog.yesno('Install update?', 'Install ' + entry['kind'] + ' ' + entry['version'] + ' and restart now? Your account and settings are retained.'):
                        updater.stage(entry)
                        xbmc.executebuiltin('Reboot')
                        return
        except Exception as error:
            dialog.ok('StremioELEC updates', 'Update not installed: ' + str(error))


if __name__ == '__main__':
    main()
