# Copyright (C) 2026 Michael Stone
# SPDX-License-Identifier: GPL-2.0-or-later
import contextlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch

BLURAY = Path(__file__).resolve().parents[1] / "scripts" / "bluray-archive"
module = runpy.run_path(str(BLURAY))
extract = module["extract"]
verify = module["verify"]
completeness = module["completeness"]
source_details = module["source_details"]
globals_ = extract.__globals__


class BluRayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "disc.iso"
        self.source.write_bytes(b"disc")
        self.identity = source_details(self.source)[1]
        self.out = self.root / "archive"
        self.out.mkdir()
        self.playlist = {"id": 1, "duration": 10, "angles": 1, "chapters": [0, 5],
                         "clips": [{"id": "00001", "still_mode": 0,
                                    "interactive_graphics": 0, "secondary_audio": 0,
                                    "secondary_video": 0, "streams": [
                                        {"type": "video", "pid": 4113, "coding": 2}]}]}
        self.media = {"format": {"duration": "10.01"},
                      "chapters": [{"start_time": "0"}, {"start_time": "5"}],
                      "streams": [{"codec_type": "video", "codec_name": "mpeg2video"}]}

    def ffmpeg(self, command, **kwargs):
        Path(command[-1]).write_bytes(b"complete")
        return subprocess.CompletedProcess(command, 0)

    def verify(self, playlists):
        with contextlib.redirect_stdout(io.StringIO()):
            status = verify(self.source, self.out, self.identity, playlists, {})
        files = sorted(self.out.glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
        return status, json.loads(files[-1].read_text())

    def test_complete_resume_missing_unexpected_and_modified(self):
        with patch.dict(globals_, {"probe": lambda path: self.media, "check_packet_timestamps": lambda path: None}), \
             patch.object(subprocess, "run", side_effect=self.ffmpeg) as ffmpeg:
            self.assertEqual(extract(self.source, self.out, self.identity, {1: self.playlist}), 0)
            self.assertEqual(extract(self.source, self.out, self.identity, {1: self.playlist}), 0)
            self.assertEqual(ffmpeg.call_count, 1)
            self.assertEqual(self.verify({1: self.playlist})[0], 0)
            path = self.out / "titles/playlist_00001.mkv"
            path.write_bytes(b"changed")
            status, report = self.verify({1: self.playlist, 2: dict(self.playlist, id=2)})
            self.assertEqual(status, 1)
            self.assertEqual(report["summary"]["failed"], 2)
            path.unlink()
            (self.out / "titles/playlist_99999.mkv").write_bytes(b"extra")
            _, report = self.verify({1: self.playlist})
            self.assertEqual(report["summary"]["failed"], 2)

    def test_incomplete_media_and_wrong_source_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duration mismatch"):
            completeness(self.playlist, dict(self.media, format={"duration": "1"}))
        with self.assertRaisesRegex(ValueError, "Chapter mismatch"):
            completeness(self.playlist, dict(self.media, chapters=[]))
        with self.assertRaisesRegex(ValueError, "Stream .*mismatch"):
            completeness(self.playlist, dict(self.media, streams=[]))
        with patch.dict(globals_, {"probe": lambda path: self.media, "check_packet_timestamps": lambda path: None}), \
             patch.object(subprocess, "run", side_effect=self.ffmpeg):
            extract(self.source, self.out, self.identity, {1: self.playlist})
            self.source.write_bytes(b"other")
            status = verify(self.source, self.out, source_details(self.source)[1], {1: self.playlist}, {})
            self.assertEqual(status, 1)

    def test_failed_playlist_does_not_stop_next_playlist(self):
        calls = []
        def ffmpeg(command, **kwargs):
            calls.append(command)
            if command[command.index("-playlist") + 1] == "1":
                return subprocess.CompletedProcess(command, 1)
            return self.ffmpeg(command, **kwargs)
        with patch.dict(globals_, {"probe": lambda path: self.media, "check_packet_timestamps": lambda path: None}), \
             patch.object(subprocess, "run", side_effect=ffmpeg):
            failures = extract(self.source, self.out, self.identity,
                               {1: self.playlist, 2: dict(self.playlist, id=2)})
        self.assertEqual(failures, 1)
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.out / "titles/playlist_00001.mkv").exists())
        self.assertTrue((self.out / "titles/playlist_00002.mkv").exists())
        self.assertIn("FFmpeg failed", (self.out / "logs/playlist_00001.log").read_text())
        with patch.dict(globals_, {"probe": lambda path: self.media, "check_packet_timestamps": lambda path: None}):
            _, report = self.verify({1: self.playlist})
        failed = next(entry for entry in report["files"] if entry["playlist"] == 1)
        self.assertIn("FFmpeg failed", failed["extraction_error"])

    def test_authored_language_and_stream_pids_are_preserved(self):
        audio = {"type": "audio", "pid": 4352, "coding": 129, "language": "eng"}
        clip = dict(self.playlist["clips"][0], streams=self.playlist["clips"][0]["streams"] + [audio])
        playlist = dict(self.playlist, clips=[clip])
        audio_media = dict(self.media, streams=self.media["streams"] + [
            {"codec_type": "audio", "codec_name": "ac3", "tags": {"language": "eng"}}])
        with patch.dict(globals_, {"probe": lambda path: audio_media, "check_packet_timestamps": lambda path: None}), \
             patch.object(subprocess, "run", side_effect=self.ffmpeg) as ffmpeg:
            self.assertEqual(extract(self.source, self.out, self.identity, {1: playlist}), 0)
        command = ffmpeg.call_args.args[0]
        self.assertIn("0:i:0x1100", command)
        self.assertIn("language=eng", command)
        audio_media["streams"][-1]["tags"]["language"] = "fra"
        with self.assertRaisesRegex(ValueError, "Stream mismatch"):
            completeness(playlist, audio_media)

    def test_duplicate_audio_timestamp_fails_packet_check(self):
        class FakeProbe:
            def __init__(self):
                self.stdout = io.StringIO("1,334.016000\n1,334.016000\n")
            def terminate(self):
                pass
            def wait(self):
                return 0
        with patch.object(subprocess, "Popen", return_value=FakeProbe()):
            with self.assertRaisesRegex(ValueError, "Non-increasing DTS"):
                module["check_packet_timestamps"](self.source)

    def test_boundary_retry_requires_matching_source_packets(self):
        video = {"type": "video", "pid": 4113, "coding": 2}
        audio = {"type": "audio", "pid": 4352, "coding": 129, "language": "eng"}
        first = {"id": "00000", "start": 0, "in": 4196.4, "out": 4530.500422222,
                 "still_mode": 0, "interactive_graphics": 0, "secondary_audio": 0,
                 "secondary_video": 0, "streams": [video, audio]}
        second = {"id": "00011", "start": 334.100422222, "in": 600, "out": 601.001,
                  "still_mode": 0, "interactive_graphics": 0, "secondary_audio": 0,
                  "secondary_video": 0, "streams": [video]}
        playlist = {"id": 1, "duration": 335.101422222, "angles": 1,
                    "chapters": [0, 334.100422222], "clips": [first, second]}
        media = {"format": {"duration": "335.101"},
                 "chapters": [{"start_time": "0"}, {"start_time": "334.100"}],
                 "streams": [{"codec_type": "video", "codec_name": "mpeg2video"},
                             {"codec_type": "audio", "codec_name": "ac3",
                              "tags": {"language": "eng"}}]}
        discontinuity = module["TimestampDiscontinuity"]("Non-increasing DTS")
        with patch.dict(globals_, {"probe": lambda path: media}), \
             patch.dict(globals_, {"check_packet_timestamps": unittest.mock.Mock(
                 side_effect=[discontinuity, None])}), \
             patch.dict(globals_, {"compare_boundary_packets": lambda *args: {"video": 4, "audio": 5}}), \
             patch.object(subprocess, "run", side_effect=self.ffmpeg) as ffmpeg:
            self.assertEqual(extract(self.source, self.out, self.identity, {1: playlist}), 0)
        self.assertEqual(ffmpeg.call_count, 2)
        retry = ffmpeg.call_args.args[0]
        self.assertIn("-copyts", retry)
        self.assertIn("-bsf:v", retry)
        receipt = json.loads((self.out / "titles/playlist_00001.mkv.receipt.json").read_text())
        self.assertEqual(receipt["timestamp_correction"]["packets_checked"], {"video": 4, "audio": 5})
        self.assertIn("video wrap adjustment", (self.out / "logs/playlist_00001.log").read_text())

        self.source.write_bytes(b"other disc")
        other_identity = source_details(self.source)[1]
        with patch.dict(globals_, {"probe": lambda path: media}), \
             patch.dict(globals_, {"check_packet_timestamps": unittest.mock.Mock(
                 side_effect=[discontinuity, None])}), \
             patch.dict(globals_, {"compare_boundary_packets": unittest.mock.Mock(
                 side_effect=ValueError("audio packet differs from source"))}), \
             patch.object(subprocess, "run", side_effect=self.ffmpeg):
            self.assertEqual(extract(self.source, self.out, other_identity, {1: playlist}), 1)
        self.assertEqual(json.loads(
            (self.out / "titles/playlist_00001.mkv.receipt.json").read_text())["source"], self.identity)

    def test_boundary_correction_rejects_other_stream_layouts(self):
        streams = module["expected_streams"](self.playlist)
        self.assertIsNone(module["boundary_correction"](self.playlist, streams))

    def test_boundary_packet_comparison_checks_hashes_and_mapped_timestamps(self):
        class FakeProbe:
            def __init__(self, lines):
                self.stdout = io.StringIO(lines)

            def poll(self):
                return 0

            def wait(self):
                return 0

        source_video = (
            "pts_time=4196.400000|dts_time=4196.366633|duration_time=0.033367|data_hash=first\n"
            "pts_time=96043.717689|dts_time=96043.684322|duration_time=0.033367|data_hash=second\n"
        )
        output_video = (
            "pts_time=0.000|dts_time=-0.033|duration_time=0.033|data_hash=first\n"
            "pts_time=334.100|dts_time=334.067|duration_time=0.033|data_hash=second\n"
        )
        source_audio = "pts_time=4196.400|dts_time=4196.400|duration_time=0.032|data_hash=audio\n"
        output_audio = "pts_time=0.000|dts_time=0.000|duration_time=0.032|data_hash=audio\n"
        streams = {("video", 4113): {}, ("audio", 4352): {}}
        correction = {"source_start_seconds": 4196.4, "threshold_seconds": 46091,
                      "jump_seconds": 91513.2172666667}
        probes = [FakeProbe(lines) for lines in (source_video, output_video, source_audio, output_audio)]
        with patch.object(subprocess, "Popen", side_effect=probes):
            counts = module["compare_boundary_packets"](self.source, 1, self.out, streams, correction)
        self.assertEqual(counts, {"video": 2, "audio": 1})

        changed = output_video.replace("data_hash=second", "data_hash=changed")
        with patch.object(subprocess, "Popen", side_effect=[FakeProbe(source_video), FakeProbe(changed)]):
            with self.assertRaisesRegex(ValueError, "video packet 2 differs"):
                module["compare_boundary_packets"](self.source, 1, self.out, streams, correction)

        changed = output_video.replace("pts_time=334.100", "pts_time=334.050")
        with patch.object(subprocess, "Popen", side_effect=[FakeProbe(source_video), FakeProbe(changed)]):
            with self.assertRaisesRegex(ValueError, "video packet 2 pts_time differs"):
                module["compare_boundary_packets"](self.source, 1, self.out, streams, correction)

        with patch.object(subprocess, "Popen", side_effect=[FakeProbe(source_video), FakeProbe("")]):
            with self.assertRaisesRegex(ValueError, "packet count differs"):
                module["compare_boundary_packets"](self.source, 1, self.out, streams, correction)

    def test_incomplete_receipt_keeps_error_visible(self):
        with patch.dict(globals_, {"probe": lambda path: self.media, "check_packet_timestamps": lambda path: None}), \
             patch.object(subprocess, "run", side_effect=self.ffmpeg):
            extract(self.source, self.out, self.identity, {1: self.playlist})
        with patch.dict(globals_, {"probe": lambda path: self.media,
                                  "check_packet_timestamps": lambda path: (_ for _ in ()).throw(ValueError("timestamp discrepancy"))}):
            status, report = self.verify({1: self.playlist})
        self.assertEqual(status, 1)
        self.assertEqual(report["files"][0]["error"], "timestamp discrepancy")
        status, report = self.verify({1: self.playlist})
        self.assertEqual(status, 1)
        self.assertEqual(report["files"][0]["error"], "timestamp discrepancy")

    def test_unsupported_playlist_is_reported(self):
        still = dict(self.playlist["clips"][0], still_mode=2)
        with self.assertRaisesRegex(ValueError, "still"):
            completeness(dict(self.playlist, clips=[still]), self.media)


if __name__ == "__main__":
    unittest.main()
