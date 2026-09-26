import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from account import AccountError, pull_library, library_rows


class LibraryTest(unittest.TestCase):
    def test_read_only_request(self):
        with patch('account.request', return_value={'result': []}) as request:
            self.assertEqual(pull_library('test-token'), [])
            request.assert_called_once_with('https://api.strem.io/api/datastoreGet',
                {'authKey': 'test-token', 'collection': 'libraryItem', 'ids': [], 'all': True})

    def test_failure_is_not_empty_library(self):
        with patch('account.request', return_value={'error': {}}):
            with self.assertRaises(AccountError):
                pull_library('test-token')

    def test_library_and_continue_filters(self):
        def entry(key, removed, temp, offset):
            return {'_id': key, 'type': 'movie', 'removed': removed, 'temp': temp,
                    'state': {'timeOffset': offset}}
        entries = [entry('saved', False, False, 100), entry('temporary', True, True, 50),
                   entry('deleted', True, False, 100), entry('finished', False, False, 0)]
        self.assertEqual({e['_id'] for e in library_rows(entries)}, {'saved', 'finished'})
        self.assertEqual({e['_id'] for e in library_rows(entries, True)}, {'saved', 'temporary'})
