#!/usr/bin/env python3
"""Publish only verified same-run pilot artifacts; never change the stable feed."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPO = '0eroiQ/StremioELEC'


def check_assets(folder, lock, commit):
    version = lock['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+-test\.\d+', version):
        raise ValueError('This publisher accepts test versions only')
    prefix = 'StremioELEC-Generic.x86_64-' + version
    expected = {'README.md', 'provenance.json', 'update-candidate.json', 'addon-repository.zip',
                prefix + '.img.gz', prefix + '.tar', prefix + '-addons.zip'}
    if {p.name for p in folder.iterdir()} != expected | {'SHA256SUMS'}:
        raise ValueError('Unexpected release asset set')
    hashes = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9._-]+)', line)
        if not match or match[2] in hashes:
            raise ValueError('Invalid checksums file')
        hashes[match[2]] = match[1]
    if set(hashes) != expected:
        raise ValueError('Every asset must have a checksum')
    for name, wanted in hashes.items():
        file = folder / name
        if file.is_symlink() or not file.is_file():
            raise ValueError('Release assets must be regular files')
        checksum = hashlib.sha256()
        with file.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(block)
        if checksum.hexdigest() != wanted:
            raise ValueError('Checksum mismatch: ' + name)
    provenance = json.loads((folder / 'provenance.json').read_text())
    if provenance.get('build_commit') != commit or any(provenance.get(k) != v for k, v in lock.items()):
        raise ValueError('Artifacts do not belong to this source/lock revision')
    candidate = json.loads((folder / 'update-candidate.json').read_text())
    if candidate.get('expires') != 0 or candidate.get('target') != lock['target']:
        raise ValueError('A prerelease must not promote the stable update channel')
    for kind, suffix in [('os', '.tar'), ('addons', '-addons.zip')]:
        entry = candidate[kind]
        name = prefix + suffix
        if (entry['sha256'] != hashes[name] or entry['size'] != (folder / name).stat().st_size
                or entry['url'] != 'https://github.com/' + REPO + '/releases/download/v' + version + '/' + name):
            raise ValueError('Candidate manifest asset mismatch')
    return 'v' + version


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def main():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REPOSITORY') != REPO
            or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'):
        raise SystemExit('Publishing is restricted to manually dispatched project CI')
    folder = Path(sys.argv[1]).resolve()
    lock = json.loads((Path(__file__).parent / 'image.lock.json').read_text())
    commit = os.environ['GITHUB_SHA']
    tag = check_assets(folder, lock, commit)
    if json.loads(gh('api', 'repos/' + REPO + '/git/matching-refs/tags/' + tag)):
        raise ValueError('Release tag already exists; use a new version, never overwrite')
    notes = ('N60 / PN60-R test image — NOT hardware-accepted.\n\n'
             'Built from pinned LibreELEC 12.2.1 Generic x86-64 with skin.stremio and the Stremio bridge. '
             'Includes separate system and skin/bridge update controls. Automatic downloads default OFF; '
             'installation requires confirmation and restart.\n\n'
             'Assets: .img.gz for first USB installation; .tar for system updates; -addons.zip for our updater; '
             'SHA256SUMS and provenance identify the exact build.\n\n'
             'This pre-release is NOT offered to boxes by the stable update feed. N60 boot, network, HDMI, '
             'remote, playback and a real upgrade retaining the profile must still be tested. '
             'SlyGuy is not bundled pending redistribution review. The bridge does not yet provide torrent '
             'playback or Stremio progress writeback. See README.md for limitations.\n\n'
             'Independent unofficial project; original component licences/credits remain included.\n\n'
             'Build: https://github.com/' + REPO + '/actions/runs/' + os.environ['GITHUB_RUN_ID'])
    gh('release', 'create', tag, '--repo', REPO, '--target', commit, '--draft', '--prerelease',
       '--title', 'StremioELEC ' + lock['version'] + ' — N60 test image', '--notes', notes,
       *[str(p) for p in sorted(folder.iterdir())])
    # A failed upload/readback stays a draft rather than advertising partial assets.
    with tempfile.TemporaryDirectory(prefix='release-readback-') as tmp:
        gh('release', 'download', tag, '--repo', REPO, '--dir', tmp)
        if (Path(tmp) / 'SHA256SUMS').read_bytes() != (folder / 'SHA256SUMS').read_bytes():
            raise ValueError('Remote checksum manifest differs')
        check_assets(Path(tmp), lock, commit)
    gh('release', 'edit', tag, '--repo', REPO, '--draft=false', '--prerelease', '--latest=false')
    print('Published verified pre-release: https://github.com/' + REPO + '/releases/tag/' + tag)


if __name__ == '__main__':
    main()
