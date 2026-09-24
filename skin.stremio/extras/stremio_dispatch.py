"""Resolve the bridge through Kodi, for both built-in and user installations."""
from pathlib import Path
import runpy
import sys
import xbmcaddon
import xbmcgui
import xbmcvfs

SCRIPTS = {'onboarding.py', 'settings_ui.py', 'trailer_player.py', 'library_ui.py', 'library_filters.py', 'settings_guard.py', 'addons_ui.py'}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SCRIPTS:
        raise ValueError('Unknown Stremio action')
    addon = xbmcaddon.Addon('plugin.video.stremioelec')
    system_core = Path('/usr/lib/stremioelec/plugin.video.stremioelec')
    addon_path = Path(xbmcvfs.translatePath(addon.getAddonInfo('path')))
    directory = system_core if system_core.is_dir() else addon_path
    script = directory / sys.argv[1]
    if not script.is_file():
        xbmcgui.Dialog().ok('StremioELEC', 'The Stremio component is incomplete. Please install a verified update.')
        return
    previous_args, previous_path = sys.argv[:], sys.path[:]
    try:
        sys.argv = [str(script)] + sys.argv[2:]
        sys.path.insert(0, str(directory))
        runpy.run_path(str(script), run_name='__main__')
    finally:
        sys.argv, sys.path = previous_args, previous_path


if __name__ == '__main__':
    main()
