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

### Feasibility

Evaluate available tools on already-readable Blu-ray sources. Start with a
straightforward feature and a multi-clip playlist. Check whether the tools
discover authored titles, follow clip order, and expose streams and chapters.
Test a representative alternate cut or branching title before claiming support
for that behavior.

### First release

Use the feasibility results to define supported input forms, playlist
selection, output naming, and how unsupported cases are reported. Extract
authored titles to Matroska with stream copy where supported. Defer acquisition,
decryption, and interactive menus.

Verification should check source identity, expected title inventory, output
checksums, and media readability. Release when representative sources pass
extraction and verification, regression tests detect missing or changed
outputs, and the commands, output layout, and verification limits are
documented.

## Format backlog

Audio CD, Video CD (VCD), Super Video CD (SVCD), and DVD-Audio are planned.
Their order is open.
