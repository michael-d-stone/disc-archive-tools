# Roadmap

DVD-Video reliability and Blu-ray development can proceed in parallel. Each
track has its own completion criteria. Coordinate changes that affect both
tracks, especially receipt and manifest behavior.

## DVD-Video reliability

### Archive rechecks — complete

Five existing archives were rechecked against their recorded sources: Frasier
season 1 disc 1, Massive Asses 3, Asa Akira Is Pure discs 1 and 2, and Squirt
Queens 11. All passed the current inventory, receipt, checksum, and media-probe
checks. The original manifests were preserved and timestamped results saved.
Passing these checks does not establish full content preservation or playback.

### Interactive still gallery export — implemented

Asa Akira Is Pure Disc 2 titles 7–17 use DVD navigation instructions to
hold still frames indefinitely. `dvd-extract` now identifies these titles,
prints the `dvd-gallery-extract` commands, and continues with the ordinary
titles and menus. The offline browser exports preserve the stills, chapter
navigation, and cross-title jumps. Exits to DVD menus identify their
destination on screen.

All 11 galleries passed source-based verification in staging. Their Next
and Previous paths matched continuous DVD navigation, and an offline
browser test confirmed that a still waits for input. The full staging
archive verified all 71 entries. The original ISO and archive were untouched.

Possible follow-up work includes supporting timed stills and on-screen DVD
buttons, and testing those behaviors on discs authored differently. A
desktop-player comparison is still open because mpv skipped the source
disc's holds during testing.

## Blu-ray — next format

### Playlist extraction — in progress

The Blu-ray commands inventory authored playlists with libbluray, extract
supported streams with FFmpeg, and verify source fingerprints, chapters,
runtime, streams, checksums, and packet timestamps. The manifest identifies
interactive graphics and BD-J titles. Menu preservation remains open.

Initial staging runs on Its A Mommy Thing 5 and Breakin Em In 9 found
playlist-boundary problems. Several audio streams contain distinct packets
with identical DTS values at a clip transition. On Its A Mommy Thing 5
playlist 00001, the corresponding source packets have different timestamps.
The extractor now retries a supported two-clip timestamp-wrap layout using the
authored clip timing, then compares every video and audio packet's payload and
mapped timestamps with the source. Playlist 00001 passed this check in staging.

FFmpeg also failed to read some VC-1 dimensions or audio parameters, and
reported corrupt packets on another playlist. A larger probe lets some files
proceed, but it does not resolve all failures. These outputs need further
investigation before the workflow can be considered complete for these discs.

Next, extend lossless boundary handling to other playlist layouts and dynamic
stream changes, then re-extract and check video and audio continuity. Test
alternate angles, branching, additional codecs, and a representative ISO
before claiming support. Blu-ray menu extraction and interactive navigation
remain separate follow-up work.

## Format backlog

Audio CD, Video CD (VCD), Super Video CD (SVCD), and DVD-Audio are planned.
Their order is open.
