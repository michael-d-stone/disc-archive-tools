# Copyright (C) 2026 Michael Stone
# SPDX-License-Identifier: GPL-2.0-or-later

FFMPEG_VERSION = 9.0.1
FFMPEG_ARCHIVE = vendor/ffmpeg-$(FFMPEG_VERSION).tar.xz
FFMPEG_BUILD = build/ffmpeg-$(FFMPEG_VERSION)
FFMPEG_PREFIX = /opt/ffmpeg-dvd
CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra
CPPFLAGS ?=
LDFLAGS ?=

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin

PROGRAM = build-ifo-dump
SCRIPTS = scripts/dvd-title-extract scripts/dvd-menu-extract scripts/dvd-extract scripts/dvd-verify

.PHONY: all disc-archive-tools clean install install-disc-archive-tools uninstall test ffmpeg install-ffmpeg

all: disc-archive-tools

disc-archive-tools: $(PROGRAM)

$(PROGRAM): src/ifo_dump.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $< $(LDFLAGS) -ldvdread

clean:
	rm -f $(PROGRAM)

install: install-disc-archive-tools

install-disc-archive-tools:
	test -x "$(PROGRAM)" || { echo "error: run 'make disc-archive-tools' first"; exit 1; }
	install -d "$(DESTDIR)$(BINDIR)"
	install -m 755 $(PROGRAM) "$(DESTDIR)$(BINDIR)/dvd-ifo-dump"
	install -m 755 $(SCRIPTS) "$(DESTDIR)$(BINDIR)/"

uninstall:
	rm -f \
		"$(DESTDIR)$(BINDIR)/dvd-ifo-dump" \
		"$(DESTDIR)$(BINDIR)/dvd-title-extract" \
		"$(DESTDIR)$(BINDIR)/dvd-menu-extract" \
		"$(DESTDIR)$(BINDIR)/dvd-extract" \
		"$(DESTDIR)$(BINDIR)/dvd-verify"

test:
		tests/test-dvd-extract.py \
		tests/fixtures/annette.json \
		test_dvd_extract
		tests/test-dvd-extract.py \
		tests/fixtures/seinfeld-s1d1.json \
		test_seinfeld_extract

ffmpeg:
	cd vendor && sha256sum -c SHA256SUMS
	rm -rf "$(FFMPEG_BUILD)"
	mkdir -p build
	tar -C build -xf "$(FFMPEG_ARCHIVE)"
	cd "$(FFMPEG_BUILD)" && ./configure \
		--prefix="$(FFMPEG_PREFIX)" \
		--enable-gpl \
		--enable-libdvdread \
		--enable-libdvdnav
	$(MAKE) -C "$(FFMPEG_BUILD)" -j"$$(nproc)"

install-ffmpeg:
	$(MAKE) -C "$(FFMPEG_BUILD)" install
