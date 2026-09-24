import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from continue_playback import button_label, resume_seconds


class ContinueTests(unittest.TestCase):
    def test_saved_episode_and_offset(self):
        saved = {'_id': 'tt123', 'type': 'series', 'state': {'video_id': 'tt123:1:3', 'timeOffset': 125000}}
        self.assertEqual(button_label(saved), 'Resume Season 1: Episode 3')
        self.assertEqual(resume_seconds(125000), 125)
        saved['state']['timeOffset'] = 0
        self.assertEqual(button_label(saved), 'Play Season 1: Episode 3')

    def test_no_guessed_episode(self):
        self.assertEqual(button_label({'_id': 'tt123', 'type': 'series', 'state': {'video_id': 'tt999:1:3'}}), 'Play')

    def test_invalid_offsets(self):
        for value in (None, 'bad', 'nan', 'inf', -1, 999999999999):
            self.assertEqual(resume_seconds(value), 0)
