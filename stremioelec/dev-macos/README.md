# StremioELEC macOS live preview

This folder turns a normal Kodi 21 installation on macOS into a fast
StremioELEC skin-development preview.

## What it links

- `skin.stremio` -> the repository's live skin source
- `plugin.video.stremioelec` -> the repository's live integration plugin
- `service.stremioelec.devwatcher` -> reloads the skin after source changes
- `F5` -> manual `ReloadSkin()` fallback
- `F6` -> jump back to Home

No StremioELEC image build is required for skin/UI work.

## Setup

From the repository checkout:

```sh
git switch stremioelec/n60-image-pipeline
./stremioelec/dev-macos/setup.sh
```

Restart Kodi after the first setup so it discovers the linked addons.
The dev watcher switches to `skin.stremio` once on startup and then watches
the skin/plugin source for XML, Python, JSON, language, font and image changes.

macOS Kodi userdata lives under
`~/Library/Application Support/Kodi`.

This preview is intended for skin, navigation, dialogs, catalogs and Python
integration. Hardware/LibreELEC-specific behavior still needs final N60 testing.
