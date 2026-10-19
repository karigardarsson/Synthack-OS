/* SysEx transport: decode a .syx into its container stream, and re-encode. */
#include "transport.h"
#include "device.h"
#include "integrity.h"
#include "util.h"

/* The packet body size is not declared anywhere, so it is inferred as the most
 * common data-packet length in the file. These bound that search. */
enum { BODY_MIN = 16, BODY_MAX = 512 };

int syx_next(syx_iter *it, const uint8_t **body, size_t *body_len) {
    while (it->pos < it->len) {
        if (it->buf[it->pos] != SYX_START) {
            it->pos++;
            continue;
        }
        size_t j = it->pos + 1;
        while (j < it->len && it->buf[j] != SYX_END)
            j++;
        if (j >= it->len) /* unterminated: no further complete messages */
            break;
        *body     = it->buf + it->pos + 1;
        *body_len = j - (it->pos + 1);
        it->pos   = j + 1;
        return 1;
    }
    it->pos = it->len;
    return 0;
}

/* ------------------------------- checksums --------------------------------- */

/* 7-bit sum over body[6..124], each byte XORed with (base+index), then +base.
 * 'base' is the start marker's info[0]. */
uint8_t syx_block_checksum(const uint8_t *body, uint8_t base) {
    unsigned acc = 0;
    for (unsigned i = 0; i < SYX_CKSUM_SPAN; i++)
        acc += (unsigned)body[PK_BLOCK + i] ^ (base + i);
    return (uint8_t)((base + acc) & SYX_MASK7);
}

uint8_t legacy_packet_checksum(uint8_t dev, const uint8_t nib[6], unsigned payload_sum) {
    unsigned s = payload_sum;
    if (dev == DEV_OCTATRACK)
        s += (unsigned)((nib[1] & 7) + nib[3] + nib[5] + ((nib[2] + nib[4]) << 4));
    else
        s += (unsigned)(nib[1] + (nib[2] << 4) + nib[3] + ((nib[4] & 0x0C) << 4));
    return (uint8_t)(s & 0xff);
}

void syx_build_preamble(uint8_t preamble[SYX_PREAMBLE], const uint8_t *container, size_t clen) {
    wr32be(preamble, (uint32_t)clen);
    wr32be(preamble + 4, syx_content_checksum(container, clen));
}

int syx_find_marker_info(const uint8_t *buf, size_t fsz, uint8_t *base,
                         uint8_t info[SYX_MARKER_INFO]) {
    syx_iter it;
    const uint8_t *m;
    size_t mlen;
    syx_iter_init(&it, buf, fsz);
    while (syx_next(&it, &m, &mlen)) {
        if (mlen >= PK_MARKER_BASE + SYX_MARKER_INFO && m[PK_CMD] == SYX_CMD_MARKER) {
            *base = m[PK_MARKER_BASE];
            memcpy(info, m + PK_MARKER_BASE, SYX_MARKER_INFO);
            return 1;
        }
    }
    return 0;
}

/* --------------------------------- decode ---------------------------------- */

/* 2+7+7 word packing: every 3 payload bytes -> one 16-bit word -> 2 bytes. */
static void decode_preele(uint8_t *dec, size_t *dpos, const uint8_t *p, size_t plen) {
    for (size_t k = 0; k + 3 <= plen; k += 3) {
        unsigned w = ((unsigned)(p[k] & 3) << 14) | ((unsigned)(p[k + 1] & SYX_MASK7) << 7) |
                     (unsigned)(p[k + 2] & SYX_MASK7);
        dec[(*dpos)++] = (uint8_t)(w >> 8);
        dec[(*dpos)++] = (uint8_t)w;
    }
}

/* 8-in-7, MSB-first: each group is one MSB byte plus up to 7 data bytes. */
static void decode_payload(uint8_t *dec, size_t *dpos, const uint8_t *p, size_t plen) {
    for (size_t k = 0; k < plen; k += SYX_7IN8_GROUP + 1) {
        uint8_t ms = p[k];
        size_t nd  = (plen - k - 1) < SYX_7IN8_GROUP ? (plen - k - 1) : SYX_7IN8_GROUP;
        for (size_t n = 0; n < nd; n++)
            dec[(*dpos)++] = (uint8_t)(p[k + 1 + n] |
                                       (((ms >> (SYX_7IN8_GROUP - 1 - n)) & 1) ? SYX_HIGH_BIT : 0));
    }
}

