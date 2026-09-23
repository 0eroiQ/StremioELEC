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
PRs/builds cannot publish a release or modify the stable feed.

Outputs: `.img.gz` installer, `.tar` update candidate, `SHA256SUMS`, provenance,
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
- Independent OS and skin/addon ON/OFF controls and the verified stable OS feed
  are **not implemented by this first build workflow**. Do not label them ready.
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
