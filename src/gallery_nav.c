// Copyright (C) 2026 Michael Stone
// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <dvdnav/dvdnav.h>
#include <dvdread/ifo_read.h>

static int inventory(const char *source)
{
    dvd_reader_t *dvd = DVDOpen(source);
    if (!dvd)
        return 1;
    ifo_handle_t *vmg = ifoOpen(dvd, 0);
    int status = 1;
    if (!vmg || !vmg->tt_srpt)
        goto done;
    for (unsigned n = 0; n < vmg->tt_srpt->nr_of_srpts; ++n) {
        title_info_t title = vmg->tt_srpt->title[n];
        ifo_handle_t *vts = ifoOpen(dvd, title.title_set_nr);
        if (!vts || !vts->vts_ptt_srpt || !vts->vts_pgcit || !title.vts_ttn ||
            title.vts_ttn > vts->vts_ptt_srpt->nr_of_srpts) {
            if (vts)
                ifoClose(vts);
            goto done;
        }
        ttu_t parts = vts->vts_ptt_srpt->title[title.vts_ttn - 1];
        unsigned holds[99], count = 0;
        if (title.nr_of_angles == 1 && parts.ptt && parts.nr_of_ptts <= 99) {
            for (unsigned p = 0; p < parts.nr_of_ptts; ++p) {
                ptt_info_t part = parts.ptt[p];
                if (!part.pgcn || part.pgcn > vts->vts_pgcit->nr_of_pgci_srp)
                    continue;
                pgc_t *pgc = vts->vts_pgcit->pgci_srp[part.pgcn - 1].pgc;
                if (!pgc || !part.pgn || part.pgn > pgc->nr_of_programs ||
                    !pgc->program_map || !pgc->cell_playback)
                    continue;
                unsigned cell = pgc->program_map[part.pgn - 1];
                if (cell && cell <= pgc->nr_of_cells &&
                    pgc->cell_playback[cell - 1].still_time == 255)
                    holds[count++] = p + 1;
            }
        }
        if (count >= 2) {
            printf("gallery %u", n + 1);
            for (unsigned p = 0; p < count; ++p)
                printf(" %u", holds[p]);
            puts("");
        }
        ifoClose(vts);
    }
    status = 0;
done:
    if (status)
        fputs("Could not read DVD gallery IFO tables\n", stderr);
    if (vmg)
        ifoClose(vmg);
    DVDClose(dvd);
    return status;
}

/* Run the VM until it needs input, enters a menu, or stops. WAIT only
 * drains the player's buffer, so it can be acknowledged immediately. */
static int position(dvdnav_t *nav, int allow_exit)
{
    union {
        unsigned char bytes[2048];
        dvdnav_still_event_t still;
        dvdnav_cell_change_event_t cell;
    } block;
    int cell = 0;
    for (unsigned i = 0; i < 100000; ++i) {
        int32_t event, length;
        if (dvdnav_get_next_block(nav, block.bytes, &event, &length) != DVDNAV_STATUS_OK)
            return 1;
        if (allow_exit && (dvdnav_is_domain_vmgm(nav) || dvdnav_is_domain_vtsm(nav))) {
            printf("point exit %s\n", dvdnav_is_domain_vmgm(nav) ? "title-menu" : "root-menu");
            return 0;
        }
        switch (event) {
        case DVDNAV_CELL_CHANGE:
            cell = block.cell.cellN;
            break;
        case DVDNAV_WAIT:
            if (dvdnav_wait_skip(nav) != DVDNAV_STATUS_OK)
                return 1;
            break;
        case DVDNAV_STOP:
            if (!allow_exit)
                return 1;
            puts("point exit stop");
            return 0;
        case DVDNAV_STILL_FRAME: {
            int32_t title, chapter, program, pgc, unused;
            pci_t *pci = dvdnav_get_current_nav_pci(nav);
            if (dvdnav_current_title_info(nav, &title, &chapter) != DVDNAV_STATUS_OK ||
                dvdnav_current_title_program(nav, &unused, &pgc, &program) != DVDNAV_STATUS_OK ||
                title <= 0 || chapter <= 0 || cell <= 0)
                return 1;
            printf("point still %d %d %d %d %d %d %d\n", title, chapter, pgc, cell,
                   block.still.length, pci ? pci->hli.hl_gi.btn_ns : 0,
                   dvdnav_get_video_aspect(nav));
            return 0;
        }
        }
    }
    return 1;
}

static int trace(const char *source, int title, int chapter, const char *action)
{
    dvdnav_t *nav;
    if (dvdnav_open(&nav, source) != DVDNAV_STATUS_OK)
        return 1;
    int result = 1;
    if (dvdnav_part_play(nav, title, chapter) != DVDNAV_STATUS_OK || position(nav, 0))
        goto done;

    dvdnav_status_t status;
    user_ops_t prohibited = dvdnav_get_restrictions(nav);
    if (!strcmp(action, "entry")) {
        result = 0;
        goto done;
    } else if (!strcmp(action, "next")) {
        status = prohibited.next_pg_search ? DVDNAV_STATUS_ERR : dvdnav_next_pg_search(nav);
    } else if (!strcmp(action, "previous")) {
        status = prohibited.prev_or_top_pg_search ? DVDNAV_STATUS_ERR : dvdnav_prev_pg_search(nav);
    } else if (!strcmp(action, "root-menu")) {
        status = prohibited.root_menu_call ? DVDNAV_STATUS_ERR : dvdnav_menu_call(nav, DVD_MENU_Root);
    } else if (!strcmp(action, "title-menu")) {
        status = prohibited.title_menu_call ? DVDNAV_STATUS_ERR : dvdnav_menu_call(nav, DVD_MENU_Title);
    } else if (!strcmp(action, "return")) {
        status = prohibited.go_up ? DVDNAV_STATUS_ERR : dvdnav_go_up(nav);
    } else if (!strcmp(action, "timeout")) {
        status = dvdnav_still_skip(nav);
    } else {
        goto done;
    }
    if (status != DVDNAV_STATUS_OK && strcmp(action, "timeout")) {
        puts("point unavailable");
        result = 0;
    } else if (status == DVDNAV_STATUS_OK) {
        result = position(nav, 1);
    }
done:
    if (result)
        fprintf(stderr, "Navigation failed at title %d chapter %d (%s): %s\n",
                title, chapter, action, dvdnav_err_to_string(nav));
    dvdnav_close(nav);
    return result;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "inventory"))
        return inventory(argv[2]);
    if (argc == 6 && !strcmp(argv[1], "trace"))
        return trace(argv[2], atoi(argv[3]), atoi(argv[4]), argv[5]);
    fputs("Usage: dvd-gallery-nav inventory SOURCE | trace SOURCE TITLE CHAPTER ACTION\n", stderr);
    return 1;
}
