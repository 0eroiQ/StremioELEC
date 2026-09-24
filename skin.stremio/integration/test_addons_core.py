import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'
sys.path.insert(0, str(ADDON))
from addons_core import (account_descriptors, active_addons, configure_url,
                         configuration_state, install_local, remove_local,
                         set_enabled)


class AddonsCoreTests(unittest.TestCase):
    def manifest(self, name='Demo'):
        return {'id': 'org.demo', 'name': name, 'version': '1.0.0',
                'resources': ['stream'], 'types': ['movie']}

    def test_install_disable_enable_remove_local(self):
        state = {'addons': [], 'disabledAddons': []}
        item = install_local(state, 'https://example.com/manifest.json',
                             fetcher=lambda _: self.manifest())
        self.assertEqual(len(active_addons(state)), 1)
        set_enabled(state, item['id'], False)
        self.assertEqual(active_addons(state), [])
        set_enabled(state, item['id'], True)
        self.assertEqual(len(active_addons(state)), 1)
        remove_local(state, item['id'])
        self.assertEqual(state['addons'], [])

    def test_reconfigure_replaces_same_addon_id(self):
        state = {'addons': [], 'disabledAddons': []}
        install_local(state, 'https://example.com/a/manifest.json',
                      fetcher=lambda _: self.manifest())
        install_local(state, 'https://example.com/b/manifest.json',
                      fetcher=lambda _: self.manifest())
        self.assertEqual(len(state['addons']), 1)
        self.assertEqual(state['addons'][0]['transportUrl'],
                         'https://example.com/b/manifest.json')

    def test_account_descriptors_preserve_flags(self):
        manifest = self.manifest()
        rows = account_descriptors([{
            'id': 'local-id', 'transportUrl': 'https://example.com/manifest.json',
            'manifest': manifest, 'flags': {'official': True, 'protected': True}
        }])
        self.assertEqual(rows[0]['flags'], {'official': True, 'protected': True})
        self.assertNotIn('id', rows[0])

    def test_configure_metadata_and_url(self):
        manifest = self.manifest()
        manifest['behaviorHints'] = {'configurable': True, 'configurationRequired': True}
        manifest['config'] = [{'key': 'token', 'type': 'password'}]
        state = configuration_state(manifest)
        self.assertTrue(state['configurable'])
        self.assertTrue(state['required'])
        self.assertEqual(configure_url('https://example.com/manifest.json'),
                         'https://example.com/configure')

    def test_rejects_non_https_manifest(self):
        with self.assertRaises(ValueError):
            install_local({}, 'http://example.com/manifest.json',
                          fetcher=lambda _: self.manifest())


if __name__ == '__main__':
    unittest.main()
