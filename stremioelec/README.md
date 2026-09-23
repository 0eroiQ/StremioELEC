# StremioELEC N60 image pilot

This is an independent, unofficial LibreELEC derivative. The first pipeline
repackages the **pinned official LibreELEC 12.2.1 Generic x86-64 image**, retaining
its kernel, drivers, partition table and bootloader. It injects the pinned Stremio
skin/bridge and checksum-locked dependencies into SYSTEM. It does not compile a
new kernel. Upstream source revision and all downloaded package hashes are in
`image.lock.json`; upstream licences are retained.

Target observed before starting this work: PN60-R, Intel i5-8250U, currently
running Android 14. Generic compatibility is a candidate, not physical boot proof.

## Build

Run **StremioELEC N60 test image** in Actions, or push the pipeline development
branch. It uses an ordinary Linux GitHub-hosted runner, no self-hosted runner,
Mac disk, USB or Android device. Only read permission is granted to the workflow.
Ordinary pushes and PRs cannot publish releases. Manual dispatch offers an
optional `publish_prerelease` switch: after a successful build, a separate job
verifies the exact asset set and source revision, uploads a draft, downloads it
again and verifies hashes, then publishes it as a Pre-release (never Latest).
Existing release tags cannot be overwritten. No workflow modifies the stable feed.

Outputs: `.img.gz` installer, `.tar` update candidate, `SHA256SUMS`, provenance,
`*-addons.zip`, an intentionally expired `update-candidate.json`,
and `addon-repository.zip` containing our skin/bridge/repository packages. Hashes
are integrity checks, **not signing or proof of a safe boot**. Artifacts expire
after 14 days. Keep accepted binaries and their corresponding sources in a release.

The source snapshot excludes account.json, userdata, caches, logs, local settings,
API keys and unused yt-dlp vendor files. The original developer checkout is not
reset or altered. The image starts with a fresh Stremio sign-in, not an account.

## First-image limitations and acceptance

- N60 boot, network, HDMI, audio, remote input, QR login and playback remain tests.
- LibreELEC's initial network wizard is retained for now; it must not be removed
  until equivalent network setup exists in our onboarding.
- Original upstream OS auto-downloads and native automatic addon updates start
  disabled. Do not enable original LibreELEC updates: they replace our SYSTEM.
- `repository.stremioelec` is bundled, but its release feed is not published by
  this workflow. Publishing the reviewed repository assets is a separate step.
- The second pilot bundles `service.stremioelec.updates` and **System > Updates**.
  Independent OS and skin/bridge download switches default OFF. ON checks at
  most every six hours while idle; it downloads but never forces a reboot.
  Manual download is available with both switches OFF. Installation requires
  explicit confirmation and playback must be stopped. One channel per restart.
- The client uses only our fixed `update-channel/stable.json` GitHub endpoint
  and our GitHub release assets. Target, major ABI, sequence, size, SHA256 and
  archive contents are checked before staging. HTTPS/GitHub write access is the
  trust anchor: **this is not a cryptographically signed update system**.
- OS packages enter `/storage/.update` only after full verification. Skin/bridge
  packages replace code overrides in `/storage/.kodi/addons` before Kodi starts;
  addon_data, accounts and guisettings are not in the packages. Interrupted code
  replacement has a rollback journal. This is not an OS A/B rollback mechanism.
- Synthetic upgrade, cancellation, tamper and rollback tests are included.
  A real N60 upgrade/reboot and retention test is still mandatory before stable
  promotion; do not equate unit tests or a successful image build with that test.
- The initial live channel is published with `os: null` and `addons: null`:
  https://raw.githubusercontent.com/0eroiQ/StremioELEC/update-channel/stable.json
  This provides a working endpoint without offering unaccepted pilot packages.
- SlyGuy playback worked in the Mac test runtime. Its packages are not
  redistributed in this candidate pending redistribution/licence review; trailers
  on this fresh image therefore need the original upstream installation.
- Stream support remains what the bridge implements (direct HTTP/S); no claim
  of torrent engine support or watch-progress writeback.

## Subsequent LibreELEC updates

1. Review a new **stable** upstream release; change the base version, immutable
   source revision and verified SHA256 in a PR (never float to latest/master).
2. Update compatible dependency pins deliberately; build and validate artifacts.
3. Boot/test on the N60; test a real update with a backed-up profile.
4. Publish an immutable StremioELEC release only after that acceptance.
5. Advance our stable update manifest, with target, minimum compatible version,
   artifact size/hash and required restart. Major Kodi changes need explicit review.

The candidate manifest has `expires: 0` so it cannot accidentally be used as a
live channel. After hardware acceptance, publish the exact checked artifacts
under its immutable release tag, verify downloaded bytes, then promote the
reviewed manifest with a finite future Unix expiry. `os` and `addons` can each
be null when no update is offered. Keep the channel alive by renewing expiry
when reviewed. An expired/unreachable feed leaves the installed system running.
The updater and third-party dependency changes travel in the OS channel, not
the skin/bridge bundle. Preserve monotonically increasing sequence numbers and
addon versions. Never replace binaries under an already published release tag.

Future automatic upstream detection may propose a PR/build, never promote itself
to stable. The box must consume our update package, not reflash its whole disk.
LibreELEC applies update packages on restart; no forced restart while playing.

## USB/install boundary

Do not write a disk from this workflow. Re-identify the removable USB immediately
before writing; the image write destroys its existing partitions. Test USB boot
before replacing Android, and resolve Android backup/erase consent separately.
Never write an installer image over a mounted running Android system via ADB.

## References

- https://wiki.libreelec.tv/development/build-basics
- https://wiki.libreelec.tv/support/update
- https://github.com/LibreELEC/LibreELEC.tv/tree/12.2.1
- https://github.com/LibreELEC/service.libreelec.settings
