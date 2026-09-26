"""Internal Kodi bridge into the StremioELEC SYSTEM runtime."""
from pathlib import Path
import runpy
import sys

CORE = Path('/usr/lib/stremioelec/plugin.video.stremioelec')
TARGET = CORE / 'default.py'
if not TARGET.is_file():
    raise RuntimeError('StremioELEC system runtime is missing')
sys.path.insert(0, str(CORE))
runpy.run_path(str(TARGET), run_name='__main__')
