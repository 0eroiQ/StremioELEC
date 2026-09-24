"""First-run prompt for StremioELEC portable mode."""
import xbmc
import xbmcgui
from portable_mode import enable, load, save

monitor = xbmc.Monitor()
if not monitor.waitForAbort(2):
    state = load()
    if not state.get('initialized'):
        dialog = xbmcgui.Dialog()
        choice = dialog.yesno('StremioELEC for Kodi',
            'Enable StremioELEC Mode now? Kodi remains the media engine underneath. '
            'You can restore your previous Kodi skin later from StremioELEC Maintenance.')
        state['initialized'] = True
        save(state)
        if choice:
            try:
                enable()
            except Exception:
                dialog.ok('StremioELEC for Kodi',
                          'StremioELEC Mode could not be enabled. Your existing Kodi interface is unchanged.')

while not monitor.waitForAbort(10):
    pass
