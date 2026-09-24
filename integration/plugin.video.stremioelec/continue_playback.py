"""Exact saved-episode labels and bounded resume offsets, without title guessing."""
import math
import re


def resume_seconds(value):
    try:
        seconds = float(value) / 1000
        return seconds if math.isfinite(seconds) and 0 < seconds < 604800 else 0
    except (TypeError, ValueError):
        return 0


def button_label(saved):
    state = saved.get('state') or {}
    verb = 'Resume' if resume_seconds(state.get('timeOffset')) else 'Play'
    if saved.get('type') == 'series':
        match = re.fullmatch(re.escape(saved['_id']) + r':(\d+):(\d+)', str(state.get('video_id', '')))
        if match and int(match[2]) > 0:
            return '{} Season {}: Episode {}'.format(verb, int(match[1]), int(match[2]))
    return verb