uint8_t *syx_transport_decode(const uint8_t *buf, size_t fsz, size_t *dec_len, uint8_t *dev_out,
                              transport_stats *ts) {
    syx_iter it;
    const uint8_t *m;
    size_t mlen;

    /* First pass: the device id and the dominant data-packet body size. */
    size_t pkt  = 0;
    uint8_t dev = 0;
    {
        size_t cnt[BODY_MAX];
        memset(cnt, 0, sizeof cnt);
        syx_iter_init(&it, buf, fsz);
        while (syx_next(&it, &m, &mlen)) {
            if (mlen > PK_DEV && !dev)
                dev = m[PK_DEV];
            if (mlen > PK_CMD && mlen < BODY_MAX && m[PK_CMD] == SYX_CMD_DATA)
                cnt[mlen]++;
        }
        size_t best = 0;
        for (size_t L = BODY_MIN; L < BODY_MAX; L++)
            if (cnt[L] > best) {
                best = cnt[L];
                pkt  = L;
            }
    }
    if (!pkt)
        return NULL;

    int preele = (dev == DEV_MACHINEDRUM || dev == DEV_MONOMACHINE);
    size_t hdr = (pkt == SYX_PKT) ? SYX_HDR : LEGACY_THDR;
    size_t pay = (pkt == SYX_PKT) ? SYX_ENC_PAY : (pkt - hdr);

    /* 8-in-7 and 2+7+7 both decode to fewer bytes than they occupy on the wire,
     * so the file size bounds the decoded stream. */
    uint8_t *dec = malloc(fsz);
    if (!dec)
        return NULL;
    size_t dpos = 0;

    size_t nmsg = 0, ndata = 0, nmarker = 0;
    size_t pk_ok = 0, pk_bad = 0;
    uint8_t ckbase  = 0;
    int have_ckbase = 0;
    int nblocks = 0, min_pk = 1 << 30, max_pk = 0, cur_pk = 0;
    long cur_block = -1, first_block = -1, seq0 = -1, seqN = -1;
    uint8_t mk[2][16];
    int mkl[2] = {0, 0}, nmk = 0;
    uint8_t ts_last_pay[SYX_PKT];
    size_t ts_last_pay_len = 0;

    syx_iter_init(&it, buf, fsz);
    while (syx_next(&it, &m, &mlen)) {
        nmsg++;
        /* Legacy transports end with a SHORT data packet, so match on the
         * command byte rather than the size. */
        int legacy  = (pkt != (size_t)SYX_PKT);
        int is_data = legacy ? (mlen > hdr && m[PK_CMD] == SYX_CMD_DATA)
                             : (mlen == pkt && m[PK_CMD] == SYX_CMD_DATA);
        if (is_data) {
            ndata++;
            size_t before = dpos;
            if (preele) {
                decode_preele(dec, &dpos, m + hdr, mlen - hdr);
            } else if (pkt == SYX_PKT) {
                const syx_data_packet *p = (const syx_data_packet *)m;
                long block               = ((long)p->block[0] << 7) | p->block[1];
                if (block != cur_block) {
                    if (cur_block >= 0) {
                        if (cur_pk < min_pk)
                            min_pk = cur_pk;
                        if (cur_pk > max_pk)
                            max_pk = cur_pk;
                    }
                    if (first_block < 0) {
                        first_block = block;
                        seq0        = p->seq;
                    }
                    cur_block = block;
                    cur_pk    = 0;
                    nblocks++;
                }
                if (block == first_block)
                    seqN = p->seq;
                cur_pk++;
                decode_payload(dec, &dpos, p->payload, SYX_ENC_PAY);
            } else {
                decode_payload(dec, &dpos, m + hdr, mlen - hdr); /* ELEK 8-in-7 */
            }
            if (mlen > hdr && mlen - hdr <= sizeof ts_last_pay) {
                ts_last_pay_len = mlen - hdr;
                memcpy(ts_last_pay, m + hdr, ts_last_pay_len);
            }
            /* Verify the per-packet transport checksum. */
            if (pkt == SYX_PKT) {
                if (have_ckbase) {
                    if (syx_block_checksum(m, ckbase) == m[SYX_CKSUM_OFF])
                        pk_ok++;
                    else
                        pk_bad++;
                }
            } else { /* legacy: body[6],body[7] are the checksum nibbles */
                unsigned s = 0;
                for (size_t q = before; q < dpos; q++)
                    s += dec[q];
                uint8_t C = legacy_packet_checksum(dev, m + LEGACY_NIB, s);
                if (((C >> 4) & 0xf) == m[LEGACY_CK_HI] && (C & 0xf) == m[LEGACY_CK_LO])
                    pk_ok++;
                else
                    pk_bad++;
            }
        } else {
            nmarker++;
            if (mlen > PK_MARKER_BASE) { /* the byte-125 checksum seed */
                ckbase      = m[PK_MARKER_BASE];
                have_ckbase = 1;
            }
            if (nmk < 2) {
                mkl[nmk] = (int)(mlen < 16 ? mlen : 16);
                memcpy(mk[nmk], m, (size_t)mkl[nmk]);
                nmk++;
            }
        }
    }
    if (cur_block >= 0) {
        if (cur_pk < min_pk)
            min_pk = cur_pk;
        if (cur_pk > max_pk)
            max_pk = cur_pk;
    }

    if (ts) {
        ts->file_size     = fsz;
        ts->nmsg          = nmsg;
        ts->ndata         = ndata;
        ts->nmarker       = nmarker;
        ts->decoded       = dpos;
        ts->pkt_body      = pkt;
        ts->hdr           = hdr;
        ts->pay           = pay;
        ts->pkt_ck_ok     = pk_ok;
        ts->pkt_ck_bad    = pk_bad;
        ts->nblocks       = nblocks;
        ts->min_pk        = (min_pk == (1 << 30)) ? 0 : min_pk;
        ts->max_pk        = max_pk;
        ts->first_block   = first_block;
        ts->seq0          = seq0;
        ts->seqN          = seqN;
        ts->nmarker_saved = nmk;
        ts->last_pay_len  = ts_last_pay_len;
        memcpy(ts->last_pay, ts_last_pay, ts_last_pay_len);
        for (int k = 0; k < nmk; k++) {
            ts->marker_len[k] = mkl[k];
            memcpy(ts->marker[k], mk[k], (size_t)mkl[k]);
        }
    }

    *dec_len = dpos;
    if (dev_out)
        *dev_out = dev;
    return dec;
}

