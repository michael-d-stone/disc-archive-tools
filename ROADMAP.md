# Roadmap

DVD-Video reliability and Blu-ray development can proceed in parallel. Each
track has its own completion criteria. Coordinate changes that affect both
tracks, especially receipt and manifest behavior.

## Disc filenames — implemented

DVD titles and Blu-ray playlists use a normalized source-name prefix, with a
manual override and compatibility for existing unprefixed archives.

## DVD-Video reliability

### Archive rechecks — complete

Five existing archives were rechecked against their recorded sources: Frasier
season 1 disc 1, Massive Asses 3, Asa Akira Is Pure discs 1 and 2, and Squirt
Queens 11. All passed the current inventory, receipt, checksum, and media-probe
checks. The original manifests were preserved and timestamped results saved.
Passing these checks does not establish full content preservation or playback.

An Elegant Angel DVD, *Jada Fire Is Squirtwoman 4*, exposed complete 33-bit
MPEG timestamp-counter cycles at several chapter boundaries. FFmpeg's general
discontinuity handling eventually shifted audio by about 82 ms, while reading
chapters separately omitted 2 video and 11 audio packets. A targeted clock
unwrap preserved all 7,276 video and 7,574 audio packets and matched normalized
source timestamps within Matroska rounding. DVD extraction now tries that
correction before its general timestamp retry and records the detected wraps.

### Workflow visibility — planned

Bring the Blu-ray workflow's live FFmpeg transcript, progress meter, and
persistent per-item logs to DVD title and menu extraction. Add the same
byte-level fingerprint progress display while preserving concise behavior when
output is redirected.

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

## SlutTV ISO playback — planned

### DVD-Video prototype

SlutTV will manage library metadata and serve the original readable ISO over
HTTP range requests. The embedded player will use libdvdnav to run the
disc's authored DVD menus. Touch and mouse will activate buttons directly
on the menu artwork, and arrow keys and Enter will follow the disc's authored
navigation. The first milestone is to verify menu video and audio, synchronized
button highlights, Play, and chapter selection on iPhone Safari and a desktop
browser.

### Client-side decoding and deinterlacing

Playback will keep the original ISO and encoded streams intact, with no
server-side transcoding or client-side re-encoding. Use browser-native decoding
where supported and evaluate FFmpeg in WebAssembly for streams that need
software decoding. Run FFmpeg's `bwdif` filter on decoded interlaced frames
before rendering when the device can sustain it. Verify playback and
deinterlacing performance on real devices before expanding support to additional
phones, TVs, and browsers.

### Blu-ray navigation

After the DVD milestone, prototype HDMV menus and pop-up navigation with
libbluray. Investigate BD-J separately because it requires a compatible Java
runtime.

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

### Elegant Angel discs — observations

Tests of *Curvy Girls 3* and *Asa Akira Is Insatiable*, identified as Elegant
Angel releases, showed strikingly similar playlist structures and failures:

- Playlist 00007 repeats clip 00009 seven times. Both extractions reported
  a repeated audio DTS at 60.001 seconds.
- Playlists 00009 and 00010 failed their timestamp-correction retries on a
  backwards video DTS.
- The long playlist 00012, likely the feature on each disc, failed its retry
  when FFmpeg could not determine video dimensions and audio sample rate.
  FFmpeg also reported corrupt packets while reading it.
- Playlist 00000 stopped on a packet FFmpeg flagged as corrupt.

The shared patterns may reflect a common studio authoring workflow or template;
that is a hypothesis, not an established cause. They do not establish whether
the source data is damaged, the disc authoring is unusual, or our reading and
correction paths are at fault. Compare direct clip reads with playlist reads,
and test conventional Blu-rays as a baseline before drawing conclusions.
The original test logs and manifests identify the individual failures.

*Asa Akira Is Insatiable 2* shows the same patterns under different playlist
numbers. Playlist 00005 repeats clip 00004 seven times and fails on the same
60.001-second audio DTS. The likely feature is playlist 00001, about 3 hours
40 minutes; its retry also lacks video dimensions and audio sample rate.
Playlists 00003, 00004, and 00012 fail their timestamp retries on backwards
video DTS. Playlist numbers and clip IDs therefore cannot identify these
patterns reliably across releases.

Next, extend lossless boundary handling to other playlist layouts and dynamic
stream changes, then re-extract and check video and audio continuity. Test
alternate angles, branching, additional codecs, and a representative ISO
before claiming support. Blu-ray menu extraction and interactive navigation
remain separate follow-up work.

## Format backlog

Audio CD, Video CD (VCD), Super Video CD (SVCD), and DVD-Audio are planned.
Their order is open.
