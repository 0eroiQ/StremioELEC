import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'plugin.video.stremioelec'))
from trailers import discover, video_identity, resolve


class TrailersTest(unittest.TestCase):
    def test_selected_clip_without_progress_dialog(self):
        import runpy
        from types import SimpleNamespace
        from unittest.mock import patch, Mock
        props = {'StremioTrailerBusy': '1'}  # stale legacy flag must recover
        window = SimpleNamespace(getProperty=lambda k: props.get(k, ''),
                                 setProperty=props.__setitem__,
                                 clearProperty=lambda k: props.pop(k, None))
        kodi = SimpleNamespace(getInfoLabel=lambda k: 'https://youtu.be/abcdefghijk' if 'FolderPath' in k else 'Trailer',
                               Monitor=lambda: SimpleNamespace(abortRequested=lambda: False),
                               log=lambda *a: self.fail(str(a)), LOGWARNING=2)
        gui = SimpleNamespace(Window=lambda _: window,
                              DialogProgress=lambda: self.fail('No extra dialog for selected clips'))
        played = Mock()
        with patch.dict(sys.modules, {'xbmc': kodi, 'xbmcgui': gui, 'xbmcaddon': SimpleNamespace()}), \
             patch.object(sys, 'argv', ['trailer_player.py', 'selected']), \
             patch('slyguy_trailers.play', played):
            runpy.run_path(str(Path(__file__).parent / 'plugin.video.stremioelec/trailer_player.py'), run_name='__main__')
        played.assert_called_once_with('https://youtu.be/abcdefghijk')
        self.assertNotIn('StremioTrailerBusy', props)

    def test_slyguy_exact_clip_route(self):
        from slyguy_trailers import youtube_route
        self.assertEqual(youtube_route('plugin://plugin.video.youtube/play/?video_id=abcdefghijk'),
                         'plugin://slyguy.trailers/play/?video_id=abcdefghijk')
        with self.assertRaises(ValueError):
            youtube_route('https://evil.test/?v=abcdefghijk')

    def test_slyguy_dispatch_and_disabled_guard(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from slyguy_trailers import play
        calls = []
        import json
        def dispatch(request):
            calls.append(json.loads(request))
            return '{"result":"OK"}'
        closed = []
        kodi = SimpleNamespace(getCondVisibility=lambda _: True, executeJSONRPC=dispatch,
                               executebuiltin=lambda *args: closed.append(args))
        addons = SimpleNamespace(Addon=lambda name: self.assertEqual(name, 'slyguy.trailers'))
        with patch.dict(sys.modules, {'xbmc': kodi, 'xbmcaddon': addons}):
            play('https://youtu.be/abcdefghijk')
            self.assertEqual(calls[0]['method'], 'Player.Open')
            self.assertEqual(closed, [('Dialog.Close(12003,true)', True)])
            self.assertEqual(calls[0]['params']['item']['file'],
                             'plugin://slyguy.trailers/play/?video_id=abcdefghijk')
            kodi.getCondVisibility = lambda _: False
            with self.assertRaises(RuntimeError):
                play('https://youtu.be/abcdefghijk')
            self.assertEqual(len(calls), 1)

    def test_links(self):
        for link in ('plugin://plugin.video.youtube/play/?video_id=abcdefghijk',
                     'https://www.youtube.com/watch?v=abcdefghijk', 'https://youtu.be/abcdefghijk'):
            self.assertEqual(video_identity(link), 'abcdefghijk')
        for link in ('plugin://evil/?video_id=abcdefghijk', 'https://evil.test/?v=abcdefghijk', 'https://youtu.be/abc'):
            with self.assertRaises(ValueError): video_identity(link)

    def test_tmdb_order_and_filter(self):
        result = discover('test', 'movie', '1', fetcher=lambda _: {'results': [
            {'site': 'YouTube', 'key': 'abcdefghijk', 'type': 'Teaser'},
            {'site': 'YouTube', 'key': 'bcdefghijkl', 'type': 'Trailer', 'official': True},
            {'site': 'BadSite', 'key': 'cdefghijklm', 'type': 'Trailer'}]})
        self.assertEqual([r['key'] for r in result], ['bcdefghijkl', 'abcdefghijk'])

    def test_no_title_guess(self):
        self.assertEqual(discover('test', 'tv', imdb='wrong', fetcher=lambda _: self.fail()), [])

    def test_resolver(self):
        class Fake:
            def __init__(self, options):
                assert options['skip_download'] and not options['cachedir']
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def extract_info(self, url, download):
                assert download is False
                return {'url': 'https://video.test/trailer', 'vcodec': 'h264', 'acodec': 'aac'}
        self.assertEqual(resolve('abcdefghijk', Fake), 'https://video.test/trailer')

    def test_skin_routes_no_install(self):
        import re
        import xml.etree.ElementTree as ET
        source = (Path(__file__).parents[1] / '1080i/IncludesDialogVideoInfo.xml').read_text()
        root = ET.fromstring(re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#)', '&amp;', source))
        blocks = [n for n in root.iter('control') if n.get('id') in ('54', '354')]
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            actions = ' '.join(n.text or '' for n in block.findall('onclick'))
            self.assertIn('trailer_player.py', actions)
            self.assertNotIn('InstallAddon', actions)
            self.assertNotIn('PlayMedia', actions)
