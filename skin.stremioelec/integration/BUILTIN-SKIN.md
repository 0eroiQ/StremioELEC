# StremioELEC Skin packaging

Addon identity: skin.stremioelec
Display name: StremioELEC Skin

The same skin package supports two distribution modes.

## StremioELEC image

The image builder installs skin.stremioelec into
/usr/share/kodi/addons/skin.stremioelec, changes Kodi's built-in
lookandfeel.skin default and required-addon manifest from skin.estuary to
skin.stremioelec, and removes Estuary from the generated disposable image
rootfs. Fresh StremioELEC installations therefore boot directly into
StremioELEC Skin.

Before Kodi starts, stremioelec/bootstrap.py also migrates an existing
test.7-era profile from the legacy skin.stremio ID to skin.stremioelec.
Preferences and skin-specific shortcut files are retained, while an old
user-installed code override is moved outside Kodi's addon scan path.

## Existing Kodi installation

The portable repository publishes skin.stremioelec as a normal Kodi skin
addon together with StremioELEC Core. Installing StremioELEC for Kodi does not
silently change lookandfeel.skin. The user's current interface remains active
until they explicitly select StremioELEC Skin in Kodi Interface settings or
use the manual portable control.

The only automatic interface migration is for a profile already using the
legacy skin.stremio ID; that profile is moved to the new addon ID so an
upgrade does not strand Kodi on a missing skin.

## Source and attribution

The GitHub repository remains 0eroiQ/StremioELEC. Renaming the Kodi addon ID
does not rename the repository or remove the inherited Bingie/GPL attribution.
Only addon code is packaged; account data, addon_data, logs, databases and
tokens are never bundled into the skin artifact.
