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
GALLERY_PROGRAM = build-gallery-nav
SCRIPTS = scripts/dvd-archive scripts/dvd-title-extract scripts/dvd-menu-extract scripts/dvd-extract scripts/dvd-verify scripts/dvd-gallery-extract

.PHONY: all disc-archive-tools clean install install-disc-archive-tools uninstall test test-fixtures ffmpeg install-ffmpeg

all: disc-archive-tools

disc-archive-tools: $(PROGRAM) $(GALLERY_PROGRAM)

$(PROGRAM): src/ifo_dump.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $< $(LDFLAGS) -ldvdread

$(GALLERY_PROGRAM): src/gallery_nav.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@.tmp $< $(LDFLAGS) -ldvdnav -ldvdread
	mv $@.tmp $@

clean:
	rm -f $(PROGRAM) $(GALLERY_PROGRAM)

install: install-disc-archive-tools

install-disc-archive-tools:
	test -x "$(PROGRAM)" && test -x "$(GALLERY_PROGRAM)" || { echo "error: run 'make disc-archive-tools' first"; exit 1; }
	install -d "$(DESTDIR)$(BINDIR)"
	install -m 755 $(PROGRAM) "$(DESTDIR)$(BINDIR)/dvd-ifo-dump"
	install -m 755 $(GALLERY_PROGRAM) "$(DESTDIR)$(BINDIR)/dvd-gallery-nav"
	install -m 755 $(SCRIPTS) "$(DESTDIR)$(BINDIR)/"

uninstall:
	rm -f "$(DESTDIR)$(BINDIR)/dvd-archive"
	rm -f \
		"$(DESTDIR)$(BINDIR)/dvd-ifo-dump" \
		"$(DESTDIR)$(BINDIR)/dvd-title-extract" \
		"$(DESTDIR)$(BINDIR)/dvd-menu-extract" \
		"$(DESTDIR)$(BINDIR)/dvd-extract" \
		"$(DESTDIR)$(BINDIR)/dvd-verify" \
		"$(DESTDIR)$(BINDIR)/dvd-gallery-nav" \
		"$(DESTDIR)$(BINDIR)/dvd-gallery-extract"

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'

test-fixtures:
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
		--enable-libdvdnav \
		--enable-libbluray
	$(MAKE) -C "$(FFMPEG_BUILD)" -j"$$(nproc)"

install-ffmpeg:
	$(MAKE) -C "$(FFMPEG_BUILD)" install