/* --------------------------------- encode ---------------------------------- */

/* Emit one F0 <body> F7 message; returns bytes written. */
static size_t emit_msg(uint8_t *out, const void *body, size_t bodylen) {
    size_t o = 0;
    out[o++] = SYX_START;
    memcpy(out + o, body, bodylen);
    o += bodylen;
    out[o++] = SYX_END;
    return o;
}

static size_t encode_8in7(const uint8_t *in, size_t inlen, uint8_t *out) {
    size_t o = 0, i = 0;
    while (i < inlen) {
        size_t nd  = (inlen - i < SYX_7IN8_GROUP) ? (inlen - i) : SYX_7IN8_GROUP;
        uint8_t ms = 0; /* MSBs of this group */
        for (size_t n = 0; n < nd; n++)
            if (in[i + n] & SYX_HIGH_BIT)
                ms |= (uint8_t)(1 << (SYX_7IN8_GROUP - 1 - n));
        out[o++] = ms;
        for (size_t n = 0; n < nd; n++)
            out[o++] = in[i + n] & SYX_MASK7;
        i += SYX_7IN8_GROUP;
    }
    return o;
}

/* Marker info: [0]=base seed, [1..3]=start block/seq, [4..6]=packet count. */
static void fill_marker(syx_marker *m, uint8_t dev, uint8_t kind, uint8_t base, size_t npkt,
                        const uint8_t tmpl[SYX_MARKER_INFO]) {
    static const uint8_t dflt[SYX_MARKER_INFO] = {0x10, 0x00, 0x01, 0x72, 0x01, 0x06, 0x6b};
    static const uint8_t mfr[3]                = SYX_MFR_INIT;
    memcpy(m->mfr, mfr, 3);
    m->device   = dev;
    m->reserved = 0x00;
    m->command  = SYX_CMD_MARKER;
    m->kind     = kind;
    memcpy(m->info, tmpl ? tmpl : dflt, SYX_MARKER_INFO);
    m->info[0] = base;
    m->info[4] = (uint8_t)((npkt >> 14) & SYX_MASK7);
    m->info[5] = (uint8_t)((npkt >> 7) & SYX_MASK7);
    m->info[6] = (uint8_t)(npkt & SYX_MASK7);
}

