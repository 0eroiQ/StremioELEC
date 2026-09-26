import pathlib
import sys
import unittest
import tempfile
from unittest.mock import Mock, patch
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from subtitles import collect_subtitles, language, prepare_selected, download


class SubtitlesTest(unittest.TestCase):
    def test_download_accepts_text_not_html_or_archive(self):
        for payload, valid in [(b'1\n00:00:01,000 --> 00:00:02,000\nHello', True),
                               (b'<html>Error</html>', False), (b'PK\x03\x04binary', False)]:
            response = Mock()
            response.read.return_value = payload
            opener = Mock()
            opener.__enter__ = Mock(return_value=response)
            opener.__exit__ = Mock(return_value=False)
            with tempfile.TemporaryDirectory() as folder, patch('subtitles.urlopen', return_value=opener):
                if valid:
                    path = download({'url': 'https://example.org/subtitle', 'lang': 'hrv'}, folder)
                    self.assertTrue(path.endswith('.hrv.srt'))
                else:
                    with self.assertRaises(ValueError):
                        download({'url': 'https://example.org/subtitle', 'lang': 'hrv'}, folder)

    def test_kodi_languages_and_preferred(self):
        provider = {'transportUrl': 'https://example.org/manifest.json',
                    'manifest': {'resources': ['subtitles'], 'types': ['movie']}}
        fetcher = Mock(return_value={'subtitles': [
            {'lang': 'eng', 'url': 'https://example.org/en.srt'},
            {'lang': 'hrv', 'url': 'https://example.org/hr.srt'},
            {'lang': 'deu', 'url': 'https://example.org/de.srt'},
            {'lang': 'hrv', 'url': 'file:///bad.srt'}]})
        results = collect_subtitles([provider, provider], 'movie', 'tt123', ['eng', 'hrv'], 'hrv', fetcher=fetcher)
        self.assertEqual([r['lang'] for r in results], ['hrv', 'eng'])
        fetcher.assert_called_once()
        self.assertEqual(language('Croatian'), 'hrv')
        self.assertEqual(language('Serbian'), 'srp')

    def test_provider_failure_and_inline_subtitles(self):
        provider = {'transportUrl': 'https://example.org/manifest.json',
                    'manifest': {'resources': [{'name': 'subtitles', 'types': ['series'], 'idPrefixes': ['tt']}]}}
        results = collect_subtitles([provider], 'series', 'tt123:1:1', ['bos'], 'bos',
                                    [{'lang': 'bs', 'url': 'https://example.org/bs.srt'}], fetcher=Mock(side_effect=ValueError))
        self.assertEqual(len(results), 1)

    def test_auto_off_does_not_fetch_or_download(self):
        with patch('subtitles.remember_selection'), patch('subtitles.preferences', return_value=(['eng'], 'eng', False)), \
             patch('subtitles.collect_subtitles') as collect:
            prepare_selected('/unused', 'movie', 'tt123', {}, [], Mock())
            collect.assert_not_called()

    def test_auto_downloads_only_selected_file(self):
        entries = [{'lang': 'hrv', 'url': 'https://example.org/1'}, {'lang': 'eng', 'url': 'https://example.org/2'}]
        item = Mock()
        with patch('subtitles.remember_selection'), patch('subtitles.preferences', return_value=(['hrv', 'eng'], 'hrv', True)), \
             patch('subtitles.collect_subtitles', return_value=entries), patch('subtitles.download', return_value='/tmp/test.hrv.srt') as download:
            prepare_selected('/unused', 'movie', 'tt123', {}, [], item)
            download.assert_called_once()
            item.setSubtitles.assert_called_once_with(['/tmp/test.hrv.srt'])
