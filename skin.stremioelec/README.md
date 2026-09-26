# Stremio skin

StremioELEC's independent Kodi skin, based on [Bingie by matke](https://github.com/matke-84/skin.bingie). Original credits and GPL-2.0 licensing are retained. This is not an official Stremio product.

The display name is now **Stremio skin**. The internal `skin.bingie` identifier is temporarily retained for compatibility with existing paths and helper scripts. A separate package identifier and update feed must be introduced before distributing alongside upstream Bingie.

Stremio login, account synchronization and addon integration are planned, not implemented yet.

## Dependency review

No dependencies have been removed in this initial branding change.

| Area | Proposed action | Source evidence / prerequisite |
| --- | --- | --- |
| Search autocomplete | Remove if basic search is sufficient | `1080i/Custom_1109_BingieSearch.xml` calls `plugin.program.autocompletion`; remove its suggestion UI and settings first. |
| Studio icon packs | Optional removal | Replace studio texture references with text before removing `resource.images.studios.coloured`. |
| Trailer integrations | Remove optional YouTube / IMDb integrations if unused | References exist throughout `1080i` and `shortcuts/template.xml`; these are not mandatory imports in addon.xml. |
| Music, weather, games, pictures, PVR | Hide unused navigation first | Includes, Kodi dialogs and hubs are shared; do not delete all corresponding windows blindly. Keep PVR if live TV is wanted. |
| TMDB catalogs, search, detail actions | Replace with the Stremio bridge | `1080i/IncludesPaths.xml` and other windows use `plugin.video.tmdb.bingie.helper`; removing its import alone breaks those paths. |
| Library widgets | Replace incrementally | `script.bingie.widgets` supplies My List, recent, recommendations and in-progress rows in `1080i/IncludesPaths.xml`. |
| Menu construction | Retain initially | `script.skinshortcuts`, `shortcuts/template.xml` and `1080i/script-skinshortcuts.xml` construct menus/widgets. |
| Helper and toolbox | Audit and retain needed actions | `script.bingie.helper` handles library/detail actions; toolbox is used by skin configuration and `DialogSubtitles.xml`. |

Preserve playback controls, subtitle/audio dialogs, core Kodi settings, profile controls and remote focus. Account-backed lists and progress require a separate Stremio integration component. No runtime compatibility or dependency-free installation is claimed by this source review.
