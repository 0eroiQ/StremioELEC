"""Start the StremioELEC Welcome flow after portable installation."""
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
            xbmcgui.Dialog().ok('StremioELEC', 'StremioELEC could not start. Your previous interface was kept where possible.')

while not monitor.waitForAbort(10):
    pass
