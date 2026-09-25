"""Development-only live reload service for the StremioELEC Kodi skin."""
import json
import os
import time

import xbmc
import xbmcaddon
import xbmcvfs

WATCH_IDS = ("skin.stremio", "plugin.video.stremioelec")
WATCH_EXTENSIONS = {
    ".xml", ".py", ".json", ".po", ".png", ".jpg", ".jpeg",
    ".webp", ".gif", ".ttf", ".otf",
}
SKIP_DIRS = {".git", "__pycache__", "vendor", ".idea", ".vscode"}
POLL_SECONDS = 0.75


def log(message):
    xbmc.log("[StremioELEC Dev] " + message, xbmc.LOGINFO)


def rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        payload["params"] = params
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(payload))).get("result")
    except Exception:
        return None


def addon_path(identity):
    try:
        raw = xbmcaddon.Addon(identity).getAddonInfo("path")
        return os.path.realpath(xbmcvfs.translatePath(raw))
    except Exception:
        return None


def snapshot(root):
    state = {}
    if not root or not os.path.isdir(root):
        return state
    for base, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in files:
            suffix = os.path.splitext(name)[1].lower()
            if suffix not in WATCH_EXTENSIONS and name != "addon.xml":
                continue
            path = os.path.join(base, name)
            try:
                info = os.stat(path)
                state[path] = (info.st_mtime_ns, info.st_size)
            except OSError:
                pass
    return state


def ensure_stremio_skin():
    if not xbmc.getCondVisibility("System.HasAddon(skin.stremio)"):
        log("skin.stremio is not installed")
        return
    current = rpc("Settings.GetSettingValue", {"setting": "lookandfeel.skin"}) or {}
    if current.get("value") == "skin.stremio":
        return
    result = rpc(
        "Settings.SetSettingValue",
        {"setting": "lookandfeel.skin", "value": "skin.stremio"},
    )
    if result in ("OK", True, None):
        log("Switching Kodi to skin.stremio")
        xbmc.executebuiltin("ReloadSkin()")


monitor = xbmc.Monitor()
ensure_stremio_skin()
roots = [path for path in (addon_path(i) for i in WATCH_IDS) if path]
states = {root: snapshot(root) for root in roots}
log("Watching: " + ", ".join(roots))

while not monitor.waitForAbort(POLL_SECONDS):
    changed = False
    for root in roots:
        current = snapshot(root)
        if current != states[root]:
            states[root] = current
            changed = True
    if changed:
        log("Source change detected; reloading skin")
        xbmc.executebuiltin("ReloadSkin()")
        time.sleep(0.35)
