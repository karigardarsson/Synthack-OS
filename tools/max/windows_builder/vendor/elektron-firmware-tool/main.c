/* elektron-firmware-tool -- inspect and modify Elektron instrument OS files. */
#include "firmware.h"
#include "report.h"
#include "aplib.h"
#include "device.h"
#include "util.h"
#include <errno.h>
#include <sys/stat.h>

static int opt_verbose = 0; /* -v: full report, packet dumps, key */

/* --emit-container: path to write the raw container (the bin layer inside the
 * .syx) to. With -i alone this is the container as parsed from the input; with
 * -c/-V/-r it is the rebuilt one, captured at the point the encoder sees it. */
static const char *opt_emit_container = NULL;

/* -------------------------------- file I/O -------------------------------- */

/* fclose can be where a buffered write finally fails (a full disk), so its
 * result decides success just as much as fwrite's. */
static int write_file(const char *path, const uint8_t *data, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        perror(path);
        return -1;
    }
    int ok = (fwrite(data, 1, n, f) == n);
    if (!ok)
        perror(path);
    if (fclose(f) != 0) {
        perror(path);
        ok = 0;
    }
    return ok ? 0 : -1;
}

static int make_outdir(const char *path) {
    char tmp[1024];
    snprintf(tmp, sizeof tmp, "%s", path);
    size_t len = strlen(tmp);
    if (len && tmp[len - 1] == '/')
        tmp[len - 1] = 0;
    for (char *p = tmp + 1; *p; p++)
        if (*p == '/') {
            *p = 0;
            if (mkdir(tmp, 0755) != 0 && errno != EEXIST)
                return -1;
            *p = '/';
        }
    if (mkdir(tmp, 0755) != 0 && errno != EEXIST)
        return -1;
    return 0;
}

static int write_in_dir(const char *dir, const char *name, const uint8_t *d, size_t n) {
    char fn[1024];
    snprintf(fn, sizeof fn, "%s/%s", dir, name);
    return write_file(fn, d, n);
}

static void spaces_to_underscores(char *s) {
    for (char *p = s; *p; p++)
        if (*p == ' ')
            *p = '_';
}

/* Output filename for an extracted section. */
static void section_fname(char *dst, size_t cap, const bin_info *b, const section_result *sr,
                          const char *ext) {
    if (b->type == CT_PREELE) {
        if (sr->compressed) {
            char k[16];
            snprintf(k, sizeof k, "%s", section_display_name(b, sr));
            spaces_to_underscores(k);
            snprintf(dst, cap, "section_%u_%s.%s", sr->id, k, ext);
        } else {
            snprintf(dst, cap, "section_%u.%s", sr->id, ext);
        }
        return;
    }
    snprintf(dst, cap, "section_%u_%s.%s", sr->id, elektron_section_name(sr->id), ext);
    spaces_to_underscores(dst);
}

/* -------------------------------- commands -------------------------------- */

static int cmd_info(const char *in) {
    firmware fw;
    int rc = fw_load(in, &fw);
    if (rc == 0) {
        verify_result vr;
        fw_verify(&fw, &vr);
        if (opt_emit_container) {
            /* The container proper, not everything up to the end of the decoded
             * stream: the transport pads its last packet, and those bytes are
             * outside the container. Emitting declared_size keeps this path
             * byte-identical to the one in cmd_replace. */
            const bin_info *b = &fw.bin;
            size_t n = (b->declared_size && b->declared_size <= b->len) ? b->declared_size : b->len;
            if (write_file(opt_emit_container, b->data, n) != 0) {
                fw_free(&fw);
                return 1; /* the file was asked for; not producing it is a failure */
            }
        }
        if (opt_verbose)
            report_full(&fw, &vr, opt_verbose);
        else
            report_summary(&fw, &vr);
        fw_free(&fw);
        return 0;
    }
    if (rc == -2 && fw.sysex_ok) {
        report_sysex(&fw);
        report_unknown_container();
        fw_free(&fw);
        return 0;
    }
    fprintf(stderr, "info: %s is not a recognizable Elektron OS .syx\n", in);
    fw_free(&fw);
    return 1;
}

