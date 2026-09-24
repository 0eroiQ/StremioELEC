# Built-in StremioELEC skin

Addon identity: `skin.stremio`; display name: `StremioELEC`.
The GitHub repository URL remains unchanged; renaming an addon does not rename
the hosted repository or remove Bingie/GPL attribution.

Portable macOS packaging pilot (Kodi stopped):
1. `migrate_skin_id.py` copies skin preferences and skin-specific shortcuts to
   the new ID, updates the bridge shortcut paths and current skin setting,
   then moves the old skin outside the scanned addon directories.
2. `install_builtin_skin.py` audits the mandatory dependency closure. With
   `--apply` it bundles missing dependencies, sets `lookandfeel.skin` default
   and the required addon-manifest entry to `skin.stremio`, and moves Estuary
   outside Kodi into a recoverable backup.

Only addon code is bundled, never addon_data or account tokens. The portable
copy remains as a development override of the built-in skin. Future deployment
must keep that override and the packaged copy consistent. These scripts are
one-time guarded operations, not an idempotent updater.

This modifies the resources of the isolated test .app, not compiled Kodi C++,
the normal Mac Kodi installation, the N60, a LibreELEC image, or a release.
App-bundle modification is not a newly signed/notarized distribution. A real
LibreELEC build still needs equivalent packaging and fresh-profile validation.
