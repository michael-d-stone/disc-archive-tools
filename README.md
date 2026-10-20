# disc-archive-tools

`disc-archive-tools` is a collection of free and open-source tools for extracting and preserving the contents of optical media using standard, inspectable file formats.

The project currently supports DVD-Video. Given an already-readable DVD ISO image or DVD directory, it extracts authored titles and playable menu content to Matroska (`.mkv`) files without re-encoding, then verifies the extracted files and produces a manifest describing them.

## Scope

The current DVD-Video tools operate on an already-readable DVD ISO image or DVD directory. DVD acquisition and decryption are not performed by `disc-archive-tools`.

Acquisition workflows may differ for other supported disc formats. For example, planned Audio CD support will use an existing secure-ripping tool rather than reimplementing secure audio extraction.

Current support:

- DVD-Video

Planned support includes:

- Audio CD
- Video CD (VCD)
- Super Video CD (SVCD)
- DVD-Audio
- Blu-ray


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

`dvd-extract` extracts all authored DVD titles and playable menu content without re-encoding. Output is written as Matroska (`.mkv`) files.

After extraction, the output is verified with `ffprobe` and a `manifest.json` file is created describing the extracted files.

An interrupted extraction can be run again. Existing readable files are skipped, while missing or invalid files are extracted again.

## DVD-Video output

A DVD-Video extraction has this layout:

```text
output/
├── titles/
│   ├── title_001.mkv
│   ├── title_002.mkv
│   └── ...
├── menus/
│   ├── menu_vts_01_lu_01_pgc_001.mkv
│   └── ...
└── manifest.json
```

The `titles` directory contains authored DVD titles. The `menus` directory contains playable menu content identified from the DVD structure.

`manifest.json` records the extracted files and verification results, including available stream, codec, chapter, duration, language, audio, and video information.

## Preservation notes

DVD-Video titles and playable menu content are remuxed without re-encoding. The original encoded audio and video streams are copied into Matroska containers whenever possible.

The current extraction does not reconstruct the original interactive DVD navigation. Menu video and audio are preserved as playable media, but DVD button behavior, navigation commands, and the original interactive menu experience are not reproduced by the resulting MKV files.

`disc-archive-tools` is intended to preserve the authored audiovisual content in accessible, inspectable files rather than emulate a DVD player.

## Testing

Run the regression test suite from the repository root:

```bash
make test
```

The regression tests exercise DVD-Video extraction and verification against known test fixtures, including expected titles, menu content, streams, chapters, and durations.

The tests require access to the corresponding test DVD sources; the repository does not contain copyrighted audiovisual content.

## Legal and licensing

`disc-archive-tools` is intended for lawful archival and preservation uses. Users are responsible for complying with applicable copyright law and the terms governing the media they process. Possession of a disc does not necessarily grant the right to reproduce or distribute its contents.

The current DVD-Video workflow does not provide copy-protection removal or decryption. It operates on already-readable DVD sources.

The software in this repository is licensed under the GNU General Public License version 2 or later (`GPL-2.0-or-later`). See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md) for details.

Third-party software retains its own copyright and licensing terms. See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) for dependency and licensing information.

Development history, source provenance, and the use of OpenAI ChatGPT during development are documented in [docs/PROVENANCE.md](docs/PROVENANCE.md).
