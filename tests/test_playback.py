"""PortAudio simulado: o envelope vem dos mesmos quadros enviados ao DAC."""
import math
import time
import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import sounddevice as sd

from iaexpert.playback import mouth_level, play_pcm


class FakeOutputStream:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.output = []
        self.finished = False
        FakeOutputStream.instances.append(self)

    def __enter__(self):
        callback = self.kwargs["callback"]
        frames = 256
        info = SimpleNamespace(
            outputBufferDacTime=100.060,
            currentTime=100.000,
        )
        for _ in range(20):
            outdata = np.zeros((frames, self.kwargs["channels"]), dtype=np.int16)
            try:
                callback(outdata, frames, info, None)
            except sd.CallbackStop:
                self.output.append(outdata.copy())
                self.finished = True
                break
            self.output.append(outdata.copy())
        self.kwargs["finished_callback"]()
        return self

    def __exit__(self, *_args):
        return False


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        FakeOutputStream.instances.clear()

    def test_envelope_tracks_actual_pcm(self):
        self.assertEqual(mouth_level(np.zeros(256, dtype=np.int16)), 0)
        self.assertGreater(mouth_level(np.full(256, 5000, np.int16)), .7)

    def test_output_frames_are_identical_to_envelope_source(self):
        samples = np.concatenate((
            np.full(256, 6000, dtype=np.int16),
            np.zeros(256, dtype=np.int16),
            np.full(256, -3500, dtype=np.int16),
        ))
        events = []
        with patch("iaexpert.playback.sd.OutputStream", side_effect=FakeOutputStream):
            play_pcm(samples, 16000, Event(), lambda value, when: events.append((value, when)))
        stream = FakeOutputStream.instances[-1]
        rendered = np.concatenate(stream.output)[:, 0]
        self.assertTrue(stream.finished)
        np.testing.assert_array_equal(rendered[:len(samples)], samples)
        self.assertEqual(stream.kwargs["dtype"], "int16")
        self.assertGreater(events[0][0], .7)
        self.assertEqual(events[1][0], 0)
        self.assertGreater(events[2][0], .5)
        self.assertEqual(events[-1][0], 0)
        # Timestamp contém o atraso DAC (60 ms), em vez de usar relógio arbitrário.
        self.assertGreater(events[0][1], time.monotonic() - .1)

    def test_cancelled_before_output_never_opens_device(self):
        stop = Event()
        stop.set()
        with patch("iaexpert.playback.sd.OutputStream") as output:
            play_pcm(np.ones(300, np.int16), 16000, stop)
            output.assert_not_called()

    def test_stereo_supported_without_downmix_side_effects(self):
        stereo = np.full((128, 2), 2000, np.int16)
        with patch("iaexpert.playback.sd.OutputStream", side_effect=FakeOutputStream):
            play_pcm(stereo, 22050, Event())
        self.assertEqual(FakeOutputStream.instances[-1].kwargs["channels"], 2)


if __name__ == "__main__":
    unittest.main()
