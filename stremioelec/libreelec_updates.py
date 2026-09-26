"""StremioELEC update module for the LibreELEC system-settings shell.

This intentionally replaces LibreELEC's stock updater in the StremioELEC image.
Network, Bluetooth, services, backups and other LibreELEC settings stay upstream.
Only the update transport is replaced so the box can never download a stock
LibreELEC SYSTEM over StremioELEC.
"""
import importlib.util
from pathlib import Path

import xbmc
import xbmcgui

import log
import modules
import oe

_ENGINE = None
ENGINE_PATH = Path('/usr/share/kodi/addons/service.stremioelec.updates/engine.py')


def update_engine():
    global _ENGINE
    if _ENGINE is None:
        if not ENGINE_PATH.is_file():
            raise RuntimeError('StremioELEC update engine is not installed')
        spec = importlib.util.spec_from_file_location('stremioelec_update_engine', ENGINE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError('StremioELEC update engine could not be loaded')
        _ENGINE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ENGINE)
    return _ENGINE


class updates(modules.Module):
    """LibreELEC settings module backed only by the StremioELEC update feed."""

    ENABLED = False
    menu = {'2': {
        'name': 32005,
        'menuLoader': 'load_menu',
        'listTyp': 'list',
        'InfoText': 707,
    }}

    @log.log_function()
    def __init__(self, oeMain):
        super().__init__()
        self.struct = {
            'update': {
                'order': 1,
                'name': 32013,
                'settings': {
                    'Version': {
                        'order': 1,
                        'name': 'Current StremioELEC version',
                        'value': '',
                        'action': 'show_version',
                        'type': 'button',
                    },
                    'Channel': {
                        'order': 2,
                        'name': 'Update channel: Stable',
                        'value': '',
                        'action': 'show_channel',
                        'type': 'button',
                    },
                    'AutoSystem': {
                        'order': 3,
                        'name': 'Automatic system downloads',
                        'value': '0',
                        'action': 'toggle_system',
                        'type': 'bool',
                    },
                    'AutoInterface': {
                        'order': 4,
                        'name': 'Automatic interface downloads',
                        'value': '0',
                        'action': 'toggle_interface',
                        'type': 'bool',
                    },
                    'Check': {
                        'order': 5,
                        'name': 'Check and download updates',
                        'value': '',
                        'action': 'check_updates',
                        'type': 'button',
                    },
                    'Install': {
                        'order': 6,
                        'name': 'Install downloaded update and restart',
                        'value': '',
                        'action': 'install_update',
                        'type': 'button',
                    },
                },
            },
        }

    def _updater(self):
        return update_engine().device()

    @log.log_function()
    def start_service(self):
        # The dedicated service.stremioelec.updates service performs bounded,
        # idle background checks. Never start LibreELEC's stock update thread.
        return

    @log.log_function()
    def stop_service(self):
        return

    @log.log_function()
    def do_init(self):
        self.load_values()

    @log.log_function()
    def exit(self):
        return

    @log.log_function()
    def load_values(self):
        try:
            updater = self._updater()
            state = updater.state()
            version = str(updater.release.get('version', 'unknown'))
            self.struct['update']['settings']['Version']['name'] = 'Current StremioELEC version: ' + version
            self.struct['update']['settings']['AutoSystem']['value'] = '1' if state['auto_os'] else '0'
            self.struct['update']['settings']['AutoInterface']['value'] = '1' if state['auto_addons'] else '0'
            ready = updater.ready()
            if ready:
                labels = ', '.join(kind + ' ' + entry['version'] for kind, entry in sorted(ready.items()))
                self.struct['update']['settings']['Install']['name'] = 'Install downloaded update: ' + labels
            else:
                self.struct['update']['settings']['Install']['name'] = 'Install downloaded update and restart'
        except Exception:
            self.struct['update']['settings']['Version']['name'] = 'Current StremioELEC version: unavailable'
            self.struct['update']['settings']['AutoSystem']['value'] = '0'
            self.struct['update']['settings']['AutoInterface']['value'] = '0'

    @log.log_function()
    def load_menu(self, focusItem):
        self.load_values()
        oe.winOeMain.build_menu(self.struct)

    def _refresh(self):
        self.load_values()

    @log.log_function()
    def show_version(self, listItem=None):
        try:
            updater = self._updater()
            xbmcgui.Dialog().ok(
                'StremioELEC System',
                'StremioELEC: ' + str(updater.release.get('version', 'unknown')) +
                '\nKodi: ' + xbmc.getInfoLabel('System.BuildVersion') +
                '\nTarget: ' + str(updater.release.get('target', 'unknown')))
        except Exception as error:
            xbmcgui.Dialog().ok('StremioELEC System', str(error))

    @log.log_function()
    def show_channel(self, listItem=None):
        xbmcgui.Dialog().ok(
            'StremioELEC Updates',
            'Stable channel\n\nOnly reviewed StremioELEC releases from the fixed project update feed are accepted. '
            'Stock LibreELEC update servers and custom update URLs are disabled.')

    @log.log_function()
    def toggle_system(self, listItem=None):
        try:
            updater = self._updater()
            with updater.locked():
                updater.toggle('auto_os')
            self._refresh()
        except Exception as error:
            xbmcgui.Dialog().ok('StremioELEC Updates', 'Setting not changed: ' + str(error))

    @log.log_function()
    def toggle_interface(self, listItem=None):
        try:
            updater = self._updater()
            with updater.locked():
                updater.toggle('auto_addons')
            self._refresh()
        except Exception as error:
            xbmcgui.Dialog().ok('StremioELEC Updates', 'Setting not changed: ' + str(error))

    @log.log_function()
    def check_updates(self, listItem=None):
        dialog = xbmcgui.Dialog()
        try:
            updater = self._updater()
            with updater.locked():
                candidates = updater.check()
                if not candidates:
                    dialog.ok('StremioELEC Updates', 'No newer approved updates are available.')
                    self._refresh()
                    return
                ready = updater.ready()
                for kind, entry in candidates.items():
                    if ready.get(kind) == entry:
                        continue
                    if not dialog.yesno(
                            'StremioELEC Updates',
                            'Download ' + kind + ' ' + entry['version'] +
                            '?\n\nThe package will be verified. Nothing restarts yet.'):
                        continue
                    progress = xbmcgui.DialogProgress()
                    progress.create('StremioELEC Updates', 'Downloading and verifying ' + kind + '…')
                    try:
                        updater.fetch(entry, cancelled=progress.iscanceled)
                    finally:
                        progress.close()
                self._refresh()
        except Exception as error:
            dialog.ok('StremioELEC Updates', 'Update check/download failed: ' + str(error))

    @log.log_function()
    def install_update(self, listItem=None):
        dialog = xbmcgui.Dialog()
        if xbmc.Player().isPlaying():
            dialog.ok('StremioELEC Updates', 'Stop playback before installing updates.')
            return
        try:
            updater = self._updater()
            with updater.locked():
                ready = updater.ready()
                if not ready:
                    dialog.ok('StremioELEC Updates', 'No verified downloaded updates are ready.')
                    return
                kinds = list(sorted(ready))
                selected = dialog.select(
                    'Select update to install',
                    [kind + ': ' + ready[kind]['version'] for kind in kinds])
                if selected < 0:
                    return
                entry = ready[kinds[selected]]
                if not dialog.yesno(
                        'Install StremioELEC update?',
                        'Install ' + entry['kind'] + ' ' + entry['version'] +
                        ' and restart now?\n\nYour Stremio account and /storage settings are retained.'):
                    return
                updater.stage(entry)
            if hasattr(oe, 'winOeMain') and oe.winOeMain.visible:
                oe.winOeMain.close()
            xbmc.executebuiltin('Reboot')
        except Exception as error:
            dialog.ok('StremioELEC Updates', 'Update not installed: ' + str(error))
