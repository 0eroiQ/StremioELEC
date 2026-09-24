"""Expose account subtitle providers in Kodi's standard subtitle download dialog."""
import hashlib
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from account import Store
from subtitles import collect_subtitles, download, preferences


def run():
    handle = int(sys.argv[1])
    params = dict(parse_qsl(sys.argv[2].lstrip('?')))
    addon = xbmcaddon.Addon('plugin.video.stremioelec')
    profile = Path(xbmcvfs.translatePath(addon.getAddonInfo('profile')))
    context = Store(profile / 'playback').load()
    player = xbmc.Player()
    try:
        current_hash = hashlib.sha256(player.getPlayingFile().encode()).hexdigest()
        if not player.isPlayingVideo() or context.get('url_hash') != current_hash:
            raise ValueError('No matching Stremio playback')
        cache = Store(profile / 'subtitle-results')
        if params.get('action') == 'download':
            saved = cache.load()
            if saved.get('url_hash') != current_hash or time.time() - saved.get('created', 0) > 3600:
                raise ValueError('Expired results')
            entry = saved.get('entries', {}).get(params.get('key'))
            if not entry:
                raise ValueError('Unknown result')
            path = download(entry, profile / 'subtitles')
            xbmcplugin.addDirectoryItem(handle, path, xbmcgui.ListItem(label=path), False)
        else:
            allowed, preferred, _ = preferences()
            entries = collect_subtitles(Store(profile).load().get('addons', []), context['kind'], context['id'],
                                        allowed, preferred, context.get('subtitles'), context.get('filename', ''))
            saved = {}
            for entry in entries:
                key = secrets.token_hex(16)
                saved[key] = entry
                label = xbmc.convertLanguage(entry['lang'], xbmc.ENGLISH_NAME) or entry['lang']
                item = xbmcgui.ListItem(label=label, label2=entry['label'])
                item.setArt({'thumb': xbmc.convertLanguage(entry['lang'], xbmc.ISO_639_1)})
                item.setProperty('sync', 'false')
                item.setProperty('hearing_imp', 'false')
                xbmcplugin.addDirectoryItem(handle, sys.argv[0] + '?' + urlencode({'action': 'download', 'key': key}), item, False)
            cache.save({'created': time.time(), 'url_hash': current_hash, 'entries': saved})
        xbmcplugin.endOfDirectory(handle)
    except Exception:
        # Never expose signed provider URLs or account secrets in Kodi logs.
        xbmcgui.Dialog().notification('Stremio subtitles', 'No matching subtitles available. Start playback through StremioELEC and check Kodi languages.')
        xbmcplugin.endOfDirectory(handle, succeeded=False)


if __name__ == '__main__':
    run()