/* Decompress sections out of a .syx into outdir. */
static int cmd_extract(const char *in, const char *outdir, const uint32_t *ids, int nids,
                       int want_all) {
    firmware fw;
    int rc = fw_load(in, &fw);
    if (rc != 0) {
        fprintf(stderr, "extract: %s is not a supported Elektron OS .syx\n", in);
        fw_free(&fw);
        return 1;
    }
    if (make_outdir(outdir) != 0) {
        fprintf(stderr, "cannot create %s: %s\n", outdir, strerror(errno));
        fw_free(&fw);
        return 1;
    }

    verify_result vr;
    fw_verify(&fw, &vr);
    if (opt_verbose)
        report_full(&fw, &vr, opt_verbose);
    printf("=== extract -> %s ===\n", outdir);

    const bin_info *b = &fw.bin;
    for (uint32_t s = 0; s < b->nsections; s++) {
        const ele3_section *sec  = &b->sections[s];
        const section_result *sr = &vr.sections[s];
        int want                 = want_all;
        for (int q = 0; q < nids && !want; q++)
            if (ids[q] == sec->id)
                want = 1;
        if (!want)
            continue;
        if (!sr->in_range) {
            fprintf(stderr, "  section %u out of range\n", sec->id);
            continue;
        }
        char name[128];
        if (sr->compressed) {
            /* fw_verify already proved this depacks; redo it for the bytes. */
            size_t n = container_section_depack(b, sec, fw.scratch, fw.scratch_cap);
            section_fname(name, sizeof name, b, sr, "bin");
            write_in_dir(outdir, name, fw.scratch, n);
            printf("  %-28s %zu B\n", name, n);
        } else {
            size_t rn = fits(b->len, sec->offset, sec->comp_len)
                            ? sec->comp_len
                            : (sec->offset < b->len ? b->len - sec->offset : 0);
            section_fname(name, sizeof name, b, sr, "raw");
            write_in_dir(outdir, name, b->data + sec->offset, rn);
            printf("  %-28s %zu B (raw)\n", name, rn);
        }
    }
    for (int q = 0; q < nids; q++)
        if (!container_find_section(b, ids[q]))
            fprintf(stderr, "  (no section id=%u)\n", ids[q]);

    fw_free(&fw);
    return 0;
}

static int section_index(const bin_info *b, uint32_t id) {
    for (uint32_t s = 0; s < b->nsections; s++)
        if (b->sections[s].id == id)
            return (int)s;
    return -1;
}

static const char *trailer_note(container_type ct) {
    switch (ct) {
        case CT_ELE2: return "none (ELE2, even-padded)";
        case CT_AD: return "none (AD raw image, CRC-32 recomputed)";
        case CT_PREELE: return "none (pre-ELE, sections + metadata)";
        case CT_ELEK: return "none (ELEK, header + section)";
        default: return NULL; /* ELE3: decided after the version is set */
    }
}

/* Replace one or more sections with raw files, recompute every gate, write a new
 * .syx. Device, checksum seed, marker and untouched sections all come from in. */