static void print_packet(const char *tag, size_t k, const syx_data_packet *p) {
    uint32_t block = ((uint32_t)p->block[0] << 7) | p->block[1];
    printf("    %-8s pkt[%zu]  block=%-3u seq=%-3u  checksum=0x%02x\n", tag, k, block, p->seq,
           p->checksum);
}

/* ------------------- legacy transport (pre-ELE / ELEK) --------------------- */

/* 2+7+7: every 2 decoded bytes -> 3 payload bytes (2 high bits + 7 + 7). */
static size_t encode_preele_payload(const uint8_t *in, size_t n, uint8_t *out) {
    size_t o = 0, k = 0;
    for (; k + 2 <= n; k += 2) {
        unsigned w = ((unsigned)in[k] << 8) | in[k + 1];
        out[o++]   = (uint8_t)((w >> 14) & 3);
        out[o++]   = (uint8_t)((w >> 7) & SYX_MASK7);
        out[o++]   = (uint8_t)(w & SYX_MASK7);
    }
    if (k < n) {
        unsigned w = ((unsigned)in[k] << 8);
        out[o++]   = (uint8_t)((w >> 14) & 3);
        out[o++]   = (uint8_t)((w >> 7) & SYX_MASK7);
        out[o++]   = (uint8_t)(w & SYX_MASK7);
    }
    return o;
}

/* 24-bit value as 6 nibbles, one per byte, big-endian order. */
static void preele_nib6(uint32_t v, uint8_t nb[6]) {
    nb[0] = (uint8_t)((v >> 20) & 0xf);
    nb[1] = (uint8_t)((v >> 16) & 0xf);
    nb[2] = (uint8_t)((v >> 12) & 0xf);
    nb[3] = (uint8_t)((v >> 8) & 0xf);
    nb[4] = (uint8_t)((v >> 4) & 0xf);
    nb[5] = (uint8_t)(v & 0xf);
}

typedef size_t (*legacy_codec)(const uint8_t *in, size_t n, uint8_t *out);

/* Decode a payload with the matching scheme, to prove a substitution is safe. */
typedef void (*legacy_decoder)(uint8_t *, size_t *, const uint8_t *, size_t);

static int tail_matches(const uint8_t *tail, size_t tail_len, const uint8_t *chunk, size_t n,
                        legacy_decoder unpack) {
    if (!tail || !tail_len)
        return 0;
    uint8_t back[SYX_PKT * 2];
    size_t bn = 0;
    unpack(back, &bn, tail, tail_len);
    return bn >= n && !memcmp(back, chunk, n);
}

