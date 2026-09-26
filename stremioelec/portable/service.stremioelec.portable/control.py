"""Manual optional-skin control for StremioELEC on Kodi."""
import sys
import xbmcgui
from portable_mode import enable, menu, restore

try:
    action = sys.argv[1] if len(sys.argv) > 1 else 'menu'
    if action == 'enable':
        enable()
    elif action == 'restore':
        restore()
    else:
        menu()
except Exception:
    xbmcgui.Dialog().ok('StremioELEC for Kodi',
                        'The interface change could not be completed. Your Kodi installation was not removed.')
