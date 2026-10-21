# Source Provenance

This document records the known provenance of source code and other project
material in disc-archive-tools.

Its purpose is to make the project's development history transparent,
including the use of external free and open-source software and AI-assisted
development.

## Project development

disc-archive-tools was designed and developed by Michael Stone with extensive
assistance from OpenAI's ChatGPT.

ChatGPT has been used for:

- design and architecture discussion
- code generation
- code review and debugging
- investigation of external APIs and software behavior
- test design
- documentation
- licensing and provenance research

Project requirements, archival policy, design decisions, testing decisions,
acceptance and modification of generated code, and maintenance are directed
by Michael Stone.

Git commit authorship should not be interpreted as indicating that a file was
created without AI assistance.

## Repository history

The repository began with an empty project document. Program code was added
incrementally in later commits.

The principal source and test files entered the repository in the following
commits:

- `3e81a1b` - `Makefile` and `src/ifo_dump.c`
- `6720f69` - `scripts/dvd-menu-extract`
- `3c7b26a` - `scripts/dvd-title-extract`
- `1d62dd4` - `scripts/dvd-extract`
- `23b2d9d` - `scripts/dvd-verify`
- `00f42f0` - `tests/test-dvd-extract.py`
- `287d039` - `tests/fixtures/annette.json`
- `e248288` - `tests/fixtures/seinfeld-s1d1.json`

Subsequent commits modified and extended these files.

## libdvdread helper

`src/ifo_dump.c` was developed specifically for this project using the public
libdvdread API and data structures.

The file includes:

- `<dvdread/dvd_reader.h>`
- `<dvdread/ifo_read.h>`

and the resulting program is linked against libdvdread.

The helper was developed incrementally to inspect DVD IFO structures,
enumerate menu PGCs, and provide playable menu candidates to the extraction
scripts.

The playable-PGC criterion was developed while investigating the structures
required by FFmpeg's `dvdvideo` DVD menu handling.

The repository history does not show a third-party source file, copyright
notice, or license notice being incorporated into `src/ifo_dump.c`.

Use of libdvdread is documented separately in `docs/DEPENDENCIES.md`.

## External software

disc-archive-tools relies on external free and open-source software including
libdvdread, libdvdnav, FFmpeg, lsdvd, Bash, Python, GNU awk, GNU Make, GCC,
and standard Unix utilities.

Their roles, tested versions, and known licensing information are recorded in
`docs/DEPENDENCIES.md`.

The unmodified FFmpeg 9.0.1 source archive and its verification materials
are intentionally vendored under `vendor/` to make the tested FFmpeg build
reproducible from a self-contained checkout. The other dependencies listed
above are not vendored.

## Third-party source audit

A file-by-file dependency and provenance review was performed before the
first release.

The original project-source audit found no third-party source code
incorporated into disc-archive-tools source files.

The repository now intentionally contains the unmodified upstream FFmpeg 9.0.1
source archive under `vendor/`, together with its detached signature and release
signing key. This vendored upstream material is kept separate from the original
disc-archive-tools source.

A repository-wide search of the project source files also found no third-party
copyright notices, license notices, source URLs, GitHub references, SourceForge
references, or Stack Overflow references.

This finding describes the repository and development history examined by the
audit. It is not a claim that every individual expression in the project is
unique or has never appeared in other software.

## Test fixtures

The JSON files under `tests/fixtures/` contain regression expectations derived
from test extractions performed with disc-archive-tools.

They describe expected properties such as title counts, menu counts,
durations, chapter counts, and stream counts. They do not contain audiovisual
content from the tested discs.

## Release review

Before release, the project license and attribution material should be checked
against the dependency and provenance information recorded here.

Where required or appropriate, upstream projects and copyright holders should
receive the notices and attribution required by their respective licenses.