static size_t emit_legacy_data(uint8_t *out, uint8_t dev, const uint8_t nb[6], const uint8_t *chunk,
                               size_t n, legacy_codec pack, const uint8_t *sub, size_t sub_len) {
    static const uint8_t MFR[3] = SYX_MFR_INIT;
    unsigned s                  = 0;
    for (size_t k = 0; k < n; k++)
        s += chunk[k];
    uint8_t C = legacy_packet_checksum(dev, nb, s);
    size_t o  = 0;
    out[o++]  = SYX_START;
    memcpy(out + o, MFR, 3);
    o += 3;
    out[o++] = dev;
    out[o++] = 0x00;
    out[o++] = SYX_CMD_DATA;
    out[o++] = (uint8_t)((C >> 4) & 0xf);
    out[o++] = (uint8_t)(C & 0xf);
    memcpy(out + o, nb, 6);
    o += 6;
    if (sub) {
        memcpy(out + o, sub, sub_len);
        o += sub_len;
    } else {
        o += pack(chunk, n, out + o);
    }
    out[o++] = SYX_END;
    return o;
}

/* N data packets, an empty data packet, then an end marker carrying the total
 * decoded length. */
static uint8_t *legacy_encode(const uint8_t *container, size_t clen, uint8_t dev, size_t dec_pkt,
                              legacy_decoder unpack, const uint8_t *tail, size_t tail_len,
                              legacy_codec pack, size_t *out_len, int verbose) {
    static const uint8_t MFR[3] = SYX_MFR_INIT;
    size_t npkt                 = (clen + dec_pkt - 1) / dec_pkt;
    size_t cap                  = (npkt + 2) * (dec_pkt * 2 + LEGACY_THDR + 4) + 64;
    uint8_t *out                = malloc(cap);
    if (!out)
        return NULL;
    size_t o = 0, off = 0;
    if (verbose) {
        printf("=== sysex encode (device 0x%02x, %s) ===\n", dev, elektron_device_name(dev));
        printf("  decoded container     : %zu B  (%zu data packets, %zu B each)\n", clen, npkt,
               dec_pkt);
    }
    while (off < clen) {
        size_t n = (clen - off < dec_pkt) ? (clen - off) : dec_pkt;
        uint8_t nb[6];
        preele_nib6((uint32_t)(PREELE_COUNTER + off), nb);
        /* Only the final packet can carry bytes no decoded byte depends on. */
        int last = (off + dec_pkt >= clen);
        const uint8_t *sub =
            (last && tail_matches(tail, tail_len, container + off, n, unpack)) ? tail : NULL;
        o += emit_legacy_data(out + o, dev, nb, container + off, n, pack, sub, tail_len);
        off += dec_pkt;
    }
    out[o++] = SYX_START; /* empty data packet */
    memcpy(out + o, MFR, 3);
    o += 3;
    out[o++] = dev;
    out[o++] = 0x00;
    out[o++] = SYX_CMD_DATA;
    out[o++] = SYX_END;
    uint8_t tn[6]; /* end marker: total decoded length */
    preele_nib6((uint32_t)clen, tn);
    out[o++] = SYX_START;
    memcpy(out + o, MFR, 3);
    o += 3;
    out[o++] = dev;
    out[o++] = 0x00;
    out[o++] = SYX_CMD_MARKER;
    memcpy(out + o, tn, 6);
    o += 6;
    out[o++] = SYX_END;
    if (verbose)
        printf("  total messages        : %zu (%zu data + empty + end marker), %zu bytes\n",
               npkt + 2, npkt, o);
    *out_len = o;
    return out;
}

uint8_t *preele_encode(const uint8_t *container, size_t clen, uint8_t dev, const uint8_t *tail,
                       size_t tail_len, size_t *out_len, int verbose) {
    return legacy_encode(container, clen, dev, PREELE_DEC_PKT, decode_preele, tail, tail_len,
                         encode_preele_payload, out_len, verbose);
}

uint8_t *elek_encode(const uint8_t *container, size_t clen, uint8_t dev, const uint8_t *tail,
                     size_t tail_len, size_t *out_len, int verbose) {
    return legacy_encode(container, clen, dev, ELEK_DEC_PKT, decode_payload, tail, tail_len,
                         encode_8in7, out_len, verbose);
}

