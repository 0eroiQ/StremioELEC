import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'plugin.video.stremioelec'))
from continue_playback import button_label, resume_seconds, next_series_episode


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

    def test_new_series_starts_first_regular_episode(self):
        videos = [
            {'id': 'tt123:0:1', 'season': 0, 'episode': 1},
            {'id': 'tt123:1:2', 'season': 1, 'episode': 2},
            {'id': 'tt123:1:1', 'season': 1, 'episode': 1},
        ]
        video, resume_ms = next_series_episode(videos, 'tt123')
        self.assertEqual(video['id'], 'tt123:1:1')
        self.assertEqual(resume_ms, 0)

    def test_completed_episode_advances_to_next(self):
        videos = [
            {'id': 'tt123:1:1', 'season': 1, 'episode': 1},
            {'id': 'tt123:1:2', 'season': 1, 'episode': 2},
            {'id': 'tt123:2:1', 'season': 2, 'episode': 1},
        ]
        saved = {'state': {'video_id': 'tt123:1:2', 'timeOffset': 0}}
        video, resume_ms = next_series_episode(videos, 'tt123', saved)
        self.assertEqual(video['id'], 'tt123:2:1')
        self.assertEqual(resume_ms, 0)

    def test_active_episode_resumes_same_episode(self):
        videos = [
            {'id': 'tt123:1:1', 'season': 1, 'episode': 1},
            {'id': 'tt123:1:2', 'season': 1, 'episode': 2},
        ]
        saved = {'state': {'video_id': 'tt123:1:2', 'timeOffset': 125000}}
        video, resume_ms = next_series_episode(videos, 'tt123', saved)
        self.assertEqual(video['id'], 'tt123:1:2')
        self.assertEqual(resume_ms, 125000)
