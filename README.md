# disc-archive-tools

`disc-archive-tools` is a collection of free and open-source tools for extracting and preserving the contents of optical media using standard, inspectable file formats.

The project currently supports DVD-Video. Given an already-readable DVD ISO image or DVD directory, it extracts authored titles and playable menu content to Matroska (`.mkv`) files without re-encoding, then verifies the extracted files and produces a manifest describing them.

## Scope

The current DVD-Video tools operate on an already-readable DVD ISO image or DVD directory. DVD acquisition and decryption are not performed by `disc-archive-tools`.

Acquisition workflows may differ for other supported disc formats. For example, planned Audio CD support will use an existing secure-ripping tool rather than reimplementing secure audio extraction.

Current support:

- DVD-Video

Planned support includes:

- Blu-ray (next format)
- Audio CD
- Video CD (VCD)
- Super Video CD (SVCD)
- DVD-Audio


## Building on Debian 12

Install the required packages:

```bash
sudo apt update
sudo apt install \
  build-essential \
  libdvdread-dev \
  libdvdnav-dev \
  lsdvd \
  nasm \
  pkg-config \
  python3 \
  xz-utils
```

Build and install the included FFmpeg 9.0.1 source with DVD-Video support:

```bash
make ffmpeg
sudo make install-ffmpeg
```

Build and install disc-archive-tools:

```bash
make disc-archive-tools
sudo make install-disc-archive-tools
```

The FFmpeg build is installed under `/opt/ffmpeg-dvd`. The disc-archive-tools commands are installed under `/usr/local/bin`.

## DVD-Video usage

Extract an already-readable DVD ISO:

```bash
dvd-extract "/path/to/disc.iso"
```

Or extract from a DVD directory:

```bash
dvd-extract "/path/to/dvd-directory"
```

To choose the output directory explicitly:

```bash
dvd-extract "/path/to/disc.iso" "/path/to/output"
```

`dvd-extract` extracts all authored DVD titles and playable menu content to Matroska (`.mkv`) files. DVD LPCM audio is converted losslessly to Matroska-compatible PCM. All other streams are copied.

After extraction, the output is verified with `ffprobe` and a `manifest.json` file is created describing the extracted files. Later verification runs preserve that original and write a new `verified-YYYY-MM-DD-HHMMSS-UTC.json` file in the output directory, with a numeric suffix if needed. The command prints the result path, including for failed checks.

An interrupted extraction can be run again. Files are skipped only when a completion receipt matches both the DVD source fingerprint and the output SHA-256 checksum. Missing, changed, or unreceipted files are extracted again. Each extraction writes a temporary file and publishes the final MKV only after FFmpeg succeeds and the result can be probed. Title checks also compare the MKV runtime and chapter count against the authored DVD metadata. A single-chapter title may use the whole MKV as its implicit chapter. A checksummed title that falls short is recorded as incomplete and retried. When the whole-title read returns an incomplete multi-chapter MKV, extraction retries with bounded chapter reads and checks packet counts across the join. Existing archives without receipts must be re-extracted.

### Optional FLAC conversion after archiving

After verification, you can make a separate MKV with losslessly compressed FLAC
audio. Use a destination outside the verified archive so its checksums and
completion receipts remain valid.

```bash
input="/path/to/archive/titles/title_002.mkv"
/opt/ffmpeg-dvd/bin/ffprobe -v error -select_streams a \
  -show_entries stream=index,codec_name -of compact "$input"

# Example for a PCM track whose stream index is 1.
/opt/ffmpeg-dvd/bin/ffmpeg -n -i "$input" -map 0 -c copy -c:1 flac \
  "/path/to/converted/title_002.mkv"
```

Use the reported index for each `pcm_s16le` or `pcm_s24le` track you want to
convert. Add a separate `-c:<index> flac` for each selected track.

## Command and source map

The normal entry point is `dvd-extract`. It runs title extraction, menu
extraction, and verification in sequence, stopping if any step fails.

| Command | Purpose |
| --- | --- |
| `dvd-extract SOURCE [OUTPUT]` | Run the complete workflow; default output is `dvd-extract/`. |
| `dvd-title-extract SOURCE [OUTPUT]` | Extract authored titles only; default output is `titles/`. |
| `dvd-menu-extract SOURCE [OUTPUT]` | Extract playable menu content only; default output is `menus/`. |
| `dvd-verify SOURCE OUTPUT` | Recheck an extraction and write `manifest.json`; requires the original source. |
| `dvd-ifo-dump [--candidates] SOURCE` | Inspect DVD menu metadata; `--candidates` lists playable menu locations. |

