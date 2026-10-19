/* Container parsing and assembly. */
#include "container.h"
#include "aplib.h"
#include "device.h"
#include "util.h"

/* --------------------------------- parsing --------------------------------- */

static container_type magic_of(const uint8_t *p) {
    if (!memcmp(p, "ELE3", 4))
        return CT_ELE3;
    if (!memcmp(p, "ELE2", 4))
        return CT_ELE2;
    if (!memcmp(p, "ELEK", 4))
        return CT_ELEK;
    if (p[0] == 'A' && p[1] == 'D' && p[2] == 0x0f && p[3] == 0x00)
        return CT_AD;
    return CT_NONE;
}

container_type container_detect(const uint8_t *stream, size_t len, uint8_t dev, size_t *off) {
    if (dev == DEV_MACHINEDRUM || dev == DEV_MONOMACHINE) {
        *off = 0; /* no magic; the container starts at byte 0 */
        return CT_PREELE;
    }
    for (size_t e = 0; e + 4 <= len; e++) {
        container_type ct = magic_of(stream + e);
        if (ct != CT_NONE) {
            *off = e;
            return ct;
        }
    }
    *off = 0;
    return CT_NONE;
}

/* Smallest container with all of its fixed-offset header fields present. The
 * magic only proves 4 readable bytes, so this is what makes reading them safe. */
static size_t container_min_len(container_type ct) {
    switch (ct) {
        case CT_ELE3: return ELE3_TABLE_OFF; /* section count + table start */
        case CT_ELE2: return ELE2_SECT_OFF + 4;
        case CT_ELEK: return ELEK_SECT_OFF + 4;
        case CT_AD: return AD_IMG_OFF;
        default: return 0; /* pre-ELE: no fixed header */
    }
}

/* A declared section length is attacker-controlled; keep it inside the buffer. */
static uint32_t clamp_len(size_t want, size_t off, size_t clen) {
    size_t avail = (off < clen) ? clen - off : 0;
    return (uint32_t)(want <= avail ? want : avail);
}

static ele3_section table_entry(const uint8_t *ele3, uint32_t idx) {
    const uint8_t *e = ele3 + ELE3_TABLE_OFF + idx * ELE3_ENTRY_SZ;
    ele3_section s   = {be32(e), be32(e + 4), be32(e + 8), be32(e + 12)};
    return s;
}

/* Walk pre-ELE sections positionally: a run of [size][sum] streams with
 * unstructured metadata between them, validated by the stored byte sum. */
static void parse_preele(const uint8_t *c, size_t clen, bin_info *b) {
    size_t off = 0;
    uint32_t n = 0;
    while (off + PREELE_SECT_HDR <= clen && n < ELE3_MAX_SECTIONS) {
        uint32_t size = be32(c + off), sum = be32(c + off + 4), calc = 0;
        int ok = (size >= PREELE_MIN_SECT && off + PREELE_SECT_HDR + size <= clen);
        if (ok) {
            for (uint32_t k = 0; k < size; k++)
                calc += c[off + PREELE_SECT_HDR + k];
            ok = (calc == sum);
        }
        if (ok) {
            b->sections[n].id       = n;
            b->sections[n].offset   = (uint32_t)off;
            b->sections[n].comp_len = PREELE_SECT_HDR + size;
            b->sections[n].dest     = 0;
            n++;
            off += PREELE_SECT_HDR + size;
        } else {
            off++; /* inter-section metadata or padding */
        }
    }
    b->nsections     = n;
    b->declared_size = clen;
    b->trailer_bytes = 0;
    b->have_key      = 0;
}

