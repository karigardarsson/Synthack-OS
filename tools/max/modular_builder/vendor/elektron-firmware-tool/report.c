/* Reporting. */
#include "report.h"
#include "device.h"
#include "util.h"

/* Report labels are padded to 22 columns; print_hex and the one dynamic label
 * use "%-22s" to match. */
static const char *mark(check_state s) {
    return s == CHK_OK ? "ok" : "MISMATCH";
}

static int is_alnum(int ch) { /* locale-independent on purpose */
    return (ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z');
}

const char *container_type_name(container_type ct) {
    return ct == CT_ELE2     ? "ELE2"
           : ct == CT_AD     ? "AD"
           : ct == CT_PREELE ? "pre-ELE"
           : ct == CT_ELEK   ? "ELEK"
                             : "ELE3";
}

const char *section_display_name(const bin_info *b, const section_result *sr) {
    if (b->type == CT_PREELE)
        return sr->compressed ? elektron_preele_section_name(sr->head, sr->head_len) : "aPLib";
    return elektron_section_name(sr->id);
}

static void print_hex(const char *label, const uint8_t *p, size_t n) {
    printf("  %-22s: ", label);
    for (size_t i = 0; i < n; i++)
        printf("%02x", p[i]);
    printf("\n");
}

/* Byte offset of the version/build header for a container type, or -1. */
static int header_off(container_type ct) {
    return ct == CT_ELE2   ? ELE2_BUILD_OFF
           : ct == CT_ELEK ? ELEK_BUILD_OFF
           : ct == CT_ELE3 ? ELE3_BUILD_OFF
                           : -1;
}

/* Extract build/model and version for display. The model is the alphanumeric run
 * before the version, skipping any leading non-alphanumeric byte. */
static void header_fields(const uint8_t *c, size_t clen, container_type ct, char *model,
                          size_t mcap, char *ver, size_t vcap) {
    int build_off = header_off(ct);
    int lim       = container_header_end(ct);
    if (clen < (size_t)lim)
        lim = (int)clen;
    int voff = container_find_version_pattern(c, build_off, lim);

    int i = build_off;
    while (i < lim && !is_alnum(c[i])) /* skip a leading non-alphanumeric byte */
        i++;
    int end  = (voff >= 0) ? voff : lim;
    size_t n = 0;
    for (; i < end && n + 1 < mcap && is_alnum(c[i]); i++)
        model[n++] = (char)c[i];
    model[n] = 0;

    n = 0;
    if (voff >= 0)
        for (i = voff; i < lim && n + 1 < vcap && (is_alnum(c[i]) || c[i] == '.'); i++)
            ver[n++] = (char)c[i];
    ver[n] = 0;
}

static void report_header(const uint8_t *c, size_t clen, container_type ct) {
    char model[24], ver[24];
    header_fields(c, clen, ct, model, sizeof model, ver, sizeof ver);
    printf("  build/model           : %s\n", model[0] ? model : "?");
    printf("  version               : %s\n", ver[0] ? ver : "?");
}

/* Describe a captured transport marker by its command/kind byte. */
static const char *marker_kind(const uint8_t *m, int len) {
    if (len <= PK_CMD)
        return "?";
    if (m[PK_CMD] == SYX_CMD_DATA)
        return "empty packet"; /* pre-ELE/ELEK terminator */
    if (m[PK_CMD] == SYX_CMD_MARKER) {
        if (len > PK_MARKER_KIND && m[PK_MARKER_KIND] == MARKER_START)
            return "start";
        return "end"; /* ELE3 kind 0x02, or a legacy terminator */
    }
    return "?";
}

void report_sysex(const firmware *fw) {
    const transport_stats *ts = &fw->sysex.ts;
    printf("=== sysex transport ===\n");
    printf("  file size             : %zu bytes\n", ts->file_size);
    printf("  F0..F7 messages       : %zu\n", ts->nmsg);
    printf("  device                : 00 20 3C / 0x%02x (%s)\n", fw->sysex.device,
           elektron_device_name(fw->sysex.device));

    printf("  data packets          : %zu  (%zu-byte, cmd 7E)\n", ts->ndata, ts->pkt_body);
    if (ts->pkt_body == SYX_PKT) {
        printf("  blocks                : %d\n", ts->nblocks);
        printf("  packets/block         : min=%d max=%d\n", ts->min_pk, ts->max_pk);
        printf("  first block           : id=%ld  seq %ld..%ld\n", ts->first_block, ts->seq0,
               ts->seqN);
    }
    printf("  %-22s: %zu bytes (%zuB hdr + %zuB payload/pkt)\n",
           fw->bin.type == CT_PREELE ? "2+7+7 decoded" : "8-in-7 decoded", ts->decoded, ts->hdr,
           ts->pay);
    if (ts->pkt_ck_ok + ts->pkt_ck_bad > 0)
        printf("  per-packet checksum   : %zu/%zu  [%s]\n", ts->pkt_ck_ok,
               ts->pkt_ck_ok + ts->pkt_ck_bad, ts->pkt_ck_bad ? "MISMATCH" : "ok");

    printf("  marker messages       : %zu\n", ts->nmarker);
    for (int k = 0; k < ts->nmarker_saved; k++) {
        char lbl[32];
        snprintf(lbl, sizeof lbl, "marker[%d] (%dB)", k, ts->marker_len[k]);
        printf("    %-20s: ", lbl);
        for (int b = 0; b < ts->marker_len[k]; b++)
            printf("%02x", ts->marker[k][b]);
        printf("  (%s)\n", marker_kind(ts->marker[k], ts->marker_len[k]));
    }
    if (fw->sysex.have_marker) {
        printf("  byte-125 base seed    : 0x%02x\n", fw->sysex.base);
        printf("  start block/seq       : block=%u seq=%u\n",
               (((uint32_t)fw->sysex.info[1] << 7) | fw->sysex.info[2]), fw->sysex.info[3]);
        uint32_t declared = ((uint32_t)fw->sysex.info[4] << 14) |
                            ((uint32_t)fw->sysex.info[5] << 7) | fw->sysex.info[6];
        printf("  declared packet count : %u  [%s]\n", declared,
               declared == fw->sysex.ts.ndata ? "ok" : "MISMATCH");
    }
}

void report_bin(const firmware *fw, const verify_result *vr, int verbose) {
    const bin_info *b = &fw->bin;
    size_t size       = b->declared_size;
    printf("=== bin container (%s) ===\n", container_type_name(b->type));

    if (b->type == CT_AD) {
        printf("  format                : raw image (%u B)\n", b->sections[0].comp_len);
        printf("  image CRC-32          : stored 0x%08x  calc 0x%08x  [%s]\n", vr->crc_stored,
               vr->crc_calc, mark(vr->image_crc));
    } else if (b->type == CT_PREELE) {
        printf("  format                : aPLib sections (positional; no header table)\n");
    } else {
        report_header(b->data, b->len, b->type);
    }
    printf("  container size        : %zu bytes\n", size);
    if (b->type == CT_ELE3)
        printf("  content checksum      : stored 0x%08x  calc 0x%08x  [%s]\n", vr->content_stored,
               vr->content_calc, mark(vr->content_cksum));
    printf("  sections              : %u\n", b->nsections);

    printf("=== bin sections ===\n");
    for (uint32_t s = 0; s < b->nsections; s++) {
        const ele3_section *sec  = &b->sections[s];
        const section_result *sr = &vr->sections[s];
        printf("  id=%-2u %-10s  off=0x%06x  clen=0x%06x  dst=0x%08x", sec->id,
               section_display_name(b, sr), sec->offset, sec->comp_len, sec->dest);
        if (!sr->in_range) {
            printf("  (out of range)\n");
            continue;
        }
        if (sr->compressed)
            printf("  -> %9zu B  stream-sum stored 0x%08x calc 0x%08x  [%s]\n",
                   sr->decompressed_len, sr->sum_stored, sr->sum_calc, mark(sr->stream_sum));
        else
            printf("  (raw/uncompressed)\n");
    }

    if (b->have_key) {
        printf("=== bin trailer ===\n");
        printf("  type                  : HMAC-SHA256 digest\n");
        if (verbose) {
            printf("  derivation string     : \"%s\"\n", b->key_str);
            print_hex("key (from input)", b->key, DIGEST_LEN);
        }
        if (vr->digest != CHK_ABSENT) {
            if (verbose) {
                print_hex("digest stored", vr->digest_stored, DIGEST_LEN);
                print_hex("digest calc", vr->digest_calc, DIGEST_LEN);
            }
            printf("  digest                : [%s]\n", mark(vr->digest));
        }
    } else if (b->trailer_bytes != 0) {
        printf("=== bin trailer ===\n");
        printf("  type                  : unrecognized (%zu bytes past sections)\n",
               b->trailer_bytes);
    }
}

void report_full(const firmware *fw, const verify_result *vr, int verbose) {
    report_sysex(fw);
    report_bin(fw, vr, verbose);
}

void report_summary(const firmware *fw, const verify_result *vr) {
    const bin_info *b = &fw->bin;
    printf("device    : %s (0x%02x)\n", elektron_device_name(fw->sysex.device), fw->sysex.device);
    int ho = header_off(b->type);
    if (ho >= 0) {
        char model[24], ver[24];
        header_fields(b->data, b->len, b->type, model, sizeof model, ver, sizeof ver);
        if (ver[0])
            printf("version   : %s\n", ver);
    }
    printf("container : %s, %zu B\n", container_type_name(b->type), b->declared_size);
    printf("sections  :\n");
    for (uint32_t s = 0; s < b->nsections; s++) {
        const section_result *sr = &vr->sections[s];
        const char *nm           = section_display_name(b, sr);
        if (sr->compressed)
            printf("  id %-2u  %-8s %9zu B\n", sr->id, nm, sr->decompressed_len);
        else
            printf("  id %-2u  %-8s %9u B (raw)\n", sr->id, nm, b->sections[s].comp_len);
    }
    printf("checksums : %s\n", vr->all_ok ? "ok" : "MISMATCH");
}

void report_unknown_container(void) {
    printf("=== bin container ===\n");
    printf("  type                  : unrecognized (no known container magic)\n");
}
