#!/bin/zsh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
KODI_DATA="$HOME/Library/Application Support/Kodi"
ADDONS="$KODI_DATA/addons"
USERDATA="$KODI_DATA/userdata"
BACKUPS="$KODI_DATA/stremioelec-dev-backups"

SKIN_SRC="$ROOT/skin.stremio"
PLUGIN_SRC="$ROOT/skin.stremio/integration/plugin.video.stremioelec"
WATCHER_SRC="$HERE/service.stremioelec.devwatcher"

fail() {
  echo "StremioELEC dev setup: $*" >&2
  exit 1
}

[[ -f "$SKIN_SRC/addon.xml" ]] || fail "skin.stremio source not found. Checkout stremioelec/n60-image-pipeline."
[[ -f "$PLUGIN_SRC/addon.xml" ]] || fail "plugin.video.stremioelec source not found."
[[ -f "$WATCHER_SRC/addon.xml" ]] || fail "dev watcher source not found."

mkdir -p "$ADDONS" "$USERDATA/keymaps" "$BACKUPS"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUPS/$STAMP"

link_addon() {
  local name="$1"
  local source="$2"
  local target="$ADDONS/$name"

  if [[ -L "$target" && "$(readlink "$target")" == "$source" ]]; then
    echo "Already linked: $name"
    return
  fi

  if [[ -e "$target" || -L "$target" ]]; then
    mkdir -p "$BACKUP"
    mv "$target" "$BACKUP/$name"
    echo "Backed up existing $name -> $BACKUP/$name"
  fi

  ln -s "$source" "$target"
  echo "Linked $name -> $source"
}

link_addon "skin.stremio" "$SKIN_SRC"
link_addon "plugin.video.stremioelec" "$PLUGIN_SRC"
link_addon "service.stremioelec.devwatcher" "$WATCHER_SRC"

cat > "$USERDATA/keymaps/stremioelec-dev.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<keymap>
  <global>
    <keyboard>
      <f5>ReloadSkin()</f5>
      <f6>ActivateWindow(Home)</f6>
    </keyboard>
  </global>
</keymap>
XML

echo "Installed Kodi keymap: F5 reload skin, F6 Home"

if [[ -d "/Applications/Kodi.app" ]]; then
  VERSION="$(defaults read /Applications/Kodi.app/Contents/Info CFBundleShortVersionString 2>/dev/null || true)"
  [[ -n "$VERSION" ]] && echo "Kodi detected: $VERSION"
  echo "Restarting Kodi so linked addons are discovered..."
  osascript -e 'tell application "Kodi" to quit' >/dev/null 2>&1 || true
  sleep 1
  open -a Kodi
else
  echo "Kodi.app was not found in /Applications."
  echo "Install Kodi 21 for macOS, then run this setup again."
fi

echo
echo "StremioELEC live preview is configured."
echo "Edit files under: $SKIN_SRC"
echo "The dev watcher reloads the skin automatically; F5 is the manual fallback."
