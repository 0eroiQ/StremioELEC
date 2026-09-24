import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
import account


class AccountTests(unittest.TestCase):
    def test_only_official_origins_receive_tokens(self):
        for url in ('http://api.strem.io/api/a', 'https://evil.test/api/a',
                    'https://api.strem.io@evil.test/api/a'):
            with self.assertRaises(account.AccountError):
                account.request(url, {'authKey': 'secret'})

    def test_readonly_collection_preserves_config_and_hides_url_in_id(self):
        descriptor = {'transportUrl': 'https://example.org/private-config/manifest.json',
                      'manifest': {'name': 'Test'}}
        with patch.object(account, 'request', return_value={'result': {'addons': [descriptor, descriptor]}}) as call:
            addons, skipped = account.pull_addons('secret')
        self.assertEqual(len(addons), 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(addons[0]['transportUrl'], descriptor['transportUrl'])
        self.assertNotIn('private-config', addons[0]['id'])
        self.assertEqual(call.call_args.args[1]['update'], False)
        self.assertTrue(call.call_args.args[0].endswith('/addonCollectionGet'))

    def test_unsupported_transports_are_counted(self):
        with patch.object(account, 'request', return_value={'result': {'addons': [
                {'transportUrl': 'http://example.org/manifest.json', 'manifest': {}}, None]}}):
            self.assertEqual(account.pull_addons('secret'), ([], 2))

    def test_unapproved_link_does_not_authenticate(self):
        with patch.object(account, 'request', return_value={'result': {}}):
            self.assertIsNone(account.read_link('test'))
        with patch.object(account, 'request', return_value={'result': {'authKey': 'secret'}}):
            self.assertEqual(account.read_link('test'), 'secret')

    def test_unexpected_login_host_rejected(self):
        with patch.object(account, 'request', return_value={'result': {
                'code': 'test', 'link': 'https://evil.test/login'}}):
            with self.assertRaises(account.AccountError):
                account.create_link()

    def test_local_storage_permissions_and_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            store = account.Store(directory)
            store.save({'token': 'secret', 'addons': []})
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(store.load()['token'], 'secret')
            store.forget()
            self.assertEqual(store.load(), {})


if __name__ == '__main__':
    unittest.main()
