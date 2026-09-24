import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ADDON = Path(__file__).parent / 'plugin.video.stremioelec'
sys.path.insert(0, str(ADDON))
from addons_core import (account_addons, account_descriptors, active_addons,
                         community_catalog, configure_url, configuration_state,
                         filter_community, install_descriptor_local, install_local,
                         merge_account, remove_local, set_enabled)


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


    def test_account_sync_preserves_local_only_addons(self):
        state = {'addons': [], 'disabledAddons': []}
        local = install_local(state, 'https://local.example/manifest.json',
                              fetcher=lambda _: self.manifest('Local'))
        remote_manifest = dict(self.manifest('Remote'), id='org.remote')
        remote = [{'id': 'remote-id', 'transportUrl': 'https://remote.example/manifest.json',
                   'manifest': remote_manifest, 'account': True,
                   'flags': {'official': True}}]
        merged = merge_account(state, remote)
        self.assertEqual({item['manifest']['name'] for item in merged}, {'Local', 'Remote'})
        state['addons'] = merged
        self.assertEqual([item['manifest']['name'] for item in account_addons(state)], ['Remote'])
        self.assertFalse(local.get('account'))

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


    def test_community_catalog_validates_dedupes_and_sorts(self):
        a = {'id': 'org.a', 'name': 'Zulu', 'version': '1.0.0',
             'resources': ['stream'], 'types': ['movie']}
        b = {'id': 'org.b', 'name': 'Alpha', 'version': '1.0.0',
             'resources': ['subtitles'], 'types': ['series']}
        rows = community_catalog(fetcher=lambda _: {'addons': [
            {'transportUrl': 'https://z.example/manifest.json', 'manifest': a},
            {'transportUrl': 'https://a.example/manifest.json', 'manifest': b},
            {'transportUrl': 'https://a.example/manifest.json', 'manifest': b},
            {'transportUrl': 'http://bad.example/manifest.json', 'manifest': a},
        ]})
        self.assertEqual([row['manifest']['name'] for row in rows], ['Alpha', 'Zulu'])

    def test_community_filters(self):
        rows = [
            {'transportUrl': 'https://a.example/manifest.json',
             'manifest': {'id': 'a', 'name': 'Movie Streams', 'version': '1',
                          'resources': ['stream'], 'types': ['movie']}},
            {'transportUrl': 'https://b.example/manifest.json',
             'manifest': {'id': 'b', 'name': 'Subs', 'version': '1',
                          'resources': ['subtitles'], 'types': ['series']}},
            {'transportUrl': 'https://c.example/manifest.json',
             'manifest': {'id': 'c', 'name': 'Live', 'version': '1',
                          'resources': [{'name': 'catalog'}], 'types': ['tv', 'channel']}},
        ]
        self.assertEqual(len(filter_community(rows, 'movies')), 2)
        self.assertEqual([r['manifest']['name'] for r in filter_community(rows, 'subtitles')], ['Subs'])
        self.assertEqual([r['manifest']['name'] for r in filter_community(rows, 'catalogs')], ['Live'])
        self.assertEqual([r['manifest']['name'] for r in filter_community(rows, 'live')], ['Live'])
        self.assertEqual([r['manifest']['name'] for r in filter_community(rows, 'all', 'movie')], ['Movie Streams'])

    def test_catalog_descriptor_installs_without_second_network_fetch(self):
        state = {'addons': [], 'disabledAddons': []}
        manifest = self.manifest('Catalog Item')
        item = install_descriptor_local(state, 'https://example.com/manifest.json', manifest)
        self.assertEqual(item['manifest']['name'], 'Catalog Item')
        self.assertFalse(item['account'])

    def test_rejects_non_https_manifest(self):
        with self.assertRaises(ValueError):
            install_local({}, 'http://example.com/manifest.json',
                          fetcher=lambda _: self.manifest())


if __name__ == '__main__':
    unittest.main()
