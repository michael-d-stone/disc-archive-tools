# Copyright (C) 2026 Michael Stone
# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.machinery
import contextlib
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
                 self.media, self.media, {'duration': 60.0, 'chapter_count': 2}]), \
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
