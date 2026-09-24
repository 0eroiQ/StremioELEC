"""Skin RunScript entry: existing TMDb clips played by SlyGuy Trailers."""
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
from trailers import discover
from slyguy_trailers import play


def main():
    window = xbmcgui.Window(10000)
    try:
        busy_since = float(window.getProperty('StremioTrailerBusy') or 0)
    except ValueError:
        busy_since = 0
    if 0 <= time.time() - busy_since < 60:
        return
    window.setProperty('StremioTrailerBusy', str(time.time()))
    progress = None
    try:
        label = xbmc.getInfoLabel
        selected_clip = 'selected' in sys.argv[1:]
        link = (label('Container(354).ListItem.FolderPath') or label('Container(354).ListItem.FileNameAndPath')) if selected_clip else label('ListItem.Trailer')
        if link:
            title = label('Container(354).ListItem.Label') if selected_clip else label('ListItem.Title')
            if xbmc.Monitor().abortRequested():
                return
            play(link)
            return
        if selected_clip:
            raise ValueError('Missing selected trailer')
        addon = xbmcaddon.Addon('plugin.video.stremioelec')
        helper = xbmcaddon.Addon('plugin.video.tmdb.bingie.helper')
        key = addon.getSetting('tmdb_api_key').strip()
        if not key:
            xbmcgui.Dialog().ok('StremioELEC trailers', 'Open Trailers & More to use the existing TMDb clips, or add your TMDb API key in Catalogs and artwork for a separate lookup.')
            return
        label = xbmc.getInfoLabel
        kind = label('ListItem.DBType') or label('ListItem.Property(DBTYPE)')
        kind = 'tv' if kind in ('tvshow', 'season', 'episode', 'series') else 'movie'
        tmdb = label('ListItem.Property(tmdb_id)') or label('ListItem.UniqueID(tmdb)')
        imdb = label('ListItem.IMDBNumber') or label('ListItem.Property(imdb_id)')
        title = label('ListItem.Title')
        progress = xbmcgui.DialogProgress()
        progress.create('StremioELEC trailers', 'Finding official trailers on TMDb…')
        rows = discover(key, kind, tmdb, imdb, helper.getSetting('language') or 'en-US')
        if progress.iscanceled() or xbmc.Monitor().abortRequested():
            return
        progress.close()
        progress = None
        if not rows:
            xbmcgui.Dialog().ok('StremioELEC trailers', 'No trailer found for this title.')
            return
        selected = xbmcgui.Dialog().select('TMDb trailers', [r.get('name', 'Trailer') for r in rows])
        if selected < 0:
            return
        if xbmc.Monitor().abortRequested():
            return
        play('https://www.youtube.com/watch?v=' + rows[selected]['key'])
    except Exception as error:
        xbmc.log('StremioELEC trailer failed: ' + type(error).__name__, xbmc.LOGWARNING)
        if progress is not None:
            progress.close()
            progress = None
        xbmcgui.Dialog().ok('StremioELEC trailers', 'Unable to open trailer. The built-in trailer playback component is unavailable; install a verified StremioELEC system update.')
    finally:
        window.clearProperty('StremioTrailerBusy')
        if progress is not None:
            progress.close()


if __name__ == '__main__':
    main()
