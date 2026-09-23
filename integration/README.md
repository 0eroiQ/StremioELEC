# Stremio bridge pilot

## Home view modes

Stremio view always uses moving focus and hides the moving-focus and spotlight switches. Original Bingie retains both switches and their saved values. The fixed-frame render paths use an effective view expression, not a destructive reset of the user's original preference.

Skin settings / Home offers Stremio view and Original Bingie view. Both currently share the original Bingie layout and all widget/content settings. Stremio view is the starting variant with spotlight hidden; it does not overwrite the original DisableSpotlightContent preference. Switching back restores original behavior. Other preferences are shared, not separate per-view profiles. Only newly initialized profiles default to Stremio view; existing profiles keep their selection. The view switch does not enable the Stremio catalog pilot or change content providers.

`plugin.video.stremioelec` is a separate Kodi video addon, not part of the skin package. It uses only Kodi Python APIs and the Python standard library. Package/install this folder separately; putting it inside the skin ZIP does not install it.

Current scope: browse catalogs without mandatory filters, map metadata to Kodi artwork/info, list series episodes, and expose direct HTTP(S) streams from the same manifest as playable Kodi items. The default Cinemeta manifest is metadata-only; it will not supply movie streams. HTTP request timeout is 15 seconds and response limit is 8 MiB. Provider URLs and errors are not logged because configured manifests can contain secrets.

Open Videos → Add-ons → StremioELEC catalogs. The manual manifest can be set in addon settings. Version 0.2 adds Connect Stremio account: approve local token storage, then open the displayed official link on another device. No password is entered in Kodi. Sign-in polls every five seconds for up to five minutes and can be cancelled. It imports the account addon collection read-only; Refresh account addons repeats the import. Disconnect this device clears only the local session/cache, not the remote session or account. No library/progress writes occur.

The token and configured addon URLs live in profile addon_data/plugin.video.stremioelec/account.json, written atomically with owner-only permissions on macOS/Linux. They are NOT encrypted and must be excluded from shared Kodi backups and diagnostics. Tokens are sent only to the official Stremio API over HTTPS; redirects are rejected. Plugin navigation uses hashed provider IDs instead of configured manifest URLs. Imported HTTPS manifests are supported; unsupported transports are counted and skipped. Account import does not automatically request every provider: opening a provider fetches its catalog. Each provider's catalogs remain separate until cross-addon routing is implemented.

Protocol references: official Stremio/stremio-core src/models/link.rs and src/types/api/{request,response,fetch_api}.rs. Live anonymous smoke test verified official link creation and pending state; account authorization and authenticated import still require user runtime acceptance. The first sign-in UI displays a link, not a QR code.

An opt-in first Home widget is available for the default Cinemeta manifest: enable the skin setting `StremioCatalogPilot` with Kodi's `Skin.SetBool(StremioCatalogPilot)` built-in. Disable with `Skin.Reset(StremioCatalogPilot)`. This pilot expects Cinemeta's `movie/top` catalog; custom manifests should be browsed through the addon root. Existing widget sources remain until Kodi runtime acceptance.

Not implemented: QR rendering, cross-addon metadata/stream aggregation, search/filter/pagination UI, subtitle providers, progress sync, torrent service, DRM, or streams requiring proxy headers. Catalog-only addons do not guarantee metadata resources. Runtime acceptance must cover these failures without confusing them with successful playback.

Required before removing TMDB/widgets: install pilot on a compatible Kodi instance, validate Home focus/details/episodes, play an authorized direct HTTP sample with audio, then implement account-driven routes and migrate all remaining TMDB references. No Kodi installation was available on the development Mac during the initial source check.

## Offline pilot bundle

`build_bundle.py --inputs INPUT_DIRECTORY --output OUTPUT_DIRECTORY` packages the local skin and bridge and resolves mandatory dependencies recursively from actual ZIP manifests. Inputs are `bingie.xml` (Bingie Omega repository index), `kodi.xml.gz` (official Kodi Omega index), and `builtins/*/addon.xml` extracted from the target LibreELEC image. Use a fresh output directory for a new dependency snapshot.

The builder checks archive paths, CRC, addon identity and dependency minimum versions. It produces a version/source/hash inventory, `SHA256SUMS` and a dependency-first `INSTALL.md`. Hashes are local integrity records, not upstream signatures. This does not install anything, rewrite an image, or validate runtime compatibility. No update repository addon is bundled. Dependencies are retained until the Stremio replacement passes runtime acceptance.
