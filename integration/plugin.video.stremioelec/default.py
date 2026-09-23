"""Kodi entry point. No account writes, library mutations or torrent engine."""
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit

import xbmcaddon
import xbmcgui
import xbmcplugin

from protocol import base_url, catalogs, fetch, resource_url

HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
ADDON = xbmcaddon.Addon()
MANIFEST = ADDON.getSetting('manifest').strip()


def route(**params):
    return BASE + '?' + urlencode(params)


def item(meta):
    entry = xbmcgui.ListItem(label=meta.get('name') or meta.get('id', ''))
    info = entry.getVideoInfoTag()
    info.setTitle(meta.get('name', ''))
    info.setPlot(meta.get('description', ''))
    info.setMediaType('tvshow' if meta.get('type') == 'series' else 'movie')
    entry.setArt({key: value for key, value in {
        'poster': meta.get('poster'), 'thumb': meta.get('background') or meta.get('poster'),
        'fanart': meta.get('background'), 'clearlogo': meta.get('logo')
    }.items() if isinstance(value, str)})
    return entry


def run(params):
    base_url(MANIFEST)
    action = params.get('action', 'root')
    if action == 'root':
        for catalog in catalogs(fetch(MANIFEST)):
            label = catalog.get('name', catalog['id']) + ' · ' + catalog['type']
            xbmcplugin.addDirectoryItem(HANDLE, route(action='catalog', kind=catalog['type'],
                id=catalog['id']), xbmcgui.ListItem(label=label), True)
    elif action == 'catalog':
        kind = params['kind']
        xbmcplugin.setContent(HANDLE, 'tvshows' if kind == 'series' else 'movies')
        response = fetch(resource_url(MANIFEST, 'catalog', kind, params['id']))
        for meta in response.get('metas', []):
            if not meta.get('id'):
                continue
            xbmcplugin.addDirectoryItem(HANDLE, route(action='meta',
                kind=meta.get('type', kind), id=meta['id']), item(meta), True)
    elif action == 'meta':
        kind, identity = params['kind'], params['id']
        meta = fetch(resource_url(MANIFEST, 'meta', kind, identity)).get('meta') or {}
        videos = meta.get('videos', []) if kind == 'series' else []
        if videos:
            xbmcplugin.setContent(HANDLE, 'episodes')
            for video in videos:
                if not video.get('id'):
                    continue
                entry = xbmcgui.ListItem(label='S{} E{} · {}'.format(
                    video.get('season', '?'), video.get('episode', '?'), video.get('title', '')))
                entry.getVideoInfoTag().setMediaType('episode')
                xbmcplugin.addDirectoryItem(HANDLE, route(action='streams', kind=kind,
                    id=video['id']), entry, True)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, route(action='streams', kind=kind,
                id=identity), item(meta), True)
    elif action == 'streams':
        manifest = fetch(MANIFEST)
        supported = any((r if isinstance(r, str) else r.get('name')) == 'stream'
                        for r in manifest.get('resources', []))
        if not supported:
            xbmcgui.Dialog().ok('StremioELEC', 'This addon provides metadata only. Stream addon aggregation is not connected yet.')
        else:
            streams = fetch(resource_url(MANIFEST, 'stream', params['kind'], params['id'])).get('streams', [])
            playable = [s for s in streams if urlsplit(s.get('url', '')).scheme in ('https', 'http')
                        and not s.get('behaviorHints', {}).get('proxyHeaders')
                        and '|' not in s.get('url', '')]
            labels = [s.get('name') or s.get('title') or 'Stream {}'.format(i + 1)
                      for i, s in enumerate(playable)]
            choice = xbmcgui.Dialog().select('Select stream', labels) if labels else -1
            if choice >= 0:
                # Use a playable plugin item so Kodi owns playback resolution.
                entry = xbmcgui.ListItem(label=labels[choice])
                entry.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(HANDLE, route(action='play', url=playable[choice]['url']), entry, False)
            elif not labels:
                xbmcgui.Dialog().ok('StremioELEC', 'No supported direct HTTP stream. Torrents, external players and custom proxy headers are not supported yet.')
    elif action == 'play':
        url = params.get('url', '')
        if urlsplit(url).scheme not in ('http', 'https') or '|' in url:
            raise ValueError('Unsupported stream URL')
        xbmcplugin.setResolvedUrl(HANDLE, True, xbmcgui.ListItem(path=url))
        return
    else:
        raise ValueError('Unknown route')
    xbmcplugin.endOfDirectory(HANDLE)


if __name__ == '__main__':
    params = dict(parse_qsl(sys.argv[2].lstrip('?')))
    try:
        run(params)
    except Exception:
        # Provider URLs can contain secrets: never log exceptions/URLs here.
        xbmcgui.Dialog().ok('StremioELEC', 'Unable to load this addon response. Check the manifest setting and connection.')
        if params.get('action') == 'play':
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
