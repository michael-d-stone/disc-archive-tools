# Vendored FFmpeg Source

This directory contains the upstream source release of FFmpeg used to build
and test disc-archive-tools.

## Version

FFmpeg 9.0.1

The project remains pinned to this version until a different FFmpeg release
has been deliberately tested against the disc-archive-tools regression suite.

## Files

- `ffmpeg-9.0.1.tar.xz`
  - Original, unmodified FFmpeg 9.0.1 source archive.
- `ffmpeg-9.0.1.tar.xz.asc`
  - Original detached OpenPGP signature for the source archive.
- `ffmpeg-devel.asc`
  - FFmpeg release-signing public key obtained from FFmpeg.
- `SHA256SUMS`
  - SHA-256 checksums recorded by the disc-archive-tools project.

These upstream files are preserved so that a checkout of disc-archive-tools
contains the FFmpeg source required to reproduce the tested build without
depending on the continued availability of an external download.

## Authentication

Before inclusion in this repository, the FFmpeg release-signing public key
was checked against the fingerprint published by FFmpeg:

    FCF9 86EA 15E6 E293 A564 4F10 B432 2F04 D676 58D8

The detached signature for `ffmpeg-9.0.1.tar.xz` was then successfully
verified using that key.

The SHA-256 digest of the verified source archive is:

    cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635

Users can verify the stored files with:

    cd vendor
    sha256sum -c SHA256SUMS

The FFmpeg source archive can additionally be authenticated using the
included detached signature and release-signing public key.

## Licensing

The FFmpeg source archive and associated upstream files are third-party
materials and are not original disc-archive-tools source code.

They remain subject to their respective upstream copyright and licensing
terms. The FFmpeg source archive contains the applicable upstream licensing
information.

The tested FFmpeg build used by disc-archive-tools is configured with GPL
components enabled and is GPL-2.0-or-later.

See `../docs/DEPENDENCIES.md` and `../docs/PROVENANCE.md` for additional
dependency and provenance information.
