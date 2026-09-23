# Stremio bridge pilot

`plugin.video.stremioelec` is a separate Kodi video addon, not part of the skin package. It uses only Kodi Python APIs and the Python standard library. Package/install this folder separately; putting it inside the skin ZIP does not install it.

Current scope: browse catalogs without mandatory filters, map metadata to Kodi artwork/info, list series episodes, and expose direct HTTP(S) streams from the same manifest as playable Kodi items. The default Cinemeta manifest is metadata-only; it will not supply movie streams. HTTP request timeout is 15 seconds and response limit is 8 MiB. Provider URLs and errors are not logged because configured manifests can contain secrets.

Open Videos → Add-ons → StremioELEC catalogs. The manifest can be set in addon settings. Account credentials are not requested. No profile/library state is modified.

An opt-in first Home widget is available for the default Cinemeta manifest: enable the skin setting `StremioCatalogPilot` with Kodi's `Skin.SetBool(StremioCatalogPilot)` built-in. Disable with `Skin.Reset(StremioCatalogPilot)`. This pilot expects Cinemeta's `movie/top` catalog; custom manifests should be browsed through the addon root. Existing widget sources remain until Kodi runtime acceptance.

Not implemented: QR login, account addon import, cross-addon metadata/stream aggregation, search/filter/pagination UI, subtitle providers, progress sync, torrent service, DRM, or streams requiring proxy headers. Catalog-only addons do not guarantee metadata resources. Runtime acceptance must cover these failures without confusing them with successful playback.

Required before removing TMDB/widgets: install pilot on a compatible Kodi instance, validate Home focus/details/episodes, play an authorized direct HTTP sample with audio, then implement account-driven routes and migrate all remaining TMDB references. No Kodi installation was available on the development Mac during the initial source check.

## Offline pilot bundle

`build_bundle.py --inputs INPUT_DIRECTORY --output OUTPUT_DIRECTORY` packages the local skin and bridge and resolves mandatory dependencies recursively from actual ZIP manifests. Inputs are `bingie.xml` (Bingie Omega repository index), `kodi.xml.gz` (official Kodi Omega index), and `builtins/*/addon.xml` extracted from the target LibreELEC image. Use a fresh output directory for a new dependency snapshot.

The builder checks archive paths, CRC, addon identity and dependency minimum versions. It produces a version/source/hash inventory, `SHA256SUMS` and a dependency-first `INSTALL.md`. Hashes are local integrity records, not upstream signatures. This does not install anything, rewrite an image, or validate runtime compatibility. No update repository addon is bundled. Dependencies are retained until the Stremio replacement passes runtime acceptance.