When running the title and menu commands separately, use `OUTPUT/titles` and
`OUTPUT/menus` respectively so `dvd-verify SOURCE OUTPUT` can find them.
Use a separate output directory for each disc. Unexpected MKVs are reported,
not automatically deleted.

The code is organized as follows:

- `scripts/dvd-extract`: Bash orchestration for the complete workflow.
- `scripts/dvd-title-extract`, `scripts/dvd-menu-extract`, and `scripts/dvd-verify`:
  small Python entry points preserving the command names above.
- `scripts/dvd-archive`: shared Python implementation for source fingerprints,
  inventory discovery, extraction, completion receipts, and verification. It
  must be installed alongside the entry points; the Makefile handles this.
- `src/ifo_dump.c`: the libdvdread menu-inspection helper. `make` builds it as
  `build-ifo-dump`; installation names it `dvd-ifo-dump`.
- `tests/test_archive.py`: self-contained regression tests (`make test`).
- `tests/test-dvd-extract.py` and `tests/fixtures/`: checks against manifests
  from known DVD extractions (`make test-fixtures`).
- `vendor/`: the pinned FFmpeg source archive and authentication materials.
- `docs/DEPENDENCIES.md` and `docs/PROVENANCE.md`: dependency and source history.

From a checkout, build the helper with `make`, then use
`./scripts/dvd-extract SOURCE OUTPUT`. Installed commands require rebuilding
and reinstalling after source changes. FFmpeg and ffprobe are currently
expected under `/opt/ffmpeg-dvd/bin`.

## DVD-Video output

A DVD-Video extraction has this layout:

```text
output/
├── titles/
│   ├── title_001.mkv
│   ├── title_001.mkv.receipt.json
│   ├── title_002.mkv
│   └── ...
├── menus/
│   ├── vts_001_lu_001_pgc_001.mkv
│   ├── vts_001_lu_001_pgc_001.mkv.receipt.json
│   └── ...
└── manifest.json
```

The `titles` directory contains authored DVD titles. The `menus` directory contains playable menu content identified from the DVD structure.

`manifest.json` (version 2) checks the expected title and menu inventory against the output, reports missing and unexpected files, and validates completion receipts and output checksums. Source discovery errors fail verification. It records the extracted files and verification results, including available stream, codec, chapter, duration, language, audio, and video information.

Completion receipts (`*.mkv.receipt.json`) must be kept alongside their MKVs. Fingerprinting reads the entire ISO or all `.IFO`, `.BUP`, and `.VOB` files in `VIDEO_TS`; this adds disk I/O during extraction and verification. Keep the source unchanged while commands run. Verification establishes successful extraction and unchanged output; it does not perform a full decode or prove equivalence to every source packet.

## Preservation notes

DVD-Video titles and playable menu content are remuxed without re-encoding. The original encoded audio and video streams are copied into Matroska containers whenever possible.

The current extraction does not reconstruct the original interactive DVD navigation. Menu video and audio are preserved as playable media, but DVD button behavior, navigation commands, and the original interactive menu experience are not reproduced by the resulting MKV files.

`disc-archive-tools` is intended to preserve the authored audiovisual content in accessible, inspectable files rather than emulate a DVD player.

## Testing

Run the regression test suite from the repository root:

```bash
make test
```

The self-contained tests exercise interrupted extraction, safe resume, discovery failures, source identity, and missing or altered outputs without DVD sources.

Check existing extraction manifests against the DVD regression fixtures separately:

```bash
make test-fixtures
```

The fixture checks cover expected titles, menu content, streams, chapters, and durations. They expect `test_dvd_extract/manifest.json` and `test_seinfeld_extract/manifest.json` from prior extractions; they do not run extraction themselves.

Producing those extraction manifests requires access to the corresponding test DVD sources; the repository does not contain copyrighted audiovisual content.

## Legal and licensing

`disc-archive-tools` is intended for lawful archival and preservation uses. Users are responsible for complying with applicable copyright law and the terms governing the media they process. Possession of a disc does not necessarily grant the right to reproduce or distribute its contents.

The current DVD-Video workflow does not provide copy-protection removal or decryption. It operates on already-readable DVD sources.

The software in this repository is licensed under the GNU General Public License version 2 or later (`GPL-2.0-or-later`). See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md) for details.

Third-party software retains its own copyright and licensing terms. See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) for dependency and licensing information.

Development history, source provenance, and the use of OpenAI ChatGPT during development are documented in [docs/PROVENANCE.md](docs/PROVENANCE.md).
