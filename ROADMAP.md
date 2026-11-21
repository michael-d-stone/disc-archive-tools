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

### Investigate disc 2 galleries — open

Asa Akira Is Pure disc 2 titles 7–17 have far fewer extracted video packets and
chapter markers than their authored durations and chapter counts suggest. They
appear to be still-image galleries. The updated verifier flagged all 11 as
incomplete in a staging copy. Gallery recovery remains open.
Keep the original ISO and extraction. Record what a DVD player displays and in
what order, then compare that record with the authored durations and chapters,
the DVD reader's packet output, and the current MKVs.

Use the comparison to choose a preservation format. This milestone is complete
when the preserved output accounts for each observed gallery item in order,
verification flags incomplete galleries separately from receipt or checksum
failures, and any unsupported behavior is documented. Add regression coverage
for a complete gallery, an incomplete gallery, and an ordinary motion-video
title.

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