static int cmd_replace(const char *in_syx, const char *out_syx, override *ovs, int novs,
                       const char *newver, int level) {
    firmware fw;
    int rc = fw_load(in_syx, &fw);
    if (rc != 0) {
        fprintf(stderr, "replace: %s is not a supported Elektron OS .syx\n", in_syx);
        fw_free(&fw);
        return 1;
    }
    if (!fw.bin.have_key && fw.bin.trailer_bytes != 0) {
        fprintf(stderr,
                "replace: %s has an unrecognized %zu-byte container trailer; "
                "cannot rebuild safely\n",
                elektron_device_name(fw.sysex.device), fw.bin.trailer_bytes);
        fw_free(&fw);
        return 1;
    }
    for (int i = 0; i < novs; i++) {
        if (!container_find_section(&fw.bin, ovs[i].id)) {
            fprintf(stderr, "replace: no section id=%u\n", ovs[i].id);
            fw_free(&fw);
            return 1;
        }
    }

    verify_result vr;
    fw_verify(&fw, &vr);
    if (opt_verbose)
        report_full(&fw, &vr, opt_verbose);

    int rcode   = 1;
    uint8_t *nc = NULL, *osyx = NULL;

    printf("=== %s -> %s ===\n", novs ? "replace" : "repack", out_syx);
    for (int i = 0; i < novs; i++) {
        ovs[i].data = read_file(ovs[i].file, &ovs[i].len);
        if (!ovs[i].data)
            goto done;
        int idx = section_index(&fw.bin, ovs[i].id);
        printf("  id=%u (%s) <- %s (%zu B, %s)\n", ovs[i].id, elektron_section_name(ovs[i].id),
               ovs[i].file, ovs[i].len,
               (idx >= 0 && vr.sections[idx].compressed) ? "compressed" : "stored raw");
    }

    /* Upper bound on the rebuilt container: the original, plus worst-case growth
     * for every recompressed override, plus per-section alignment and the
     * padded HMAC trailer. */
    size_t cap = fw.bin.len + CONTAINER_ALIGN * (size_t)ELE3_MAX_SECTIONS + 4096;
    for (int i = 0; i < novs; i++)
        cap += ovs[i].len + ovs[i].len / 2 + 256;
    nc = xalloc(cap);

    size_t nclen = container_build(&fw.bin, nc, cap, ovs, novs, fw.scratch, fw.scratch_cap, level);
    if (nclen == (size_t)-1) {
        fprintf(stderr, "replace: cannot rebuild container "
                        "(recompression failed or output too large)\n");
        goto done;
    }
    const char *note = trailer_note(fw.bin.type);
    if (note)
        printf("  trailer               : %s\n", note);

    if (newver) { /* set the version before any checksum or HMAC covers it */
        int v = container_set_version(nc, nclen, fw.bin.type, newver);
        if (v == 0)
            printf("  version               : set to \"%s\"\n", newver);
        else if (v == -2)
            printf("  version               : (not editable for %s; unchanged)\n",
                   fw.bin.type == CT_PREELE ? "pre-ELE" : "this container");
        else if (v == -3)
            printf("  version               : (\"%s\" too long for field; unchanged)\n", newver);
        else
            printf("  version               : (field not found; unchanged)\n");
    }

    if (fw.bin.type == CT_ELE3) {
        nclen = fw.bin.have_key ? container_append_trailer(nc, cap, nclen, fw.bin.key)
                                : align_up(nclen, CONTAINER_ALIGN);
        if (nclen == (size_t)-1 || nclen > cap) {
            fprintf(stderr, "replace: rebuilt container does not fit its buffer\n");
            goto done;
        }
        printf("  trailer               : %s\n", fw.bin.have_key ? "HMAC-SHA256" : "none");
    }
    printf("  container             : %zu -> %zu bytes\n", fw.bin.declared_size, nclen);

    /* Emit here, not straight after container_build: for ELE3 the version and
     * the HMAC trailer are both applied above, so only at this point do the
     * bytes match what the encoder is about to wrap. */
    if (opt_emit_container && write_file(opt_emit_container, nc, nclen) != 0)
        goto done;

    size_t olen = 0;
    if (fw.bin.type == CT_PREELE) {
        osyx = preele_encode(nc, nclen, fw.sysex.device, fw.sysex.ts.last_pay,
                             fw.sysex.ts.last_pay_len, &olen, opt_verbose);
    } else if (fw.bin.type == CT_ELEK) {
        osyx = elek_encode(nc, nclen, fw.sysex.device, fw.sysex.ts.last_pay,
                           fw.sysex.ts.last_pay_len, &olen, opt_verbose);
    } else {
        uint8_t preamble[SYX_PREAMBLE];
        syx_build_preamble(preamble, nc, nclen);
        if (opt_verbose)
            printf("  content checksum      : 0x%08x\n", be32(preamble + 4));
        osyx = syx_encode(nc, nclen, fw.sysex.device, preamble, fw.sysex.base,
                          fw.sysex.have_marker ? fw.sysex.info : NULL, &olen, opt_verbose);
    }
    if (!osyx) {
        fprintf(stderr, "replace: cannot encode the output .syx\n");
        goto done;
    }
    if (write_file(out_syx, osyx, olen) == 0) {
        printf("=== wrote %s (%zu bytes, %s) ===\n", out_syx, olen,
               elektron_device_name(fw.sysex.device));
        rcode = 0;
    }

done:
    for (int i = 0; i < novs; i++)
        free(ovs[i].data);
    free(nc);
    free(osyx);
    fw_free(&fw);
    return rcode;
}

/* ---------------------------------- main ---------------------------------- */

static void print_usage(const char *prog, FILE *o) {
    fprintf(o,
            "usage:\n"
            "  %s -i <in.syx>                                  summary and checksum verdict\n"
            "  %s -i <in.syx> -v                               full report of every layer\n"
            "  %s -i <in.syx> [-d N]... -o <outdir>            decompress sections (all if no "
            "-d)\n"
            "  %s -i <in.syx> [-c N <file>]... [-V VER] -o <out.syx>   replace sections / set "
            "version\n"
            "  %s -h\n"
            "\n"
            "  -i, --input   <file>      input .syx (also accepted as a bare argument)\n"
            "  -o, --output  <path>      output folder (with -d) or .syx (with -c/-V)\n"
            "  -d, --decompress N        decompress section N (repeatable)\n"
            "  -c, --compress   N F      replace section N with raw file F (repeatable)\n"
            "  -V, --set-version VER     set the version string in the output .syx\n"
            "                            (ELE3/ELE2/ELEK; --version is a deprecated alias)\n"
            "  -r, --repack              rebuild without changing anything; sections are\n"
            "                            copied verbatim, so the output is byte-identical\n"
            "                            to the input for a well-formed file\n"
            "  -l, --level     N         compression effort %d..%d (default %d): higher is\n"
            "                            smaller but slower. Level %d is roughly 18x faster\n"
            "                            than %d and about 3%% larger.\n"
            "  -v, --verbose             verbose output\n"
            "      --emit-container F    also write the raw container to F: as parsed from\n"
            "                            the input with -i, or as rebuilt with -c/-V/-r\n",
            prog, prog, prog, prog, prog, APLIB_LEVEL_MIN, APLIB_LEVEL_MAX, APLIB_LEVEL_DEFAULT,
            APLIB_LEVEL_MIN, APLIB_LEVEL_MAX);
}

