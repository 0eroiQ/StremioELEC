"""Initialize portable StremioELEC without forcing an interface change."""
import xbmc
import xbmcgui
from portable_mode import begin_onboarding, load

monitor = xbmc.Monitor()
if not monitor.waitForAbort(2):
    state = load()
    if not state.get('initialized'):
        try:
            begin_onboarding()
        except Exception:
            xbmcgui.Dialog().ok('StremioELEC for Kodi', 'StremioELEC could not initialize. Your current Kodi interface was not changed.')

while not monitor.waitForAbort(10):
    pass
