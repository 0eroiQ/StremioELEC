"""Kodi entry point. No account writes, library mutations or torrent engine."""
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

import xbmcaddon
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin

from protocol import base_url, catalogs, fetch, resource_url
from account import AccountError, Store, create_link, read_link, pull_addons

HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
ADDON = xbmcaddon.Addon()
MANIFEST = ADDON.getSetting('manifest').strip()
STORE = Store(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')))


def connect_account():
    if not xbmcgui.Dialog().yesno('Connect Stremio',
            'Sign in on the official Stremio page. This device will store a session token '
            'and your addon URLs locally (not encrypted). Continue?'):
        return
    code, link = create_link()
    progress = xbmcgui.DialogProgress()
    progress.create('Connect Stremio', 'Open on your phone or computer:\n' + link)
    monitor = xbmc.Monitor()
    deadline = time.monotonic() + 300
    try:
        while time.monotonic() < deadline and not progress.iscanceled():
            if monitor.abortRequested():
                return
            token = read_link(code)
            if progress.iscanceled() or monitor.abortRequested():
                return
            if token:
                addons, skipped = pull_addons(token)
                if progress.iscanceled() or monitor.abortRequested():
                    return
                STORE.save({'token': token, 'addons': addons})
                progress.close()
                xbmcgui.Dialog().ok('Stremio connected',
                    '{} addons imported. {} unsupported entries skipped.'.format(len(addons), skipped))
                return
            if monitor.waitForAbort(5):
                return
        if not progress.iscanceled():
            xbmcgui.Dialog().ok('Stremio', 'Sign-in timed out. Start again for a new link.')
    finally:
        progress.close()


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
    action = params.get('action', 'root')
    if action in ('connect', 'sync', 'disconnect'):
        if action == 'connect':
            connect_account()
        elif action == 'sync':
            state = STORE.load()
            if not state.get('token'):
                raise AccountError('Connect your account first.')
            addons, skipped = pull_addons(state['token'])
            STORE.save({'token': state['token'], 'addons': addons})
            xbmcgui.Dialog().ok('Stremio', '{} addons imported. {} skipped.'.format(len(addons), skipped))
        elif xbmcgui.Dialog().yesno('Disconnect this device',
                'Remove the local token and imported addon list? Your Stremio account stays unchanged.'):
            STORE.forget()
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        xbmc.executebuiltin('Container.Refresh')
        return
    provider = params.get('provider', '')
    manifest_url = MANIFEST
    descriptor = None
    if provider:
        descriptor = next((entry for entry in STORE.load().get('addons', [])
                           if entry.get('id') == provider), None)
        if descriptor is None:
            raise AccountError('Addon no longer in local account collection. Refresh the list.')
        manifest_url = descriptor['transportUrl']
    base_url(manifest_url)

    def provider_route(**values):
        return route(provider=provider, **values)

    if action == 'widgets':
        # Widget picker has no login/logout actions and excludes stream-only addons.
        xbmcplugin.addDirectoryItem(HANDLE, route(action='provider'),
                                   xbmcgui.ListItem(label='Manual catalog'), True)
        for addon in STORE.load().get('addons', []):
            if not catalogs(addon['manifest']):
                continue
            label = addon['manifest'].get('name') or 'Stremio addon'
            xbmcplugin.addDirectoryItem(HANDLE, route(action='provider', provider=addon['id']),
                                       xbmcgui.ListItem(label=label), True)
    elif action == 'root':
        state = STORE.load()
        options = [('connect', 'Connect Stremio account')]
        if state.get('token'):
            options = [('sync', 'Refresh account addons'), ('disconnect', 'Disconnect this device')]
        for target, label in options:
            xbmcplugin.addDirectoryItem(HANDLE, route(action=target), xbmcgui.ListItem(label=label), True)
        xbmcplugin.addDirectoryItem(HANDLE, route(action='provider'),
                                   xbmcgui.ListItem(label='Manual catalog'), True)
        for addon in state.get('addons', []):
            label = addon['manifest'].get('name') or 'Stremio addon'
            xbmcplugin.addDirectoryItem(HANDLE, route(action='provider', provider=addon['id']),
                                       xbmcgui.ListItem(label=label), True)
    elif action == 'provider':
        manifest = descriptor['manifest'] if descriptor else fetch(manifest_url)
        available = catalogs(manifest)
        if not available:
            xbmcgui.Dialog().ok('Stremio', 'This addon has no unfiltered catalogs. Stream-only addons are imported; cross-addon playback is the next step.')
        for catalog in available:
            label = catalog.get('name', catalog['id']) + ' · ' + catalog['type']
            xbmcplugin.addDirectoryItem(HANDLE, provider_route(action='catalog', kind=catalog['type'],
                id=catalog['id']), xbmcgui.ListItem(label=label), True)
    elif action == 'catalog':
        kind = params['kind']
        xbmcplugin.setContent(HANDLE, 'tvshows' if kind == 'series' else 'movies')
        response = fetch(resource_url(manifest_url, 'catalog', kind, params['id']))
        for meta in response.get('metas', []):
            if not meta.get('id'):
                continue
            xbmcplugin.addDirectoryItem(HANDLE, provider_route(action='meta',
                kind=meta.get('type', kind), id=meta['id']), item(meta), True)
    elif action == 'meta':
        kind, identity = params['kind'], params['id']
        meta = fetch(resource_url(manifest_url, 'meta', kind, identity)).get('meta') or {}
        videos = meta.get('videos', []) if kind == 'series' else []
        if videos:
            xbmcplugin.setContent(HANDLE, 'episodes')
            for video in videos:
                if not video.get('id'):
                    continue
                entry = xbmcgui.ListItem(label='S{} E{} · {}'.format(
                    video.get('season', '?'), video.get('episode', '?'), video.get('title', '')))
                entry.getVideoInfoTag().setMediaType('episode')
                xbmcplugin.addDirectoryItem(HANDLE, provider_route(action='streams', kind=kind,
                    id=video['id']), entry, True)
        else:
            xbmcplugin.addDirectoryItem(HANDLE, provider_route(action='streams', kind=kind,
                id=identity), item(meta), True)
    elif action == 'streams':
        manifest = fetch(manifest_url)
        supported = any((r if isinstance(r, str) else r.get('name')) == 'stream'
                        for r in manifest.get('resources', []))
        if not supported:
            xbmcgui.Dialog().ok('StremioELEC', 'This addon provides metadata only. Stream addon aggregation is not connected yet.')
        else:
            streams = fetch(resource_url(manifest_url, 'stream', params['kind'], params['id'])).get('streams', [])
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
    except AccountError as error:
        xbmcgui.Dialog().ok('Stremio account', str(error))
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
    except Exception:
        # Provider URLs can contain secrets: never log exceptions/URLs here.
        xbmcgui.Dialog().ok('StremioELEC', 'Unable to load this addon response. Check the manifest setting and connection.')
        if params.get('action') == 'play':
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