int container_parse(const uint8_t *data, size_t len, container_type ct, size_t preamble_size,
                    bin_info *b) {
    b->data = data;
    b->len  = len;
    b->type = ct;

    if (ct == CT_PREELE) {
        parse_preele(data, len, b);
        return 0;
    }
    if (len < container_min_len(ct))
        return -2;

    if (ct == CT_ELEK) { /* header + single [size][sum] section */
        uint32_t seclen         = be32(data + ELEK_SECT_OFF);
        b->declared_size        = len;
        b->nsections            = 1;
        b->sections[0].id       = 3; /* present it as the MAIN OS section */
        b->sections[0].offset   = ELEK_SECT_OFF;
        b->sections[0].comp_len = clamp_len((size_t)seclen + APLIB_SECT_HDR, ELEK_SECT_OFF, len);
        b->sections[0].dest     = 0;
        b->trailer_bytes        = 0;
        b->have_key             = 0;
        return 0;
    }

    b->declared_size = preamble_size;

    if (ct == CT_ELE2) { /* single OS section, no table, no digest */
        uint32_t seclen         = be32(data + ELE2_SECT_OFF);
        b->nsections            = 1;
        b->sections[0].id       = 3;
        b->sections[0].offset   = ELE2_SECT_OFF;
        b->sections[0].comp_len = clamp_len((size_t)seclen + APLIB_SECT_HDR, ELE2_SECT_OFF, len);
        b->sections[0].dest     = be32(data + ELE2_DEST_OFF);
        b->trailer_bytes        = 0;
        return 0;
    }
    if (ct == CT_AD) { /* 16-byte header + raw image */
        b->nsections            = 1;
        b->sections[0].id       = 3;
        b->sections[0].offset   = AD_IMG_OFF;
        b->sections[0].comp_len = clamp_len(be32(data + AD_LEN_OFF), AD_IMG_OFF, len);
        b->sections[0].dest     = 0;
        b->trailer_bytes        = 0;
        return 0;
    }
    if (ct != CT_ELE3)
        return -2;

    /* Ignore table entries that lie past the end of a truncated container. */
    uint32_t declared = be32(data + ELE3_COUNT_OFF);
    uint32_t fits_n   = (uint32_t)((len - ELE3_TABLE_OFF) / ELE3_ENTRY_SZ);
    if (declared > ELE3_MAX_SECTIONS)
        return -1;
    b->nsections = (declared < fits_n) ? declared : fits_n;

    size_t sections_end = 0;
    for (uint32_t s = 0; s < b->nsections; s++) {
        b->sections[s] = table_entry(data, s);
        size_t e       = (size_t)b->sections[s].offset + b->sections[s].comp_len;
        if (e > sections_end)
            sections_end = e;
    }
    size_t aligned   = align_up(sections_end, CONTAINER_ALIGN);
    b->trailer_bytes = (b->declared_size > aligned) ? b->declared_size - aligned : 0;
    return 0;
}

/* -------------------------------- sections --------------------------------- */

size_t container_section_stored_len(const bin_info *b, const ele3_section *sec) {
    size_t avail = (sec->offset < b->len) ? b->len - sec->offset : 0;
    return (sec->comp_len && sec->comp_len <= avail) ? sec->comp_len : avail;
}

size_t container_section_depack(const bin_info *b, const ele3_section *sec, uint8_t *scratch,
                                size_t scap) {
    size_t cl = container_section_stored_len(b, sec);
    if (!cl)
        return (size_t)-1;
    return ap_depack(b->data + sec->offset, cl, scratch, scap, 1);
}

int container_section_stream_sum(const bin_info *b, const ele3_section *sec, uint32_t *stored,
                                 uint32_t *calc) {
    if (!fits(b->len, sec->offset, APLIB_SECT_HDR))
        return 0;
    const uint8_t *p = b->data + sec->offset;
    uint32_t slen = be32(p), acc = 0;
    *stored = be32(p + 4);
    for (uint32_t k = 0; k < slen && (size_t)sec->offset + APLIB_SECT_HDR + k < b->len; k++)
        acc += p[APLIB_SECT_HDR + k];
    *calc = acc;
    return 1;
}

const ele3_section *container_find_section(const bin_info *b, uint32_t id) {
    for (uint32_t s = 0; s < b->nsections; s++)
        if (b->sections[s].id == id)
            return &b->sections[s];
    return NULL;
}

