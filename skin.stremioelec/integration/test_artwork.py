import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from artwork import enrich


class ArtworkTests(unittest.TestCase):
    def test_enrichment_cache_and_progress_preserved(self):
        row = {'_id': 'tt123', 'type': 'series', 'poster': 'poster', 'state': {'timeOffset': 500}}
        providers = [{'transportUrl': 'https://example.org/manifest.json', 'manifest': {'resources': ['meta'], 'types': ['series']}}]
        fetch = Mock(return_value={'meta': {'id': 'tt123', 'background': 'wide', 'logo': 'logo', 'state': {}}})
        with tempfile.TemporaryDirectory() as folder:
            for _ in range(2):
                result = enrich([row], providers, pathlib.Path(folder), fetch)[0]
                self.assertEqual(result['background'], 'wide')
                self.assertEqual(result['state'], row['state'])
            fetch.assert_called_once()
        self.assertNotIn('background', row)

    def test_provider_failure_preserves_row(self):
        row = {'_id': 'tt123', 'type': 'movie', 'state': {}}
        providers = [{'transportUrl': 'https://example.org/manifest.json', 'manifest': {'resources': ['meta'], 'types': ['movie']}}]
        with tempfile.TemporaryDirectory() as folder:
            result = enrich([row], providers, pathlib.Path(folder), Mock(side_effect=ValueError))[0]
        self.assertEqual(result['_id'], 'tt123')
        self.assertNotIn('background', result)
