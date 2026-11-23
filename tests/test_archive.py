# Copyright (C) 2026 Michael Stone
# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.machinery
import contextlib
import wave
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'dvd-archive'
loader = importlib.machinery.SourceFileLoader('dvd_archive', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
archive = importlib.util.module_from_spec(spec)
loader.exec_module(archive)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'dvd.iso'
        self.source.write_bytes(b'disc one')
        self.out = self.root / 'output'
        self.titles = self.out / 'titles'
        galleries = patch.object(archive, "confirmed_galleries", return_value={})
        self.galleries = galleries.start()
        self.addCleanup(galleries.stop)
        self.real_compare_dvd = archive.compare_dvd
        comparison = patch.object(archive, "compare_dvd", return_value={
            "verified": True, "method": "whole", "streams": []})
        self.comparison = comparison.start()
        self.addCleanup(comparison.stop)
        self.calls = []
        self.options = {'title_001.mkv': (1, 10.0, [10.0])}
        self.media = {'verified': True, 'duration': 10.0, 'chapter_count': 0}

    def fake_ffmpeg(self, command, **kwargs):
        self.calls.append(command)
        Path(command[-1]).write_bytes(b'completed mkv')
        return subprocess.CompletedProcess(command, 0)

    def extract(self, ffmpeg=None):
        with patch.object(archive, 'inventory', return_value=self.options), \
             patch.object(archive, 'probe_dvd_streams', return_value=[]), \
             patch.object(archive.subprocess, 'run', side_effect=ffmpeg or self.fake_ffmpeg), \
             patch.object(archive, 'probe', return_value=self.media):
            archive.extract(self.source, self.titles, 'title')

    def test_prefix_normalization_and_persistent_legacy_choice(self):
        iso = self.root / 'Home Alone:  Disc 1.ISO'
        iso.touch()
        self.assertEqual(archive.output_prefix(iso), 'home_alone_disc_1')
        disc = self.root / 'Smokey and the Bandit'
        (disc / 'VIDEO_TS').mkdir(parents=True)
        self.assertEqual(archive.output_prefix(disc / 'VIDEO_TS'), 'smokey_and_the_bandit')
        self.assertEqual(archive.output_prefix(iso, 'The Getaway: Disc 2'), 'the_getaway_disc_2')
        with self.assertRaisesRegex(ValueError, '--name'):
            archive.output_prefix(iso, ':::')
        self.assertEqual(archive.archive_prefix(self.titles, iso, create=True), 'home_alone_disc_1')
        self.assertEqual(archive.archive_prefix(self.titles, self.source), 'home_alone_disc_1')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            archive.archive_prefix(self.titles, iso, 'different')
        legacy = self.root / 'legacy'
        legacy.mkdir()
        (legacy / 'title_001.mkv').touch()
        self.assertEqual(archive.archive_prefix(legacy, iso, create=True), '')
        (legacy / 'title_001.mkv').unlink()
        self.assertEqual(archive.archive_prefix(legacy, iso), '')

    def test_prefixed_dvd_extraction_verifies_and_resumes(self):
        with patch.object(archive, 'inventory', return_value=self.options), \
             patch.object(archive, 'probe_dvd_streams', return_value=[]), \
             patch.object(archive.subprocess, 'run', side_effect=self.fake_ffmpeg), \
             patch.object(archive, 'probe', return_value=self.media):
            archive.extract(self.source, self.titles, 'title', 'home_alone')
            archive.extract(self.source, self.titles, 'title', 'home_alone')
        self.assertEqual(len(self.calls), 1)
        self.assertTrue((self.titles / 'home_alone_title_001.mkv.receipt.json').exists())
        output = io.StringIO()
        with patch.object(archive, 'inventory', side_effect=lambda source, kind: self.options if kind == 'title' else {}), \
             patch.object(archive, 'probe', return_value=self.media), contextlib.redirect_stdout(output):
            self.assertEqual(archive.verify(self.source, self.out, 'home_alone'), 0)
        report = json.loads(Path(output.getvalue().strip().removeprefix('Verification result: ')).read_text())
        self.assertEqual(report['files'][0]['file'], 'titles/home_alone_title_001.mkv')

    def test_only_dvd_pcm_streams_use_lossless_pcm_conversion(self):
        streams = [
            {"index": 0, "codec_name": "mpeg2video"},
            {"index": 1, "codec_name": "pcm_dvd", "sample_fmt": "s16"},
            {"index": 2, "codec_name": "ac3"},
            {"index": 3, "codec_name": "pcm_dvd", "sample_fmt": "s32"},
        ]
        with patch.object(archive, 'inventory', return_value=self.options), \
             patch.object(archive, 'probe_dvd_streams', return_value=streams), \
             patch.object(archive.subprocess, 'run', side_effect=self.fake_ffmpeg), \
             patch.object(archive, 'probe', return_value=self.media):
            archive.extract(self.source, self.titles, 'title')
        self.assertEqual(self.calls[0][-9:-3], [
            "-c", "copy", "-c:1", "pcm_s16le", "-c:3", "pcm_s24le",
        ])

    def test_timestamp_failure_retries_but_other_errors_do_not(self):
        reason = 'Non-monotonic DTS'
        calls = []

        def ffmpeg(command, **kwargs):
            calls.append(command)
            if '-xerror' in command:
                kwargs['stderr'].write(reason)
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        with patch.object(archive, 'probe_dvd_streams', return_value=[]), \
             patch.object(archive.subprocess, 'run', side_effect=ffmpeg):
            archive.remux_dvd(self.source, [], self.root / 'out.mkv')
            self.assertEqual(len(calls), 2)
            self.assertNotIn('-xerror', calls[1])
            calls.clear()
            reason = 'read failure'
            with self.assertRaises(subprocess.CalledProcessError):
                archive.remux_dvd(self.source, [], self.root / 'out.mkv')
            self.assertEqual(len(calls), 1)

    def test_timestamp_retry_rejects_other_ffmpeg_errors(self):
        def ffmpeg(command, **kwargs):
            if '-xerror' in command:
                kwargs['stderr'].write('Non-monotonic DTS')
                raise subprocess.CalledProcessError(1, command)
            kwargs['stderr'].write('Error reading input\n')
            return subprocess.CompletedProcess(command, 0)

        with patch.object(archive, 'probe_dvd_streams', return_value=[]), \
             patch.object(archive.subprocess, 'run', side_effect=ffmpeg):
            with self.assertRaisesRegex(ValueError, 'Error reading input'):
                archive.remux_dvd(self.source, [], self.root / 'out.mkv')

    def test_dvd_probe_reads_json_separately_from_stdout_diagnostics(self):
        streams = [{"index": 0, "codec_name": "mpeg2video"}]

        def noisy_probe(command, **kwargs):
            report = Path(command[command.index("-o") + 1])
            report.write_text(json.dumps({"streams": streams}))
            return subprocess.CompletedProcess(command, 0, "libdvdread: CHECK_VALUE failed\n", "")

        with patch.object(archive.subprocess, 'run', side_effect=noisy_probe):
            self.assertEqual(archive.probe_dvd_streams(self.source, ["-f", "dvdvideo"]), streams)

    def inventories(self, source, kind):
        return self.options if kind == 'title' else {'vts_000_lu_001_pgc_001.mkv': []}

    def verify(self):
        output = io.StringIO()
        with patch.object(archive, 'inventory', side_effect=self.inventories), \
             patch.object(archive, 'probe', return_value=self.media), \
             contextlib.redirect_stdout(output):
            status = archive.verify(self.source, self.out)
        path = Path(output.getvalue().strip().removeprefix('Verification result: '))
        return status, json.loads(path.read_text())

    def test_resume_requires_completed_receipt_and_checksum(self):
        self.titles.mkdir(parents=True)
        path = self.titles / 'title_001.mkv'
        path.write_bytes(b'readable but partial legacy output')
        self.extract()
        self.assertEqual(path.read_bytes(), b'completed mkv')
        self.assertEqual(len(self.calls), 1)
        self.extract()
        self.assertEqual(len(self.calls), 1)
        path.write_bytes(b'truncated')
        self.extract()
        self.assertEqual(len(self.calls), 2)
        self.source.write_bytes(b'disc two')
        self.extract()
        self.assertEqual(len(self.calls), 3)

    def test_failed_extraction_does_not_publish_or_destroy_old_file(self):
        self.titles.mkdir(parents=True)
        path = self.titles / 'title_001.mkv'
        path.write_bytes(b'old file')
        def fail(command, **kwargs):
            Path(command[-1]).write_bytes(b'partial')
            raise subprocess.CalledProcessError(1, command)
        with self.assertRaises(subprocess.CalledProcessError):
            self.extract(fail)
        self.assertEqual(path.read_bytes(), b'old file')
        self.assertFalse(archive.receipt_path(path).exists())
        self.assertEqual(list(self.titles.glob('*.part')), [])

    def test_successful_ffmpeg_with_invalid_output_does_not_publish(self):
        with patch.object(archive, 'inventory', return_value=self.options), \
             patch.object(archive, 'probe_dvd_streams', return_value=[]), \
             patch.object(archive.subprocess, 'run', side_effect=self.fake_ffmpeg), \
             patch.object(archive, 'probe', side_effect=ValueError('invalid media')):
            with self.assertRaises(ValueError):
                archive.extract(self.source, self.titles, 'title')
        self.assertFalse((self.titles / 'title_001.mkv').exists())

    def test_menu_discovery_error_propagates(self):
        with patch.object(archive, 'ifo_tool', return_value='dvd-ifo-dump'), \
             patch.object(archive.subprocess, 'run', return_value=subprocess.CompletedProcess(
                 [], 23, '', 'unreadable VTS')):
            with self.assertRaisesRegex(ValueError, '23'):
                archive.extract(self.source, self.out / 'menus', 'menu')
        self.assertFalse((self.out / 'menus').exists())

    def test_menu_inventory_preserves_diagnostics_and_rejects_bad_records(self):
        warning = 'libdvdread: C_ADT nr_of_vobs > available info entries'
        diagnostics = io.StringIO()
        with patch.object(archive, 'ifo_tool', return_value='dvd-ifo-dump'), \
             patch.object(archive, 'run', side_effect=[
                 f'1 1 9\n{warning}\n1 1 10\n',
                 f'{warning}\n1 1 invalid\n',
             ]), contextlib.redirect_stderr(diagnostics):
            self.assertEqual(list(archive.inventory(self.source, 'menu')), [
                'vts_001_lu_001_pgc_009.mkv', 'vts_001_lu_001_pgc_010.mkv',
            ])
            with self.assertRaisesRegex(ValueError, 'Invalid menu candidate'):
                archive.inventory(self.source, 'menu')
        self.assertEqual(diagnostics.getvalue().splitlines(), [warning, warning])

    def test_missing_and_unexpected_files_fail_verification(self):
        self.extract()
        (self.titles / 'title_099.mkv').write_bytes(b'extra')
        status, manifest = self.verify()
        self.assertEqual(status, 1)
        entries = {e['file']: e for e in manifest['files']}
        self.assertTrue(entries['titles/title_001.mkv']['verified'])
        self.assertIn('missing', entries['menus/vts_000_lu_001_pgc_001.mkv']['error'])
        self.assertIn('Unexpected', entries['titles/title_099.mkv']['error'])

    def test_wrong_source_and_modified_output_fail_verification(self):
        self.extract()
        self.source.write_bytes(b'other disc')
        _, manifest = self.verify()
        self.assertFalse(next(e for e in manifest['files'] if e['kind'] == 'title')['verified'])
        self.source.write_bytes(b'disc one')
        (self.titles / 'title_001.mkv').write_bytes(b'half')
        _, manifest = self.verify()
        self.assertFalse(next(e for e in manifest['files'] if e['kind'] == 'title')['verified'])

    def test_complete_archive_verifies(self):
        self.extract()
        # Titles-only disc is valid when menu discovery succeeds with no candidates.
        with patch.object(archive, 'inventory', side_effect=lambda source, kind:
                          self.options if kind == 'title' else {}), \
             patch.object(archive, 'probe', return_value=self.media):
            self.assertEqual(archive.verify(self.source, self.out), 0)
        self.assertEqual(json.loads((self.out / 'manifest.json').read_text())['summary']['failed'], 0)

    def test_repeat_verification_preserves_original_and_collision_results(self):
        self.extract()
        self.verify()
        original = (self.out / 'manifest.json').read_bytes()
        self.source.write_bytes(b'changed')
        with patch.object(archive, 'datetime') as clock:
            clock.now.return_value.strftime.return_value = '2026-01-02-030405-UTC'
            status, result = self.verify()
            self.assertEqual(status, 1)
            self.assertGreater(result['summary']['failed'], 0)
            self.verify()
        self.assertEqual((self.out / 'manifest.json').read_bytes(), original)
        self.assertTrue((self.out / 'verified-2026-01-02-030405-UTC.json').is_file())
        self.assertTrue((self.out / 'verified-2026-01-02-030405-UTC-1.json').is_file())

    def test_actual_title_numbers_are_preserved(self):
        output = "".join(f"Title: {n:02d}, Length: 00:00:10.000 Chapters: 1,\n"
                         "  Chapter: 01, Length: 00:00:10.000\n" for n in (1, 3))
        with patch.object(archive, 'run', return_value=output):
            self.assertEqual(set(archive.inventory(self.source, 'title')),
                             {'title_001.mkv', 'title_003.mkv'})

    def test_short_legacy_title_fails_verification_and_recovers(self):
        self.extract()
        path = self.titles / 'title_001.mkv'
        identity = archive.source_identity(self.source)
        archive.write_receipt(path, identity, archive.digest(path))
        self.options[path.name] = (1, 60.0, [10.0, 50.0])
        status, manifest = self.verify()
        entry = next(e for e in manifest['files'] if e['kind'] == 'title')
        self.assertEqual(status, 1)
        self.assertFalse(entry['verified'])
        self.assertEqual(entry['expected'], {'duration': 60.0, 'chapter_count': 2})
        self.assertEqual(json.loads(archive.receipt_path(path).read_text())['status'], 'incomplete')

        with patch.object(archive, 'inventory', return_value=self.options), \
             patch.object(archive, 'remux_dvd'), \
             patch.object(archive, 'probe', side_effect=[
                 self.media, {'duration': 60.0, 'chapter_count': 2}]), \
             patch.object(archive, 'recover_chapters') as recover:
            archive.extract(self.source, self.titles, 'title')
        recover.assert_called_once()
        self.assertEqual(json.loads(archive.receipt_path(path).read_text())['status'], 'complete')
        self.media = {'verified': True, 'duration': 60.0, 'chapter_count': 2}
        _, manifest = self.verify()
        self.assertTrue(next(e for e in manifest['files'] if e['kind'] == 'title')['verified'])

    def test_complete_runtime_with_missing_chapter_marker_is_incomplete(self):
        check = archive.completeness((1, 60.0, [10.0, 50.0]), {
            'duration': 60.0, 'chapter_count': 1,
        })
        self.assertIn('error', check)

    def test_failed_chapter_retry_preserves_incomplete_title(self):
        self.extract()
        path = self.titles / 'title_001.mkv'
        original = path.read_bytes()
        self.options[path.name] = (1, 60.0, [10.0, 50.0])
        with patch.object(archive, 'inventory', return_value=self.options), \
             patch.object(archive, 'remux_dvd', side_effect=[None, ValueError('bad chapter')]), \
             patch.object(archive, 'probe', return_value=self.media):
            with self.assertRaisesRegex(ValueError, 'chapter 1'):
                archive.extract(self.source, self.titles, 'title')
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(json.loads(archive.receipt_path(path).read_text())['status'], 'incomplete')
        self.assertEqual(set(self.titles.iterdir()), {path, archive.receipt_path(path)})

    def test_gallery_is_pending_and_title_extraction_continues(self):
        gallery = 'title_001.mkv'
        other_title = 'title_002.mkv'
        self.options[other_title] = (2, 10.0, [10.0])
        self.galleries.return_value = {1: {2, 3}}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.extract()
        self.assertIn('dvd-gallery-extract', output.getvalue())
        self.assertFalse((self.titles / gallery).exists())
        self.assertTrue((self.titles / other_title).exists())

        status, manifest = self.verify()
        pending = next(e for e in manifest['files'] if e['kind'] == 'gallery')
        self.assertEqual(status, 1)
        self.assertEqual(pending['status'], 'pending')
        self.assertIn('galleries/title_001', pending['command'])

    def test_gallery_preserves_entry_and_cross_title_navigation(self):
        first = (2, 2, 1, 2, 255, 0, 3)
        second = (1, 2, 1, 2, 255, 0, 3)
        third = (1, 3, 1, 3, 255, 0, 3)

        def trace(source, title, chapter, action):
            if chapter == 1:
                return first, first
            index = [first, second, third].index(next(
                still for still in [first, second, third] if still[:2] == (title, chapter)))
            state = [first, second, third][index]
            target = {"next": [second, third, first][index], "root-menu": "root-menu"}.get(action)
            return state, target

        with patch.object(archive, 'gallery_point', side_effect=trace):
            graph = archive.gallery_graph(self.source, 1, {1: {2, 3}, 2: {2}}, {})
        entry = graph['images'][graph['entry']]
        self.assertEqual(entry['title'], 2)
        self.assertEqual(entry['hold'], 'indefinite')
        self.assertEqual(entry['actions']['next'], {'image': archive.gallery_id(second)})
        self.assertEqual(entry['actions']['root-menu'], {'exit': 'root-menu'})

        identity = archive.source_identity(self.source)
        path = archive.gallery_destination(self.out, 1)
        def png_output(command):
            Path(command[-1]).write_bytes(archive.PNG_HEADER + b'fake payload')
        with patch.object(archive, 'run', side_effect=png_output):
            archive.publish_gallery(self.source, 1, path, identity, graph)
        self.assertEqual(archive.verify_gallery(path, identity, 1, graph), 3)
        manifest_file = path / 'manifest.json'
        manifest = json.loads(manifest_file.read_text())
        manifest['navigation']['images'][graph['entry']]['actions']['next'] = {'image': 'absent'}
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'navigation'):
            archive.verify_gallery(path, identity, 1, graph)
        manifest['navigation'] = graph
        manifest_file.write_text(json.dumps(manifest))
        (path / entry['image']).unlink()
        with self.assertRaises(FileNotFoundError):
            archive.verify_gallery(path, identity, 1, graph)

    def test_comparison_failure_marks_receipt_and_preserves_existing_file(self):
        self.extract()
        path = self.titles / 'title_001.mkv'
        original = path.read_bytes()
        self.comparison.side_effect = archive.SourceComparisonError("packet content differs")
        status, manifest = self.verify()
        entry = next(e for e in manifest['files'] if e['kind'] == 'title')
        self.assertEqual(status, 1)
        self.assertFalse(entry['verified'])
        self.assertIn("packet content differs", entry['source_comparison']['error'])
        receipt = json.loads(archive.receipt_path(path).read_text())
        self.assertEqual(receipt['status'], 'incomplete')
        self.assertFalse(receipt['source_comparison']['verified'])
        with self.assertRaisesRegex(archive.SourceComparisonError, "packet content differs"):
            self.extract()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(json.loads(archive.receipt_path(path).read_text())['status'], 'incomplete')

    def test_missing_packet_and_incomplete_source_are_rejected(self):
        def packet(pts, digest):
            return {"pts_time": str(pts), "dts_time": str(pts),
                    "duration_time": "1", "data_hash": digest}
        source_packets = [packet(0, "a"), packet(1, "b")]
        output_packets = [packet(0, "a")]

        @contextlib.contextmanager
        def records(command, prefix):
            yield iter(source_packets if command[-1] == str(self.source) else output_packets)

        with patch.object(archive, 'probe_records', side_effect=records):
            with self.assertRaisesRegex(archive.SourceComparisonError, 'output ended early'):
                archive.compare_packet_stream(self.source, ['-title', '1'], self.root / 'out.mkv',
                                              0, 0, [None], {}, {None: 2}, 'video')
            output_packets.append(packet(1, "changed"))
            with self.assertRaisesRegex(archive.SourceComparisonError, 'packet content differs'):
                archive.compare_packet_stream(self.source, ['-title', '1'], self.root / 'out.mkv',
                                              0, 0, [None], {}, {None: 2}, 'video')
            output_packets[-1] = packet(1, "b")
            with self.assertRaisesRegex(archive.SourceComparisonError, 'Authored DVD metadata'):
                archive.compare_packet_stream(self.source, ['-title', '1'], self.root / 'out.mkv',
                                              0, 0, [None], {}, {None: 10}, 'video')
            warnings = []
            counts = archive.compare_packet_stream(
                self.source, ['-title', '1'], self.root / 'out.mkv', 0, 0,
                [None], {}, {None: 10}, 'video',
                duration_warnings=warnings, require_duration_match=False)
            self.assertEqual(counts, [2])
            self.assertIn('metadata reports 10.000s', warnings[0])
            output_packets[-1]["pts_time"] = "1.1"
            with self.assertRaisesRegex(archive.SourceComparisonError, 'pts_time differs'):
                archive.compare_packet_stream(self.source, ['-title', '1'], self.root / 'out.mkv',
                                              0, 0, [None], {}, {None: 2}, 'video')
            output_packets[-1] = packet(1, "b")
            source_packets[-1]["flags"] = "K_C"
            with self.assertRaisesRegex(archive.SourceComparisonError, 'packet is corrupt'):
                archive.compare_packet_stream(self.source, ['-title', '1'], self.root / 'out.mkv',
                                              0, 0, [None], {}, {None: 2}, 'video')

    def test_menu_comparison_upgrades_legacy_receipt(self):
        self.extract()
        menu = self.out / 'menus' / 'vts_000_lu_001_pgc_001.mkv'
        menu.parent.mkdir()
        menu.write_bytes(b'menu')
        archive.write_receipt(menu, archive.source_identity(self.source), archive.digest(menu))
        status, manifest = self.verify()
        entry = next(item for item in manifest['files'] if item['kind'] == 'menu')
        self.assertEqual(status, 0)
        self.assertTrue(entry['source_comparison']['verified'])
        receipt = json.loads(archive.receipt_path(menu).read_text())
        self.assertEqual(receipt['version'], 3)
        self.assertTrue(receipt['source_comparison']['verified'])

    def test_chapter_read_comparison_when_whole_title_stops(self):
        video = {"index": 0, "codec_type": "video", "codec_name": "mpeg2video"}
        output = self.root / 'out.mkv'
        media = {"streams": [video], "chapter_starts": [0, 1]}
        title = (1, 2.0, [1.0, 1.0])

        def packet(pts, digest):
            return {"pts_time": str(pts), "dts_time": str(pts),
                    "duration_time": "1", "data_hash": digest}

        @contextlib.contextmanager
        def records(command, prefix):
            if command[-1] == str(output):
                data = [packet(0, "a"), packet(1, "b")]
            elif "-chapter_start" in command:
                chapter = int(command[command.index("-chapter_start") + 1])
                data = [packet(0, "a" if chapter == 1 else "b")]
            else:
                data = [packet(0, "a")]
            yield iter(data)

        with patch.object(archive, 'probe_dvd_streams', return_value=[video]), \
             patch.object(archive, 'probe', return_value=media), \
             patch.object(archive, 'probe_records', side_effect=records):
            result = self.real_compare_dvd(self.source, ['-title', '1'], output, title)
        self.assertEqual(result['method'], 'chapters')
        self.assertEqual(result['streams'][0]['packets'], 2)
        self.assertTrue(result['whole_source_prefix_checked'])

    def test_source_comparison_reports_timestamp_adjustment(self):
        video = {"index": 0, "codec_type": "video", "codec_name": "mpeg2video"}
        audio = {"index": 1, "codec_type": "audio", "codec_name": "ac3"}
        output = self.root / 'out.mkv'
        media = {"streams": [video, audio], "chapter_starts": []}

        @contextlib.contextmanager
        def records(command, prefix):
            stream = int(command[command.index('-select_streams') + 1])
            pts = 1.002 if stream == 1 and command[-1] == str(output) else 1 if stream == 1 else 0
            yield iter([{"pts_time": str(pts), "dts_time": str(pts),
                         "duration_time": "1", "data_hash": str(stream)}])

        with patch.object(archive, 'probe_dvd_streams', return_value=[video, audio]), \
             patch.object(archive, 'probe', return_value=media), \
             patch.object(archive, 'probe_records', side_effect=records):
            result = self.real_compare_dvd(self.source, ['-title', '1'], output)
        self.assertEqual(len(result['timestamp_adjustments']), 2)
        self.assertEqual(result['timestamp_adjustments'][0]['difference_seconds'], 0.002)
        self.assertIn('timestamp fields', result['warnings'][0])

    def test_chapter_comparison_rejects_audio_omitted_by_chapter_reads(self):
        video = {"index": 0, "codec_type": "video", "codec_name": "mpeg2video"}
        audio = {"index": 1, "codec_type": "audio", "codec_name": "ac3"}
        output = self.root / 'out.mkv'
        media = {"streams": [video, audio], "chapter_starts": [0, 1]}
        title = (1, 2.0, [1.0, 1.0])

        def packet(pts, digest):
            return {"pts_time": str(pts), "dts_time": str(pts),
                    "duration_time": "1", "data_hash": digest}

        @contextlib.contextmanager
        def records(command, prefix):
            is_output = command[-1] == str(output)
            chapter = (int(command[command.index('-chapter_start') + 1])
                       if '-chapter_start' in command else None)
            stream = int(command[command.index('-select_streams') + 1])
            if stream == 0:
                data = ([packet(0, 'a'), packet(1, 'b')] if is_output or chapter is None
                        else [packet(0, 'a' if chapter == 1 else 'b')])
            else:
                data = ([packet(0, 'audio')] if is_output or chapter == 1
                        else [] if chapter == 2
                        else [packet(0, 'audio'), packet(1, 'missing')])
            yield iter(data)

        with patch.object(archive, 'probe_dvd_streams', return_value=[video, audio]), \
             patch.object(archive, 'probe', return_value=media), \
             patch.object(archive, 'probe_records', side_effect=records):
            with self.assertRaisesRegex(archive.SourceComparisonError, 'audio stream 1.*output ended early'):
                self.real_compare_dvd(self.source, ['-title', '1'], output, title)

    def test_matching_media_with_authored_length_difference_is_verified_with_warning(self):
        self.extract()
        self.media = {'verified': True, 'duration': 12.0, 'chapter_count': 0}
        with patch.object(self, 'inventories',
                          side_effect=lambda source, kind: self.options if kind == 'title' else {}):
            status, manifest = self.verify()
        entry = next(item for item in manifest['files'] if item['kind'] == 'title')
        self.assertTrue(entry['verified'])
        self.assertIn('10.000s', entry['warnings'][0])
        self.assertIn('12.000s', entry['warnings'][0])
        self.assertTrue(entry['source_comparison']['verified'])
        self.assertEqual(manifest['summary']['warnings'], 1)
        receipt = json.loads((self.titles / 'title_001.mkv.receipt.json').read_text())
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(receipt['warnings'], entry['warnings'])
        self.assertEqual(status, 0)

    def test_short_matching_whole_read_checks_all_chapters(self):
        video = {"index": 0, "codec_type": "video", "codec_name": "mpeg2video"}
        output = self.root / 'out.mkv'
        media = {"streams": [video], "chapter_starts": [0, 10]}
        title = (1, 20.0, [10.0, 10.0])
        unreadable = False

        @contextlib.contextmanager
        def records(command, prefix):
            packet = {"pts_time": "0", "dts_time": "0", "duration_time": "1",
                      "data_hash": "first"}
            if "-chapter_start" in command and command[command.index("-chapter_start") + 1] == "2":
                if unreadable:
                    yield iter([])
                    return
                packet = dict(packet, data_hash="second")
            yield iter([packet])

        with patch.object(archive, 'probe_dvd_streams', return_value=[video]), \
             patch.object(archive, 'probe', return_value=media), \
             patch.object(archive, 'probe_records', side_effect=records):
            with self.assertRaisesRegex(archive.SourceComparisonError, 'output ended early'):
                self.real_compare_dvd(self.source, ['-title', '1'], output, title)
            unreadable = True
            with self.assertRaisesRegex(archive.SourceComparisonError, 'chapter 2 is empty'):
                self.real_compare_dvd(self.source, ['-title', '1'], output, title)

    def test_matching_chapters_report_authored_duration_warnings(self):
        video = {"index": 0, "codec_type": "video", "codec_name": "mpeg2video"}
        output = self.root / 'out.mkv'
        media = {"streams": [video], "chapter_starts": [0, 1]}
        title = (1, 20.0, [10.0, 10.0])

        @contextlib.contextmanager
        def records(command, prefix):
            first = {"pts_time": "0", "dts_time": "0", "duration_time": "1", "data_hash": "a"}
            second = {"pts_time": "1", "dts_time": "1", "duration_time": "1", "data_hash": "b"}
            if command[-1] == str(output):
                data = [first, second]
            elif "-chapter_start" in command and command[command.index("-chapter_start") + 1] == "2":
                data = [dict(second, pts_time="0", dts_time="0")]
            else:
                data = [first]
            yield iter(data)

        with patch.object(archive, 'probe_dvd_streams', return_value=[video]), \
             patch.object(archive, 'probe', return_value=media), \
             patch.object(archive, 'probe_records', side_effect=records):
            result = self.real_compare_dvd(self.source, ['-title', '1'], output, title)
        self.assertTrue(result['verified'])
        self.assertEqual(result['method'], 'chapters')
        self.assertEqual(len(result['warnings']), 2)
        self.assertIn('chapter 2', result['warnings'][1])

    def test_source_comparison_failure_retries_multichapter_extraction(self):
        self.options['title_001.mkv'] = (1, 10.0, [5.0, 5.0])
        self.media = {'verified': True, 'duration': 10.0, 'chapter_count': 2}
        self.comparison.side_effect = [
            archive.SourceComparisonError('packet mismatch'),
            {'verified': True, 'method': 'chapters', 'streams': []},
        ]
        with patch.object(archive, 'recover_chapters') as recover:
            self.extract()
        recover.assert_called_once()
        receipt = json.loads((self.titles / 'title_001.mkv.receipt.json').read_text())
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(receipt['source_comparison']['method'], 'chapters')

    def test_chapter_recovery_warns_about_authored_duration(self):
        output = self.root / 'joined.mkv'

        def remux(source, options, destination):
            destination.write_bytes(b'chapter')

        def join(command, **kwargs):
            output.write_bytes(b'joined')
            return subprocess.CompletedProcess(command, 0)

        def counts(path):
            return {0: 2 if path == output else 1}

        diagnostics = io.StringIO()
        with patch.object(archive, 'remux_dvd', side_effect=remux), \
             patch.object(archive, 'probe', return_value={'duration': 2.0, 'streams': []}), \
             patch.object(archive, 'packet_counts', side_effect=counts), \
             patch.object(archive.subprocess, 'run', side_effect=join), \
             contextlib.redirect_stderr(diagnostics):
            archive.recover_chapters(self.source, (1, 20.0, [10.0, 10.0]), output)
        self.assertTrue(output.exists())
        self.assertIn('authored DVD metadata reports 10.000s', diagnostics.getvalue())

    def test_pcm_comparison_matches_samples_despite_repacketization(self):
        ffmpeg = Path(archive.FFMPEG)
        if not ffmpeg.is_file():
            self.skipTest("DVD-enabled FFmpeg is required")
        original = self.root / 'original.wav'
        output = self.root / 'output.wav'
        samples = bytes(range(256)) * 40
        for path in (original, output):
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(2)
                audio.setsampwidth(2)
                audio.setframerate(48000)
                audio.writeframes(samples)
        with patch.object(archive, 'dvd_input', return_value=[str(original)]):
            self.assertEqual(archive.pcm_hash(original, [[]], output, 0, 0, 's16'), len(samples) * 2)
        with wave.open(str(output), 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(48000)
            audio.writeframes(bytes(reversed(samples)))
        with patch.object(archive, 'dvd_input', return_value=[str(original)]):
            with self.assertRaisesRegex(archive.SourceComparisonError, 'samples differ'):
                archive.pcm_hash(original, [[]], output, 0, 0, 's16')

    def test_pcm_frame_timing_can_cross_different_packet_boundaries(self):
        source_frames = [{"pts_time": str(n / 2), "duration_time": "0.5",
                          "nb_samples": "2", "sample_fmt": "s16", "channels": "2"}
                         for n in range(2)]
        output_frames = [{"pts_time": str(n / 4), "duration_time": "0.25",
                          "nb_samples": "1", "sample_fmt": "s16", "channels": "2"}
                         for n in range(4)]

        @contextlib.contextmanager
        def records(command, prefix):
            yield iter(source_frames if command[-1] == str(self.source) else output_frames)

        with patch.object(archive, 'probe_records', side_effect=records):
            archive.compare_pcm_timing(self.source, [[]], self.root / 'output.mkv', 1, 1, 4,
                                       {None: 0}, [None], "s16", 2)
            output_frames[2]["pts_time"] = "0.6"
            with self.assertRaisesRegex(archive.SourceComparisonError, 'timing differs'):
                archive.compare_pcm_timing(self.source, [[]], self.root / 'output.mkv', 1, 1, 4,
                                           {None: 0}, [None], "s16", 2)
            output_frames[2]["pts_time"] = "0.5"
            source_frames[1]["sample_fmt"] = "s32"
            with self.assertRaisesRegex(archive.SourceComparisonError, 'format or sample rate change'):
                archive.compare_pcm_timing(self.source, [[]], self.root / 'output.mkv', 1, 1, 4,
                                           {None: 0}, [None], "s16", 2)

    def test_24_bit_pcm_comparison_normalizes_samples(self):
        if not Path(archive.FFMPEG).is_file():
            self.skipTest("DVD-enabled FFmpeg is required")
        original = self.root / 'original24.wav'
        output = self.root / 'output24.wav'
        samples = bytes(range(240)) * 20
        for path in (original, output):
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(2)
                audio.setsampwidth(3)
                audio.setframerate(48000)
                audio.writeframes(samples)
        with patch.object(archive, 'dvd_input', return_value=[str(original)]):
            self.assertEqual(archive.pcm_hash(original, [[]], output, 0, 0, 's32'), len(samples) * 4 // 3)

    def test_pcm_comparison_detects_lost_low_bits(self):
        if not Path(archive.FFMPEG).is_file():
            self.skipTest("DVD-enabled FFmpeg is required")
        original = self.root / 'source24.wav'
        output = self.root / 'output16.wav'
        for path, width, samples in (
                (original, 3, b"\x01\x00\x10" * 100),
                (output, 2, b"\x00\x10" * 100)):
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(width)
                audio.setframerate(48000)
                audio.writeframes(samples)
        with patch.object(archive, 'dvd_input', return_value=[str(original)]):
            with self.assertRaisesRegex(archive.SourceComparisonError, 'samples differ'):
                archive.pcm_hash(original, [[]], output, 0, 0, 's16')

    def test_directory_fingerprint_tracks_dvd_content_only(self):
        dvd = self.root / 'folder'
        video = dvd / 'VIDEO_TS'
        video.mkdir(parents=True)
        (video / 'VIDEO_TS.IFO').write_bytes(b'ifo')
        identity = archive.source_identity(dvd)
        (dvd / 'output.txt').write_bytes(b'new output')
        self.assertEqual(identity, archive.source_identity(dvd))
        self.assertEqual(identity, archive.source_identity(video))
        (video / 'VIDEO_TS.IFO').write_bytes(b'changed')
        self.assertNotEqual(identity, archive.source_identity(dvd))

    def test_probe_requires_video(self):
        with patch.object(archive, 'run', return_value='{"streams": []}'):
            with self.assertRaisesRegex(ValueError, 'No video'):
                archive.probe(self.source)

    def test_corrupt_receipt_is_not_trusted(self):
        self.extract()
        path = self.titles / 'title_001.mkv'
        archive.receipt_path(path).write_text('[]')
        self.assertIsNone(archive.matching_receipt(path, archive.source_identity(self.source)))


class IfoFailureTests(unittest.TestCase):
    def test_unreadable_title_set_fails_candidate_enumeration(self):
        compiler = shutil.which("cc")
        if not compiler or not Path("/usr/include/dvdread/ifo_read.h").exists():
            self.skipTest("C compiler and libdvdread headers required")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = SCRIPT.parent.parent / "src" / "ifo_dump.c"
            harness = root / "harness.c"
            harness.write_text(r'''#define DVDOpen audit_DVDOpen
#define DVDClose audit_DVDClose
#define ifoOpen audit_ifoOpen
#define ifoClose audit_ifoClose
#define main audit_main
#include "''' + str(source) + r'''"
#undef main
static vmgi_mat_t metadata;
static ifo_handle_t vmg;
dvd_reader_t *audit_DVDOpen(const char *path) { (void)path; return (dvd_reader_t *)&vmg; }
void audit_DVDClose(dvd_reader_t *dvd) { (void)dvd; }
ifo_handle_t *audit_ifoOpen(dvd_reader_t *dvd, int title) {
    (void)dvd;
    if (title != 0) return NULL;
    metadata.vmg_nr_of_title_sets = 1;
    vmg.vmgi_mat = &metadata;
    return &vmg;
}
void audit_ifoClose(ifo_handle_t *ifo) { (void)ifo; }
int main(void) {
    char *args[] = {"dvd-ifo-dump", "--candidates", "fake.iso"};
    return audit_main(3, args);
}
''')
            executable = root / "ifo-test"
            subprocess.run([compiler, "-Wall", "-Wextra", "-Werror", str(harness),
                            "-o", str(executable)], check=True, capture_output=True)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("VTS 1", result.stderr)
            self.assertIn("incomplete", result.stderr)


if __name__ == '__main__':
    unittest.main()
