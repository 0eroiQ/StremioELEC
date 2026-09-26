"""Runtime dependency guard for the Stremio-first skin."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REMOVED = (
    'plugin.video.themoviedb.helper',
    'plugin.video.tmdb.bingie.helper',
    'script.bingie.helper',
    'script.bingie.widgets',
    'script.bingie.toolbox',
    'script.skinshortcuts',
    'script.skin.helper.colorpicker',
)


class SkinDependencyTests(unittest.TestCase):
    def test_no_removed_addon_executes_anywhere_in_skin(self):
        roots = (ROOT / '1080i', ROOT / 'extras', ROOT / 'shortcuts')
        offenders = []
        for base in roots:
            if not base.exists():
                continue
            for path in base.rglob('*'):
                if not path.is_file():
                    continue
                text = path.read_text(errors='ignore')
                for line_no, line in enumerate(text.splitlines(), 1):
                    low = line.lower()
                    if not any(addon in low for addon in REMOVED):
                        continue
                    if any(token in line for token in ('plugin://', 'RunScript(', 'ActivateWindow(')):
                        offenders.append(f'{path.relative_to(ROOT)}:{line_no}: {line.strip()}')
        self.assertEqual(offenders, [], '\n'.join(offenders))

    def test_removed_bingie_widget_backend_is_gone(self):
        text = (ROOT / '1080i/IncludesPaths.xml').read_text()
        self.assertNotIn('script.bingie.widgets', text)

    def test_media_flags_use_native_kodi_mpaa(self):
        text = (ROOT / '1080i/IncludesMediaFlags.xml').read_text()
        self.assertNotIn('TMDbBingieHelper.Player.mpaa', text)
        self.assertIn('videoplayer.mpaa', text.lower())

    def test_legacy_shortcut_editor_redirects_to_supported_settings(self):
        text = (ROOT / '1080i/script-skinshortcuts.xml').read_text()
        self.assertIn('ReplaceWindow(1198)', text)
        for addon in REMOVED:
            self.assertNotIn(addon, text.lower())

    def test_music_youtube_button_is_optional(self):
        text = (ROOT / '1080i/DialogMusicInfo.xml').read_text()
        self.assertIn('System.HasAddon(plugin.video.youtube)', text)
        self.assertIn('plugin://plugin.video.youtube/search/', text)


if __name__ == '__main__':
    unittest.main()
