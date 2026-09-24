"""Stremio addon collection management for the StremioELEC SYSTEM runtime."""
import hashlib
from urllib.parse import urlsplit, urlunsplit

from account import AccountError, request
from protocol import fetch


def normalize_manifest_url(value):
    value = (value or '').strip()
    if value.startswith('stremio://'):
        value = 'https://' + value[len('stremio://'):]
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not parsed.path.endswith('/manifest.json')):
        raise ValueError('Use an HTTPS Stremio manifest URL ending in /manifest.json')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Invalid addon manifest')
    for key in ('id', 'name', 'version', 'resources', 'types'):
        if key not in manifest:
            raise ValueError('Addon manifest is missing ' + key)
    if not isinstance(manifest['id'], str) or not manifest['id'].strip():
        raise ValueError('Invalid addon id')
    if not isinstance(manifest['name'], str) or not manifest['name'].strip():
        raise ValueError('Invalid addon name')
    if not isinstance(manifest['resources'], list) or not isinstance(manifest['types'], list):
        raise ValueError('Invalid addon capabilities')
    return manifest


def descriptor_id(url):
    return hashlib.sha256(url.encode()).hexdigest()


def make_descriptor(url, manifest, flags=None):
    result = {'id': descriptor_id(url), 'transportUrl': url, 'manifest': validate_manifest(manifest)}
    if isinstance(flags, dict):
        result['flags'] = flags
    return result


def install_local(state, url, fetcher=fetch):
    url = normalize_manifest_url(url)
    manifest = validate_manifest(fetcher(url))
    descriptor = make_descriptor(url, manifest)
    descriptor['account'] = False
    addons = list(state.get('addons', []))
    # A configured URL for the same addon replaces the old configuration.
    same_id = manifest.get('id')
    addons = [item for item in addons if item.get('manifest', {}).get('id') != same_id]
    addons.append(descriptor)
    state['addons'] = addons
    disabled = set(state.get('disabledAddons', []))
    disabled.discard(descriptor['id'])
    state['disabledAddons'] = sorted(disabled)
    return descriptor


def remove_local(state, identity):
    state['addons'] = [item for item in state.get('addons', []) if item.get('id') != identity]
    state['disabledAddons'] = sorted(set(state.get('disabledAddons', [])) - {identity})


def set_enabled(state, identity, enabled):
    if not any(item.get('id') == identity for item in state.get('addons', [])):
        raise ValueError('Unknown addon')
    disabled = set(state.get('disabledAddons', []))
    if enabled:
        disabled.discard(identity)
    else:
        disabled.add(identity)
    state['disabledAddons'] = sorted(disabled)


def active_addons(state):
    disabled = set(state.get('disabledAddons', []))
    return [item for item in state.get('addons', []) if item.get('id') not in disabled]



def account_addons(state):
    return [item for item in state.get('addons', []) if item.get('account') is True]


def merge_account(state, remote):
    """Replace account-owned entries while preserving local-only installs."""
    local = [item for item in state.get('addons', []) if item.get('account') is not True]
    remote_ids = {item.get('manifest', {}).get('id') for item in remote}
    local = [item for item in local if item.get('manifest', {}).get('id') not in remote_ids]
    return local + remote


def mark_account(state, identity, value=True):
    for item in state.get('addons', []):
        if item.get('id') == identity:
            item['account'] = bool(value)
            return
    raise ValueError('Unknown addon')


def account_descriptors(addons):
    rows = []
    for item in addons:
        url = normalize_manifest_url(item.get('transportUrl', ''))
        manifest = validate_manifest(item.get('manifest'))
        row = {'transportUrl': url, 'manifest': manifest}
        # Preserve official/protected flags received from Stremio.
        if isinstance(item.get('flags'), dict):
            row['flags'] = item['flags']
        rows.append(row)
    return rows


def push_account(token, addons):
    if not token:
        raise AccountError('Connect your Stremio account first.')
    payload = {'authKey': token, 'addons': account_descriptors(addons)}
    data = request('https://api.strem.io/api/addonCollectionSet', payload)
    if data.get('error'):
        raise AccountError('Stremio rejected the addon collection update.')
    if 'result' not in data:
        raise AccountError('Stremio did not confirm the addon collection update.')
    return data['result']


def configure_url(url):
    parsed = urlsplit(normalize_manifest_url(url))
    path = parsed.path[:-len('/manifest.json')] + '/configure'
    return urlunsplit((parsed.scheme, parsed.netloc, path, '', ''))


def configuration_state(manifest):
    hints = manifest.get('behaviorHints') if isinstance(manifest.get('behaviorHints'), dict) else {}
    return {
        'configurable': bool(hints.get('configurable')),
        'required': bool(hints.get('configurationRequired')),
        'schema': manifest.get('config') if isinstance(manifest.get('config'), list) else [],
    }
