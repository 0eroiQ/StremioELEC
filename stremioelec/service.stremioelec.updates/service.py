"""Download-only idle update checks; installation always needs confirmation."""
import time
import xbmc
import xbmcgui
from engine import device


def main():
    try:
        updater = device()
    except RuntimeError:
        return  # Not a StremioELEC image (e.g. the macOS development runtime).
    monitor = xbmc.Monitor()
    while not monitor.waitForAbort(60):
        state = updater.state()
        if (xbmc.Player().isPlaying() or not (state['auto_os'] or state['auto_addons'])
                or time.time() - state.get('last_attempt', 0) < 6 * 3600):
            continue
        try:
            with updater.locked():
                updater.save(last_attempt=int(time.time()))
                candidates = updater.check()
                ready = updater.ready()
                downloaded = False
                for kind, entry in candidates.items():
                    if not state['auto_' + kind] or ready.get(kind) == entry:
                        continue
                    updater.fetch(entry, cancelled=lambda: monitor.abortRequested() or xbmc.Player().isPlaying())
                    downloaded = True
                if downloaded:
                    xbmcgui.Dialog().notification('StremioELEC', 'Update downloaded. Open Settings > System > Updates to install.', time=8000)
        except RuntimeError:
            pass  # Another operation or a cancelled download; retry later.
        except Exception:
            # No account data/URLs in logs or notifications.
            xbmc.log('StremioELEC update check failed; installed system unchanged.', xbmc.LOGWARNING)


if __name__ == '__main__':
    main()
