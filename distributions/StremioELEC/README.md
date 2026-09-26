# StremioELEC distribution overlay

StremioELEC keeps LibreELEC as the upstream operating-system and Kodi base while owning the Stremio-specific product layer here.

## Ownership

This distribution layer owns:

- the built-in StremioELEC Main skin, initially based on Nimbus;
- Stremio Core integration and Kodi-facing bridge code;
- `script.nimbus.helper` compatibility during the Nimbus migration;
- the Portable setup/controller as a Kodi Program addon;
- StremioELEC defaults and first-boot behavior.

## Upstream policy

Do not copy or modify LibreELEC distribution files here unless StremioELEC requires an explicit override. Keep generic hardware/platform changes in their existing project/package layers so LibreELEC updates remain easy to merge.

## Migration stages

1. Package upstream Nimbus 0.1.43 unchanged enough to establish a known-good Kodi boot baseline.
2. Package the Nimbus helper dependency separately.
3. Make the StremioELEC image install and select the Main skin.
4. Connect Stremio Core catalogs, metadata, seasons/episodes, streams and playback to the skin.
5. Replace Nimbus-specific helper behavior incrementally with StremioELEC-owned APIs/properties.
6. Convert Portable to a Kodi Program addon and keep setup/controller logic outside skin XML.

All active development is performed on `stremio-native-ui` until the integration is proven bootable and testable.
