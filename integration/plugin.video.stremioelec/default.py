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
from account import AccountError, Store, create_link, read_link, pull_addons, pull_library, library_rows
from sources import collect, direct_url

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
                try:
                    library = pull_library(token)
                    STORE.save({'token': token, 'addons': addons, 'library': library})
                except AccountError:
                    xbmcgui.Dialog().notification('Stremio', 'Library import failed; retry Refresh library.')
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
    # Kodi may dispatch the subtitle extension through the addon's primary
    # plugin entry point; support both entry paths explicitly.
    if action in ('search', 'manualsearch', 'download'):
        from subtitle_service import run as subtitle_service
        return subtitle_service()
    if action == 'helper_play':
        from helper_player import resolve
        from subtitles import prepare_selected
        providers = STORE.load().get('addons', [])
        return resolve(params, providers, collect,
                       xbmcgui.Dialog(), xbmcplugin, xbmcgui, HANDLE,
                       lambda kind, identity, stream, item: prepare_selected(STORE.directory, kind, identity, stream, providers, item))
    if action == 'subtitles':
        from subtitles import manual_selection
        manual_selection(STORE.directory, STORE.load().get('addons', []))
        return
    if action == 'setup_home':
        if xbmcgui.Dialog().yesno('StremioELEC setup', 'Replace Home with Continue Watching and nine Bingie catalogs? Existing Home will be backed up. Kodi language choices are kept.'):
            from setup_profile import prepare
            prepare(STORE.directory, xbmcvfs.translatePath(ADDON.getAddonInfo('path')), force_home=True)
            xbmc.executebuiltin('ReloadSkin()')
        return
    if action == 'first_catalog':
        for addon in STORE.load().get('addons', []):
            available = catalogs(addon['manifest'])
            if available:
                return run({'action': 'catalog', 'provider': addon['id'],
                            'kind': available[0]['type'], 'id': available[0]['id']})
        xbmcplugin.endOfDirectory(HANDLE)
        return
    if action in ('connect', 'sync', 'sync_library', 'disconnect'):
        if action == 'connect':
            connect_account()
        elif action == 'sync':
            state = STORE.load()
            if not state.get('token'):
                raise AccountError('Connect your account first.')
            addons, skipped = pull_addons(state['token'])
            state['addons'] = addons
            STORE.save(state)
            xbmcgui.Dialog().ok('Stremio', '{} addons imported. {} skipped.'.format(len(addons), skipped))
        elif action == 'sync_library':
            state = STORE.load()
            if not state.get('token'):
                raise AccountError('Connect your account first.')
            state['library'] = pull_library(state['token'])
            STORE.save(state)
            xbmcgui.Dialog().ok('Stremio', '{} library entries imported. Account unchanged.'.format(len(state['library'])))
        elif xbmcgui.Dialog().yesno('Disconnect this device',
                'Remove the local token and imported addon list? Your Stremio account stays unchanged.'):
            STORE.forget()
            Store(STORE.directory / 'streams').forget()
            Store(STORE.directory / 'playback').forget()
            Store(STORE.directory / 'subtitle-results').forget()
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
        for target, label in [('library', 'My Library'), ('continue', 'Continue Watching')]:
            xbmcplugin.addDirectoryItem(HANDLE, route(action=target), xbmcgui.ListItem(label=label), True)
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
            options = [('sync', 'Refresh account addons'), ('sync_library', 'Refresh library'),
                       ('library', 'My Library'), ('continue', 'Continue Watching'), ('disconnect', 'Disconnect this device')]
        for target, label in options:
            xbmcplugin.addDirectoryItem(HANDLE, route(action=target), xbmcgui.ListItem(label=label), True)
        for target, label in [('setup_home', 'Set up Bingie Home (10 rows)'), ('subtitles', 'Stremio subtitles for current video')]:
            xbmcplugin.addDirectoryItem(HANDLE, route(action=target), xbmcgui.ListItem(label=label), False)
        xbmcplugin.addDirectoryItem(HANDLE, route(action='provider'),
                                   xbmcgui.ListItem(label='Manual catalog'), True)
        for addon in state.get('addons', []):
            label = addon['manifest'].get('name') or 'Stremio addon'
            xbmcplugin.addDirectoryItem(HANDLE, route(action='provider', provider=addon['id']),
                                       xbmcgui.ListItem(label=label), True)
    elif action in ('library', 'continue'):
        xbmcplugin.setContent(HANDLE, 'videos')
        for saved in library_rows(STORE.load().get('library', []), action == 'continue'):
            meta = dict(saved, id=saved['_id'])
            entry = item(meta)
            progress = saved['state']
            video = progress.get('video_id')
            if action == 'continue' and (saved['type'] == 'movie' or video):
                target = route(action='streams', kind=saved['type'], id=video or saved['_id'])
                entry.setProperty('StremioResumeMilliseconds', str(progress.get('timeOffset', 0)))
            else:
                target = route(action='meta', kind=saved['type'], id=saved['_id'])
            xbmcplugin.addDirectoryItem(HANDLE, target, entry, True)
    elif action == 'provider':
        manifest = descriptor['manifest'] if descriptor else fetch(manifest_url)
        available = catalogs(manifest)
        if not available:
            xbmcgui.Dialog().ok('Stremio', 'This addon has no unfiltered catalogs. Its supported streams are requested when opening sources for a matching title.')
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
        providers = list(STORE.load().get('addons', []))
        if not provider:
            try:
                providers.append({'transportUrl': manifest_url, 'manifest': fetch(manifest_url)})
            except Exception:
                pass  # Account providers can still work if the manual provider is down.
        playable, skipped, failed = collect(providers, params['kind'], params['id'])
        # Keep signed stream URLs out of saved plugin routes and widget configuration.
        import secrets
        cache = Store(STORE.directory / 'streams')
        cached = {}
        for stream in playable:
            key = secrets.token_hex(16)
            cached[key] = dict(stream, kind=params['kind'], id=params['id'])
            entry = xbmcgui.ListItem(label=stream['label'])
            entry.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, route(action='play', key=key), entry, False)
        cache.save({'created': time.time(), 'urls': cached})
        if not playable:
            xbmcgui.Dialog().ok('StremioELEC',
                'No supported direct HTTP streams. {} unsupported; {} addons failed. '
                'Torrents, DRM and custom proxy headers are not supported yet.'.format(skipped, failed))
        elif skipped or failed:
            xbmcgui.Dialog().notification('StremioELEC',
                '{} unsupported streams; {} addons failed'.format(skipped, failed))
    elif action == 'play':
        cache = Store(STORE.directory / 'streams').load()
        stream = cache.get('urls', {}).get(params.get('key'), '')
        url = stream.get('url', '') if isinstance(stream, dict) else stream
        if time.time() - cache.get('created', 0) > 3600 or not direct_url({'url': url}):
            raise ValueError('Source expired; reopen the stream list')
        entry = xbmcgui.ListItem(path=url)
        if isinstance(stream, dict):
            from subtitles import prepare_selected
            try:
                prepare_selected(STORE.directory, stream['kind'], stream['id'], stream,
                                 STORE.load().get('addons', []), entry)
            except Exception:
                xbmcgui.Dialog().notification('Stremio subtitles', 'Subtitles unavailable; video will still start.')
        xbmcplugin.setResolvedUrl(HANDLE, True, entry)
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
        if params.get('action') in ('play', 'helper_play'):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
