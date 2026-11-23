# disc-archive-tools

`disc-archive-tools` is a collection of free and open-source tools for extracting and preserving the contents of optical media using standard, inspectable file formats.

The project supports DVD-Video extraction and verification. Initial Blu-ray playlist extraction and verification are available for testing against readable discs.

## Scope

The current DVD-Video tools operate on an already-readable DVD ISO image or DVD directory. DVD acquisition and decryption are not performed by `disc-archive-tools`.

Acquisition workflows may differ for other supported disc formats. For example, planned Audio CD support will use an existing secure-ripping tool rather than reimplementing secure audio extraction.

Current support:

- DVD-Video
- Blu-ray playlist extraction and verification, with unsupported cases reported

Planned support includes:
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
  libbluray-dev \
  libdvdread-dev \
  libdvdnav-dev \
  libudfread-dev \
  lsdvd \
  nasm \
  pkg-config \
  python3 \
  xz-utils
```

Build and install the included FFmpeg 9.0.1 source with DVD-Video and
Blu-ray protocol support:

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
Confirm the installed FFmpeg has both disc capabilities:

```bash
/opt/ffmpeg-dvd/bin/ffmpeg -hide_banner -protocols | grep bluray
/opt/ffmpeg-dvd/bin/ffmpeg -hide_banner -demuxers | grep dvdvideo
```

## Inspect a disc

List the titles and chapters on an already-readable DVD ISO or DVD directory:

```bash
lsdvd -c "/path/to/disc.iso"
```

For optional Blu-ray inspection on Debian 12, install the package that provides
`bd_list_titles`:

```bash
sudo apt install libbluray-bin
```

Point it at the directory containing `BDMV`:

```bash
bd_list_titles -a -l "/path/to/disc-root"
```

It also accepts a Blu-ray ISO directly:

```bash
bd_list_titles -a -l "/path/to/disc.iso"
```

`-a` lists all titles and `-l` includes language codes. The output shows
playlist numbers, runtimes, chapter counts, and clip counts. Blu-ray inspection
is available through this external tool.

## Blu-ray usage

Extract and verify every playlist from an already-readable Blu-ray ISO or the
directory containing `BDMV`:

```bash
bluray-extract "/path/to/disc-root" "/path/to/output"
```

`bluray-extract` writes playlist MKVs and source-bound completion receipts in
`OUTPUT/titles`, FFmpeg diagnostics in `OUTPUT/logs`, and a verification
manifest in `OUTPUT`. It continues after a playlist fails and exits with a
nonzero status if any playlist fails verification. An interrupted run can be
repeated and complete matching playlists are reused.

Use `bluray-title-extract SOURCE [OUTPUT]` for extraction alone and
`bluray-verify SOURCE OUTPUT` for a separate recheck. The default extraction
output directory is `bluray-extract/`. Verification preserves the first
manifest and writes timestamped results on later runs. Each verification reads
the original source and hashes the ISO or all files in `BDMV`.

The playlist metadata comes from libbluray. Authored chapter marks are written
to the MKV and checked alongside runtime, stream inventory, packet timestamps,
and checksums. For a supported two-clip timestamp-wrap case, extraction retries
with a video timestamp adjustment and compares every output video and audio
packet with the source before publishing. The playlist log and receipt record
the adjustment.
Multiple angles, interactive or timed stills, secondary streams, and
unsupported codecs are reported for investigation. Interactive graphics and
Blu-ray Java navigation are listed in the manifest. Blu-ray menu preservation
is not yet implemented. Verification checks metadata, timestamps, and
checksums. It does not compare every output packet with the source or perform
a full decode.

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

An interrupted extraction can be run again. Files are skipped only when a completion receipt matches the DVD source fingerprint and output SHA-256 checksum, and a fresh source comparison passes. Missing, changed, or unreceipted files are extracted again. Each extraction writes a temporary file and publishes the final MKV only after FFmpeg succeeds, the result can be probed, and its media matches the DVD source. Title checks also compare the MKV runtime and chapter count against the authored DVD metadata. A single-chapter title may use the whole MKV as its implicit chapter. When the whole-title read returns an incomplete multi-chapter MKV, extraction retries with bounded chapter reads and checks packet counts across the join. Existing archives without receipts must be re-extracted.

DVD title and menu verification rereads the source. It compares copied packet
contents, order, and presentation timing, and compares decoded PCM samples
normalized to 32 bits and their timing for DVD LPCM audio. When a whole-title source read
ends early, it checks the authored chapters individually. Comparison results
are stored in the receipt and manifest. A failed or unsupported comparison is
reported as unverified. If accessible source media matches the MKV but its
duration differs from the authored DVD metadata, the result is verified with
a warning showing the differing durations. The warning does not establish why
they differ. Source comparison adds disc reads and processing time.

If FFmpeg stops on a non-monotonic decode timestamp, extraction retries without
`-xerror`. The retry is rejected if FFmpeg reports other errors, and its output
must still pass source comparison before publication. Packet timestamp
differences above 1.1 ms and within the 3 ms comparison tolerance are recorded
in the source comparison and reported as warnings; smaller differences can arise
from Matroska timestamp rounding. Larger differences fail verification.

### Interactive still galleries

When a DVD title uses indefinite stills, `dvd-extract` prints the command to
export it and continues extracting the remaining titles and menus. Run the
printed `dvd-gallery-extract` command, then open the resulting `index.html`
in a browser. Keep the page, PNGs, and gallery manifest together. The page
holds each image until you use an available DVD chapter or menu control.
Links between gallery titles follow the disc. An exit to a DVD menu identifies
the destination on screen. Use the source DVD or ISO to play that menu.

Run `dvd-verify SOURCE OUTPUT` again after exporting. It checks the gallery
images and navigation against the source and reports unexported galleries as
pending. The exporter supports indefinite stills with chapter controls and
menu exits. It reports unsupported on-screen DVD buttons and other still
behavior rather than substituting a slideshow.

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
| `dvd-gallery-extract SOURCE TITLE OUTPUT` | Export an interactive still gallery as an offline HTML page and lossless PNG images. |
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

Completion receipts (`*.mkv.receipt.json`) must be kept alongside their MKVs. Fingerprinting reads the entire ISO or all `.IFO`, `.BUP`, and `.VOB` files in `VIDEO_TS`; source comparison reads the media again. Keep the source unchanged while commands run. The comparison checks the media packets that DVD navigation exposes and verifies decoded LPCM samples. DVD menu navigation and still-frame behavior remain represented by the original DVD source and the separate interactive gallery exports.

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