/* Parse the numeric id argument following -d / -c. */
static int parse_id(const char *s, uint32_t *out) {
    char *end;
    unsigned long v = strtoul(s, &end, 0);
    if (*end || end == s)
        return -1;
    *out = (uint32_t)v;
    return 0;
}

int main(int argc, char **argv) {
    const char *input = NULL, *output = NULL, *newver = NULL;
    uint32_t d_ids[ELE3_MAX_SECTIONS];
    int nd = 0;
    override ovs[ELE3_MAX_SECTIONS];
    int nov    = 0;
    int level  = APLIB_LEVEL_DEFAULT;
    int repack = 0;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        if (!strcmp(a, "-h") || !strcmp(a, "--help")) {
            print_usage(argv[0], stdout);
            return 0;
        } else if (!strcmp(a, "-i") || !strcmp(a, "--input")) {
            if (i + 1 >= argc) {
                fprintf(stderr, "-i needs a .syx\n");
                return 2;
            }
            input = argv[++i];
        } else if (!strcmp(a, "-o") || !strcmp(a, "--output")) {
            if (i + 1 >= argc) {
                fprintf(stderr, "-o needs a path\n");
                return 2;
            }
            output = argv[++i];
        } else if (!strcmp(a, "--emit-container")) {
            if (i + 1 >= argc) {
                fprintf(stderr, "--emit-container needs a path\n");
                return 2;
            }
            opt_emit_container = argv[++i];
        } else if (!strcmp(a, "-v") || !strcmp(a, "--verbose")) {
            opt_verbose = 1;
        } else if (!strcmp(a, "-r") || !strcmp(a, "--repack")) {
            repack = 1;
        } else if (!strcmp(a, "-l") || !strcmp(a, "--level")) {
            uint32_t v;
            if (i + 1 >= argc || parse_id(argv[++i], &v) || (int)v > APLIB_LEVEL_MAX) {
                fprintf(stderr, "-l needs a level %d..%d\n", APLIB_LEVEL_MIN, APLIB_LEVEL_MAX);
                return 2;
            }
            level = (int)v;
        } else if (!strcmp(a, "-V") || !strcmp(a, "--set-version") ||
                   !strcmp(a, "--version")) { /* --version kept for compatibility */
            if (i + 1 >= argc) {
                fprintf(stderr, "%s needs a version string\n", a);
                return 2;
            }
            newver = argv[++i];
        } else if (!strcmp(a, "-d") || !strcmp(a, "--decompress")) {
            if (nd >= ELE3_MAX_SECTIONS) {
                fprintf(stderr, "too many -d options (max %d)\n", ELE3_MAX_SECTIONS);
                return 2;
            }
            if (i + 1 >= argc || parse_id(argv[++i], &d_ids[nd])) {
                fprintf(stderr, "-d needs a section id (number)\n");
                return 2;
            }
            nd++;
        } else if (!strcmp(a, "-c") || !strcmp(a, "--compress")) {
            if (nov >= ELE3_MAX_SECTIONS) {
                fprintf(stderr, "too many -c options (max %d)\n", ELE3_MAX_SECTIONS);
                return 2;
            }
            if (i + 2 >= argc || parse_id(argv[i + 1], &ovs[nov].id)) {
                fprintf(stderr, "-c needs <id> <file>\n");
                return 2;
            }
            ovs[nov].file = argv[i + 2];
            ovs[nov].data = NULL;
            ovs[nov].len  = 0;
            i += 2;
            nov++;
        } else if (a[0] == '-' && a[1]) {
            fprintf(stderr, "unknown option: %s\n", a);
            return 2;
        } else if (!input) {
            input = a;
        } else {
            fprintf(stderr, "unexpected argument: %s\n", a);
            return 2;
        }
    }

    if (!input) {
        print_usage(argv[0], stderr);
        return 2;
    }
    if (nov > 0 || newver || repack) {
        if (!output) {
            fprintf(stderr, "%s needs -o <out.syx>\n",
                    nov > 0 ? "compress" : (repack ? "repack" : "version"));
            return 2;
        }
        return cmd_replace(input, output, ovs, nov, newver, level);
    }
    if (nd > 0 || output) {
        if (!output) {
            fprintf(stderr, "extract needs -o <outdir>\n");
            return 2;
        }
        return cmd_extract(input, output, d_ids, nd, nd == 0);
    }
    return cmd_info(input);
}