void container_find_key(bin_info *b, uint8_t *scratch, size_t scap) {
    b->have_key  = 0;
    size_t csize = b->declared_size;
    if (csize < 4 + DIGEST_LEN || csize > b->len)
        return;
    const uint8_t *msg = b->data, *expect = b->data + csize - DIGEST_LEN;
    size_t msglen = csize - DIGEST_LEN;
    for (uint32_t s = 0; s < b->nsections; s++) {
        size_t dn = container_section_depack(b, &b->sections[s], scratch, scap);
        if (dn == (size_t)-1 || dn == 0)
            continue;
        if (elektron_extract_key(scratch, dn, msg, msglen, expect, b->key, b->key_str,
                                 sizeof b->key_str)) {
            b->have_key = 1;
            return;
        }
    }
}

/* --------------------------------- version --------------------------------- */

static int is_alnum(int ch) { /* locale-independent on purpose */
    return (ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z');
}

int container_header_end(container_type ct) {
    /* One past the last byte of the text header. Past this lies the section
     * table (ELE3), the destination address (ELE2) or the section stream
     * itself (ELEK), none of which is version text. */
    return ct == CT_ELE2 ? ELE2_DEST_OFF : ct == CT_ELEK ? ELEK_SECT_OFF : ELE3_COUNT_OFF;
}

int container_find_version_pattern(const uint8_t *c, int from, int lim) {
    for (int i = from; i + 2 < lim; i++)
        if (c[i] >= '0' && c[i] <= '9' && c[i + 1] == '.' && c[i + 2] >= '0' && c[i + 2] <= '9')
            return i;
    return -1;
}

int container_version_field(const uint8_t *c, size_t clen, container_type ct, int *voff,
                            int *vend) {
    int lim = container_header_end(ct);
    if (clen < (size_t)lim)
        lim = (int)clen;
    int off = -1, end;

    if (ct == CT_ELE3 || ct == CT_ELE2) {
        off =
            container_find_version_pattern(c, ct == CT_ELE2 ? ELE2_BUILD_OFF : ELE3_BUILD_OFF, lim);
        if (off < 0)
            return -1;
        for (end = off; end < lim && (is_alnum(c[end]) || c[end] == '.' || c[end] == ' '); end++)
            ;
    } else if (ct == CT_ELEK) {
        /* A fixed-width field, so it is taken whole rather than scanned: the
         * leading pad is part of the field, and scanning forward from the first
         * digit would leave it out of the writable width. */
        off = ELEK_VERSION_OFF;
        end = lim;
        if (end <= off)
            return -1;
    } else {
        return -2; /* pre-ELE keeps its version in section-gap metadata */
    }
    *voff = off;
    *vend = end;
    return 0;
}

int container_set_version(uint8_t *c, size_t clen, container_type ct, const char *ver) {
    int voff, vend, rc = container_version_field(c, clen, ct, &voff, &vend);
    if (rc != 0)
        return rc;
    int cap = vend - voff, nl = (int)strlen(ver);
    if (nl > cap)
        return -3;
    /* ELE3/ELE2 locate the field by pattern, so voff is where the version text
     * already begins and writing from there keeps the file's own justification.
     * ELEK's voff is the start of the fixed field instead, so its pad has to be
     * put back explicitly -- every observed ELEK header is right-justified. */
    int pad = (ct == CT_ELEK) ? cap - nl : 0;
    for (int i = 0; i < cap; i++)
        c[voff + i] = (i >= pad && i - pad < nl) ? (uint8_t)ver[i - pad] : ' ';
    return 0;
}

/* -------------------------------- assembly --------------------------------- */

static const override *find_ov(const override *ovs, int n, uint32_t id) {
    for (int i = 0; i < n; i++)
        if (ovs[i].id == id)
            return &ovs[i];
    return NULL;
}

/* Bytes to store for one section: a recompressed override, a raw override, or
 * the original stream verbatim. Sets *packed when it allocated (caller frees).
 * Returns -1 if recompression failed. */
static int section_bytes(const uint8_t *orig, size_t orig_len, const override *ov, int compressed,
                         const uint8_t **out, size_t *out_len, uint8_t **packed, int level) {
    *packed = NULL;
    if (ov && compressed) {
        size_t pcap = ov->len + ov->len / 2 + 256;
        uint8_t *p  = xalloc(pcap);
        size_t n    = ap_pack(ov->data, ov->len, p, pcap, level);
        if (n == (size_t)-1) {
            free(p);
            return -1;
        }
        *packed  = p;
        *out     = p;
        *out_len = n;
        return 0;
    }
    if (ov) {
        *out     = ov->data;
        *out_len = ov->len;
        return 0;
    }
    *out     = orig;
    *out_len = orig_len;
    return 0;
}

size_t container_append_trailer(uint8_t *c, size_t cap, size_t end, const uint8_t key[32]) {
    size_t hmac_off = align_up(end + 4, CONTAINER_ALIGN);
    if (!fits(cap, hmac_off, DIGEST_LEN))
        return (size_t)-1;
    memset(c + end, 0, hmac_off - end);
    uint8_t dig[DIGEST_LEN];
    syx_content_digest(key, c, hmac_off, dig);
    memcpy(c + hmac_off, dig, DIGEST_LEN);
    return hmac_off + DIGEST_LEN;
}

/* ELE3: sections in offset order, each 16-byte aligned, table rewritten. */
static size_t build_ele3(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs, int novs,
                         uint8_t *scratch, size_t scap, int level) {
    const uint8_t *c = b->data;
    uint32_t cnt     = b->nsections;
    uint32_t order[ELE3_MAX_SECTIONS];
    size_t first_off = b->len;
    for (uint32_t s = 0; s < cnt; s++) {
        order[s] = s;
        if (b->sections[s].offset < first_off)
            first_off = b->sections[s].offset;
    }
    for (uint32_t a = 0; a < cnt; a++)
        for (uint32_t bb = a + 1; bb < cnt; bb++)
            if (b->sections[order[bb]].offset < b->sections[order[a]].offset) {
                uint32_t t = order[a];
                order[a]   = order[bb];
                order[bb]  = t;
            }

    if (!fits(cap, 0, first_off))
        return (size_t)-1;
    memcpy(nc, c, first_off);
    size_t pos = first_off;
    for (uint32_t k = 0; k < cnt; k++) {
        uint32_t s         = order[k];
        ele3_section sec   = b->sections[s];
        const override *ov = find_ov(ovs, novs, sec.id);
        pos                = align_up(pos, CONTAINER_ALIGN);

        size_t stored  = container_section_stored_len(b, &sec);
        size_t dn      = container_section_depack(b, &sec, scratch, scap);
        int compressed = (dn != (size_t)-1 && dn > 0);

        const uint8_t *sdata;
        size_t slen;
        uint8_t *packed = NULL;
        if (section_bytes(c + (stored ? sec.offset : b->len), stored, ov, compressed, &sdata, &slen,
                          &packed, level) < 0)
            return (size_t)-1;
        if (!fits(cap, pos, slen) ||
            !fits(cap, ELE3_TABLE_OFF + (size_t)s * ELE3_ENTRY_SZ, ELE3_ENTRY_SZ)) {
            free(packed);
            return (size_t)-1;
        }
        memcpy(nc + pos, sdata, slen);
        uint8_t *e = nc + ELE3_TABLE_OFF + s * ELE3_ENTRY_SZ;
        wr32be(e + 4, (uint32_t)pos);
        wr32be(e + 8, (uint32_t)slen);
        free(packed);
        pos += slen;
    }
    return pos;
}

/* ELE2: single section at 0x18, no table, container padded to even. */
static size_t build_ele2(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs, int novs,
                         int level) {
    if (!fits(cap, 0, ELE2_SECT_OFF))
        return (size_t)-1;
    memcpy(nc, b->data, ELE2_SECT_OFF);
    const uint8_t *sdata;
    size_t slen;
    uint8_t *packed = NULL;
    /* ELE2 sections are always compressed, so an override is always repacked. */
    if (section_bytes(b->data + ELE2_SECT_OFF, b->sections[0].comp_len, find_ov(ovs, novs, 3), 1,
                      &sdata, &slen, &packed, level) < 0)
        return (size_t)-1;
    if (!fits(cap, ELE2_SECT_OFF, slen + 1)) {
        free(packed);
        return (size_t)-1;
    }
    memcpy(nc + ELE2_SECT_OFF, sdata, slen);
    free(packed);
    size_t pos = ELE2_SECT_OFF + slen;
    return pos + (pos & 1);
}

/* AD: 16-byte header + raw image; image length and CRC-32 recomputed. */
static size_t build_ad(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs, int novs) {
    const override *ov = find_ov(ovs, novs, 3);
    const uint8_t *img = ov ? ov->data : b->data + AD_IMG_OFF;
    size_t imglen      = ov ? ov->len : b->sections[0].comp_len;
    if (!fits(cap, AD_IMG_OFF, imglen))
        return (size_t)-1;
    memcpy(nc, b->data, AD_IMG_OFF);
    memcpy(nc + AD_IMG_OFF, img, imglen);
    wr32be(nc + AD_LEN_OFF, (uint32_t)imglen);
    wr32be(nc + AD_CRC_OFF, crc32_calc(nc + AD_IMG_OFF, imglen));
    return AD_IMG_OFF + imglen;
}

/* ELEK: header + single section at 0x12, trailing padding preserved. */
static size_t build_elek(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs, int novs,
                         int level) {
    if (!fits(cap, 0, ELEK_SECT_OFF))
        return (size_t)-1;
    memcpy(nc, b->data, ELEK_SECT_OFF);
    size_t sec_end = ELEK_SECT_OFF + b->sections[0].comp_len;
    const uint8_t *sdata;
    size_t slen;
    uint8_t *packed = NULL;
    if (section_bytes(b->data + ELEK_SECT_OFF, b->sections[0].comp_len, find_ov(ovs, novs, 3), 1,
                      &sdata, &slen, &packed, level) < 0)
        return (size_t)-1;
    size_t tail = (b->len > sec_end) ? b->len - sec_end : 0;
    if (!fits(cap, ELEK_SECT_OFF, slen + tail)) {
        free(packed);
        return (size_t)-1;
    }
    memcpy(nc + ELEK_SECT_OFF, sdata, slen);
    size_t pos = ELEK_SECT_OFF + slen;
    if (tail) {
        memcpy(nc + pos, b->data + sec_end, tail);
        pos += tail;
    }
    free(packed);
    return pos;
}

/* pre-ELE: walk sections in offset order, preserving the metadata between them.
 * ap_pack already emits the [size][sum] header a section needs. */
static size_t build_preele(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs,
                           int novs, int level) {
    const uint8_t *c = b->data;
    size_t pos = 0, prev_end = 0;
    for (uint32_t s = 0; s < b->nsections; s++) {
        ele3_section sec = b->sections[s];
        if (sec.offset > prev_end) {
            size_t gap = sec.offset - prev_end;
            if (!fits(cap, pos, gap))
                return (size_t)-1;
            memcpy(nc + pos, c + prev_end, gap);
            pos += gap;
        }
        const uint8_t *sdata;
        size_t slen;
        uint8_t *packed = NULL;
        if (section_bytes(c + sec.offset, sec.comp_len, find_ov(ovs, novs, sec.id), 1, &sdata,
                          &slen, &packed, level) < 0)
            return (size_t)-1;
        if (!fits(cap, pos, slen)) {
            free(packed);
            return (size_t)-1;
        }
        memcpy(nc + pos, sdata, slen);
        pos += slen;
        free(packed);
        prev_end = (size_t)sec.offset + sec.comp_len;
    }
    if (b->len > prev_end) {
        size_t tail = b->len - prev_end;
        if (!fits(cap, pos, tail))
            return (size_t)-1;
        memcpy(nc + pos, c + prev_end, tail);
        pos += tail;
    }
    return pos;
}

size_t container_build(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs, int novs,
                       uint8_t *scratch, size_t scap, int level) {
    switch (b->type) {
        case CT_ELE2: return build_ele2(b, nc, cap, ovs, novs, level);
        case CT_AD: return build_ad(b, nc, cap, ovs, novs);
        case CT_ELEK: return build_elek(b, nc, cap, ovs, novs, level);
        case CT_PREELE: return build_preele(b, nc, cap, ovs, novs, level);
        default: return build_ele3(b, nc, cap, ovs, novs, scratch, scap, level);
    }
}
