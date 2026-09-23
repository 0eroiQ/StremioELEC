import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from sources import collect, supports, direct_url


class SourcesTest(unittest.TestCase):
    def test_string_resource_uses_global_filters(self):
        manifest = {'resources': ['stream'], 'types': ['series'], 'idPrefixes': ['tt']}
        self.assertTrue(supports(manifest, 'series', 'tt123:1:2'))
        self.assertFalse(supports(manifest, 'movie', 'tt123'))
        self.assertFalse(supports(manifest, 'series', 'other'))

    def test_object_resource_overrides_global_filters(self):
        manifest = {'types': ['series'], 'idPrefixes': ['bad'],
                    'resources': [{'name': 'stream', 'types': ['movie']}]}
        self.assertTrue(supports(manifest, 'movie', 'tt123'))
        self.assertFalse(supports(manifest, 'series', 'tt123'))

    def test_unsupported_sources(self):
        self.assertTrue(direct_url({'url': 'https://example.com/video.mp4'}))
        for stream in ({'infoHash': 'abc'}, {'url': 'file:///tmp/video'},
                       {'url': 'https://example.com/x|Header=secret'},
                       {'url': 'https://example.com/x', 'behaviorHints': {'proxyHeaders': {'request': {}}}},
                       {'url': 'https://user:pass@example.com/x'}):
            self.assertFalse(direct_url(stream))

    def test_aggregation_deduplicates_providers_and_isolates_failures(self):
        providers = [{'transportUrl': 'https://{}.example/manifest.json'.format(name),
                      'manifest': {'name': name, 'resources': ['stream'], 'types': ['movie']}}
                     for name in ('first', 'broken', 'last')]
        requested = []
        def fetcher(url):
            requested.append(url)
            if 'broken' in url:
                raise RuntimeError('private error')
            return {'streams': [{'url': 'https://example.com/video', 'title': '1080p'}, {'infoHash': 'abc'}]}
        streams, skipped, failed = collect(providers + providers[:1], 'movie', 'tt123', fetcher)
        self.assertEqual(len(requested), 3)
        self.assertEqual([s['label'] for s in streams], ['first · 1080p', 'last · 1080p'])
        self.assertEqual((skipped, failed), (2, 1))


if __name__ == '__main__':
    unittest.main()
