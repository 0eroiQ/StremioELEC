"""Exercise widget browsing without an account, network, or Kodi runtime."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'


class WidgetRoutesTest(unittest.TestCase):
    def test_picker_filters_providers_and_preserves_catalog_identity(self):
        modules = {name: MagicMock() for name in
                   ('xbmc', 'xbmcaddon', 'xbmcvfs', 'xbmcgui', 'xbmcplugin')}
        modules['xbmcvfs'].translatePath.return_value = '/unused-test-profile'
        modules['xbmcaddon'].Addon.return_value.getSetting.return_value = 'https://v3-cinemeta.strem.io/manifest.json'
        with patch.dict(sys.modules, modules), patch.object(sys, 'argv',
                ['plugin://plugin.video.stremioelec/', '1', '']), patch.object(sys, 'path', [str(ADDON)] + sys.path):
            spec = importlib.util.spec_from_file_location('widget_entry_test', ADDON / 'default.py')
            entry = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(entry)
            provider = {'id': 'opaque-provider-id',
                        'transportUrl': 'https://example.com/private-config/manifest.json',
                        'manifest': {'name': 'Test catalogs', 'catalogs': [
                            {'id': 'top', 'type': 'movie', 'name': 'Popular'}]}}
            entry.STORE = MagicMock()
            entry.STORE.load.return_value = {'addons': [provider,
                {'id': 'stream-only', 'manifest': {'name': 'Streams', 'catalogs': []}}]}
            entry.run({'action': 'widgets'})
            calls = modules['xbmcplugin'].addDirectoryItem.call_args_list
            self.assertEqual(len(calls), 4)  # Library, Continue, manual, catalog provider.
            route = calls[3].args[1]
            self.assertNotIn('private-config', route)
            self.assertEqual(parse_qs(urlsplit(route).query)['provider'], ['opaque-provider-id'])
            modules['xbmcplugin'].addDirectoryItem.reset_mock()
            entry.run({'action': 'provider', 'provider': 'opaque-provider-id'})
            query = parse_qs(urlsplit(modules['xbmcplugin'].addDirectoryItem.call_args.args[1]).query)
            self.assertEqual(query, {'action': ['catalog'], 'provider': ['opaque-provider-id'],
                                     'kind': ['movie'], 'id': ['top']})
            entry.STORE.save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
