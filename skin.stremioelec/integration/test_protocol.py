import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from protocol import base_url, catalogs, resource_url


class ProtocolTests(unittest.TestCase):
    def test_configured_manifest_path_is_preserved(self):
        self.assertEqual(resource_url('https://example.org/config/manifest.json',
            'meta', 'series', 'tt123:1:2'),
            'https://example.org/config/meta/series/tt123%3A1%3A2.json')

    def test_extra_values_are_encoded(self):
        self.assertTrue(resource_url('https://example.org/manifest.json',
            'catalog', 'movie', 'top', {'search': 'a/b & c'}).endswith(
                '/search=a%2Fb%20%26%20c.json'))

    def test_invalid_transports_rejected(self):
        for url in ('file:///tmp/manifest.json', 'https://example.org/nope',
                    'https://example.org/manifest.json?token=x'):
            with self.assertRaises(ValueError):
                base_url(url)

    def test_required_filter_catalogs_not_requested_without_filter(self):
        result = catalogs({'catalogs': [
            {'id': 'top', 'type': 'movie'},
            {'id': 'search', 'type': 'movie', 'extra': [{'name': 'search', 'isRequired': True}]}
        ]})
        self.assertEqual([entry['id'] for entry in result], ['top'])


if __name__ == '__main__':
    unittest.main()
