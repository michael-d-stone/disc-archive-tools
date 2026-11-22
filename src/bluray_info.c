// Copyright (C) 2026 Michael Stone
// SPDX-License-Identifier: GPL-2.0-or-later
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <udfread/udfread.h>
#include <libbluray/bluray.h>

static void streams(const BLURAY_STREAM_INFO *s, unsigned count, const char *type, int *comma)
{
    for (unsigned i = 0; i < count; i++) {
        printf("%s{\"type\":\"%s\",\"coding\":%u,\"pid\":%u,\"language\":\"%.3s\"}",
               *comma ? "," : "", type, s[i].coding_type, s[i].pid, s[i].lang);
        *comma = 1;
    }
}

static UDFDIR *find_directory(UDFDIR *parent, const char *name)
{
    struct udfread_dirent entry;
    while (udfread_readdir(parent, &entry)) {
        if (entry.d_type == UDF_DT_DIR && !strcasecmp(entry.d_name, name))
            return udfread_opendir_at(parent, entry.d_name);
    }
    return NULL;
}

static int image_playlists(const char *path, unsigned char *ids)
{
    udfread *udf = udfread_init();
    if (!udf || udfread_open(udf, path) < 0) {
        if (udf)
            udfread_close(udf);
        return 1;
    }
    UDFDIR *root = udfread_opendir(udf, "/");
    UDFDIR *bdmv = root ? find_directory(root, "BDMV") : NULL;
    UDFDIR *playlist = bdmv ? find_directory(bdmv, "PLAYLIST") : NULL;
    int count = 0;
    if (playlist) {
        struct udfread_dirent entry;
        while (udfread_readdir(playlist, &entry)) {
            const char *name = entry.d_name;
            if (entry.d_type != UDF_DT_REG || strlen(name) != 10 ||
                strcasecmp(name + 5, ".mpls"))
                continue;
            int valid = 1;
            for (int i = 0; i < 5; i++)
                valid = valid && isdigit((unsigned char)name[i]);
            if (valid) {
                ids[atoi(name)] = 1;
                count++;
            }
        }
        udfread_closedir(playlist);
    }
    if (bdmv)
        udfread_closedir(bdmv);
    if (root)
        udfread_closedir(root);
    udfread_close(udf);
    return count ? 0 : 1;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Usage: bluray-info SOURCE\n");
        return 1;
    }
    struct stat st;
    unsigned char *authored = calloc(100000, 1);
    unsigned char *seen = calloc(100000, 1);
    if (!authored || !seen || stat(argv[1], &st))
        return 1;
    int image = S_ISREG(st.st_mode);
    if (image && image_playlists(argv[1], authored)) {
        fputs("Cannot enumerate MPLS files in Blu-ray image\n", stderr);
        return 1;
    }
    BLURAY *bd = bd_open(argv[1], NULL);
    if (!bd) {
        fprintf(stderr, "Cannot open Blu-ray source\n");
        return 1;
    }
    const BLURAY_DISC_INFO *disc = bd_get_disc_info(bd);
    uint32_t count = bd_get_titles(bd, TITLES_ALL, 0);
    if (!count) {
        fprintf(stderr, "No Blu-ray playlists found\n");
        bd_close(bd);
        return 1;
    }
    printf("{\"menus\":{\"hdmv_titles\":%u,\"bdj_titles\":%u},\"playlists\":[",
           disc ? disc->num_hdmv_titles : 0, disc ? disc->num_bdj_titles : 0);
    for (uint32_t i = 0; i < count; i++) {
        BLURAY_TITLE_INFO *info = bd_get_title_info(bd, i, 0);
        if (!info) {
            fprintf(stderr, "Cannot inspect playlist at index %u\n", i);
            bd_close(bd);
            return 1;
        }
        if (info->playlist >= 100000 || seen[info->playlist]) {
            fputs("Invalid or duplicate libbluray playlist number\n", stderr);
            bd_free_title_info(info);
            bd_close(bd);
            return 1;
        }
        seen[info->playlist] = 1;
        printf("%s{\"id\":%u,\"duration\":%.9f,\"angles\":%u,\"chapters\":[",
               i ? "," : "", info->playlist, info->duration / 90000.0, info->angle_count);
        for (uint32_t j = 0; j < info->chapter_count; j++)
            printf("%s%.9f", j ? "," : "", info->chapters[j].start / 90000.0);
        printf("],\"clips\":[");
        for (uint32_t j = 0; j < info->clip_count; j++) {
            BLURAY_CLIP_INFO *c = &info->clips[j];
            printf("%s{\"id\":\"%.5s\",\"start\":%.9f,\"in\":%.9f,\"out\":%.9f,"
                   "\"still_mode\":%u,\"interactive_graphics\":%u,\"secondary_audio\":%u,"
                   "\"secondary_video\":%u,\"streams\":[", j ? "," : "", c->clip_id,
                   c->start_time / 90000.0, c->in_time / 90000.0, c->out_time / 90000.0,
                   c->still_mode, c->ig_stream_count, c->sec_audio_stream_count, c->sec_video_stream_count);
            int comma = 0;
            streams(c->video_streams, c->video_stream_count, "video", &comma);
            streams(c->audio_streams, c->audio_stream_count, "audio", &comma);
            streams(c->pg_streams, c->pg_stream_count, "subtitle", &comma);
            printf("]}");
        }
        printf("]}");
        bd_free_title_info(info);
    }
    puts("]}");
    bd_close(bd);
    if (image && memcmp(authored, seen, 100000)) {
        fputs("libbluray playlist inventory differs from MPLS files in image\n", stderr);
        free(authored);
        free(seen);
        return 1;
    }
    free(authored);
    free(seen);
    return 0;
}
