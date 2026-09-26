import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from library_actions import change
from account import AccountError


class LibraryActionTests(unittest.TestCase):
    def test_remove_preserves_progress(self):
        before = {'_id': 'tt1', 'type': 'movie', 'removed': False, 'temp': False, 'state': {'timeOffset': 1234}, 'extra': 'keep'}
        after = dict(before, removed=True)
        with patch('library_actions.pull_library', side_effect=[[before], [after]]), patch('library_actions.request', return_value={'result': True}) as request:
            change('test', 'tt1', 'movie', 'Title', '', False)
            item = request.call_args.args[1]['changes'][0]
            self.assertEqual(item['state'], before['state'])
            self.assertEqual(item['extra'], 'keep')
            self.assertFalse(before['removed'])

    def test_no_write_when_already_in_library(self):
        with patch('library_actions.pull_library', return_value=[{'_id': 'tt1', 'type': 'movie'}]), patch('library_actions.request') as request:
            change('test', 'tt1', 'movie', 'Title', '', True)
            request.assert_not_called()

    def test_unconfirmed_write_is_error(self):
        with patch('library_actions.pull_library', return_value=[]), patch('library_actions.request', return_value={'result': True}):
            with self.assertRaises(AccountError):
                change('test', 'tt1', 'movie', 'Title', '', True)