uint8_t *syx_encode(const uint8_t *container, size_t clen, uint8_t dev,
                    const uint8_t preamble[SYX_PREAMBLE], uint8_t base,
                    const uint8_t marker_info[SYX_MARKER_INFO], size_t *out_len, int verbose) {
    size_t total    = SYX_PREAMBLE + clen;
    size_t npkt     = total / SYX_DEC_PER_PKT + 1; /* always a final, maybe empty, packet */
    size_t padded   = npkt * SYX_DEC_PER_PKT;      /* last packet zero-padded to full     */
    uint8_t *stream = calloc(1, padded ? padded : 1);
    if (!stream)
        return NULL;
    memcpy(stream, preamble, SYX_PREAMBLE);
    memcpy(stream + SYX_PREAMBLE, container, clen);

    size_t cap   = (npkt + 2) * (SYX_PKT + 2) + 256; /* +2 per msg for F0/F7 */
    uint8_t *out = malloc(cap);
    if (!out) {
        free(stream);
        return NULL;
    }
    size_t o = 0;

    uint32_t start_block = marker_info ? (((uint32_t)marker_info[1] << 7) | marker_info[2]) : 1;
    uint32_t start_seq   = marker_info ? marker_info[3] : 0x72;

    if (verbose) {
        printf("=== sysex encode (device 0x%02x, %s) ===\n", dev, elektron_device_name(dev));
        printf("  decoded stream        : %zu B (preamble %d + container %zu), padded to %zu\n",
               total, SYX_PREAMBLE, clen, padded);
        printf("  data packets          : %zu  (%d decoded B each, last zero-padded)\n", npkt,
               SYX_DEC_PER_PKT);
        printf("  packet body           : %d B = %d header + %d 8-in-7 payload + 1 checksum\n",
               SYX_PKT, SYX_HDR, SYX_ENC_PAY);
        printf("  start block/seq       : block=%u seq=%u  (counter wraps every %d packets)\n",
               start_block, start_seq, SYX_BLOCK_PKTS);
        printf("  packet-count field    : info[4..6] = %02x %02x %02x\n",
               (unsigned)((npkt >> 14) & SYX_MASK7), (unsigned)((npkt >> 7) & SYX_MASK7),
               (unsigned)(npkt & SYX_MASK7));
    }

    syx_marker mk;
    fill_marker(&mk, dev, MARKER_START, base, npkt, marker_info);
    if (verbose) {
        const uint8_t *b = (const uint8_t *)&mk;
        printf("  start marker          : ");
        for (size_t i = 0; i < sizeof mk; i++)
            printf("%02x", b[i]);
        printf("\n");
    }
    o += emit_msg(out + o, &mk, sizeof mk);

    /* block/seq is one 7-bit-wrapping counter starting at the marker's info[1..3]. */
    for (size_t k = 0; k < npkt; k++) {
        uint32_t cum      = start_seq + (uint32_t)k;
        uint32_t block    = start_block + (cum >> 7);
        syx_data_packet p = {
            .mfr      = SYX_MFR_INIT,
            .device   = dev,
            .reserved = 0x00,
            .command  = SYX_CMD_DATA,
            .block    = {(uint8_t)((block >> 7) & SYX_MASK7), (uint8_t)(block & SYX_MASK7)},
            .seq      = (uint8_t)(cum & SYX_MASK7),
        };
        encode_8in7(stream + k * SYX_DEC_PER_PKT, SYX_DEC_PER_PKT, p.payload);
        p.checksum = syx_block_checksum((const uint8_t *)&p, base);
        o += emit_msg(out + o, &p, sizeof p);
        if (verbose && (k < 3 || k + 3 >= npkt))
            print_packet("data", k, &p);
        else if (verbose && k == 3)
            printf("    ...      (%zu packets)\n", npkt - 6);
    }
    fill_marker(&mk, dev, MARKER_END, base, npkt, marker_info);
    if (verbose) {
        const uint8_t *b = (const uint8_t *)&mk;
        printf("  end marker            : ");
        for (size_t i = 0; i < sizeof mk; i++)
            printf("%02x", b[i]);
        printf("\n");
    }
    o += emit_msg(out + o, &mk, sizeof mk);

    if (verbose)
        printf("  total messages        : %zu (2 markers + %zu data), %zu bytes on the wire\n",
               npkt + 2, npkt, o);
    free(stream);
    *out_len = o;
    return out;
}
