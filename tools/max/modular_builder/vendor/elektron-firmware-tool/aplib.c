/* aPLib-variant codec. The depacker reads an interlaced Elias-gamma bit stream;
 * the packer chooses its parse with a cost-optimal forward DP. */
#include "aplib.h"
#include "util.h"

/* ------------------------------- depacker ---------------------------------- */

typedef struct {
    const uint8_t *ip, *iend;
    uint32_t tag;
    int err;
} bitstate;

static int gb_read(bitstate *b) {
    if (b->ip >= b->iend) {
        b->err = 1;
        return 0;
    }
    return *b->ip++;
}

static int getbit(bitstate *b) {
    b->tag <<= 1;
    if ((b->tag & 0xFF) == 0) {
        uint32_t by = (uint32_t)gb_read(b);
        b->tag      = (by << 1) | 1;
        return (by >> 7) & 1;
    }
    return (b->tag >> 8) & 1;
}

static uint32_t getgamma(bitstate *b) {
    uint32_t v = 1;
    for (;;) {
        v = (v << 1) + (uint32_t)getbit(b);
        if (getbit(b))
            break;
        if (b->err)
            break;
        /* A corrupt stream can encode an unbounded value; treat overflow as an
         * error rather than returning a truncated one. */
        if (v > 0x02000000u) {
            b->err = 1;
            break;
        }
    }
    return v;
}

size_t ap_depack(const uint8_t *src, size_t srclen, uint8_t *out, size_t outcap, int allow_trunc) {
    if (srclen < APLIB_SECT_HDR)
        return (size_t)-1;
    bitstate b  = {src + APLIB_SECT_HDR, src + srclen, 0, 0};
    uint8_t *op = out, *oend = out + outcap;
    uint32_t last_off = 1;

#define AP_END()             \
    do {                     \
        if (allow_trunc)     \
            goto done;       \
        return (size_t) - 1; \
    } while (0)

    for (;;) {
        if (b.err)
            AP_END();
        if (getbit(&b)) { /* literal */
            if (op >= oend)
                return (size_t)-1;
            if (b.ip >= b.iend)
                AP_END();
            *op++ = *b.ip++;
            continue;
        }
        uint32_t g = getgamma(&b), off;
        if (g == APLIB_REUSE_GAMMA) {
            off = last_off;
        } else {
            off = (g << 8) + (uint32_t)gb_read(&b);
            if (b.err)
                AP_END();
            if (off == APLIB_OFFSET_BIAS) /* end of stream */
                break;
            /* A raw offset below the bias wraps to a value near UINT32_MAX
             * rather than going negative, and that is what makes it safe: the
             * "off > bytes written so far" test below cannot pass for a wrapped
             * value, so a malformed stream is rejected there. Do not "fix" this
             * into a signed subtraction without adding an explicit check. */
            off -= APLIB_OFFSET_BIAS;
            last_off = off;
        }
        uint32_t L;
        int ba = getbit(&b), bb = getbit(&b);
        uint32_t sl = (uint32_t)(2 * ba + bb);
        L           = sl ? sl : getgamma(&b) + 2;
        if (b.err)
            AP_END();
        if (off > APLIB_FAR_THRESHOLD)
            L += 1;
        uint32_t n = L + 1;
        if (off == 0 || (size_t)(op - out) < off)
            return (size_t)-1;
        if ((size_t)(oend - op) < n)
            return (size_t)-1;
        const uint8_t *cp = op - off;
        while (n--)
            *op++ = *cp++;
    }
done:
#undef AP_END
    /* Empty output only counts for a truncation-tolerant caller; otherwise the
     * input was not an aPLib stream at all. */
    return (op == out && !allow_trunc) ? (size_t)-1 : (size_t)(op - out);
}

/* -------------------------------- packer ----------------------------------- */

typedef struct {
    uint8_t *o;
    size_t cap, n;
    long tagpos;
    int tagbits, err;
} packer;

static void put_bit(packer *p, int bit) {
    if (p->tagbits == 0) {
        if (p->n >= p->cap) {
            p->err = 1;
            return;
        }
        p->tagpos    = (long)p->n;
        p->o[p->n++] = 0;
        p->tagbits   = 8;
    }
    if (bit)
        p->o[p->tagpos] |= (uint8_t)(1 << (p->tagbits - 1));
    p->tagbits--;
}

static void put_byte(packer *p, uint8_t v) {
    if (p->n >= p->cap) {
        p->err = 1;
        return;
    }
    p->o[p->n++] = v;
}

static void put_gamma(packer *p, uint32_t v) {
    int nb = 0;
    for (uint32_t t = v; t; t >>= 1)
        nb++;
    for (int i = nb - 2; i >= 0; i--) {
        put_bit(p, (int)((v >> i) & 1));
        put_bit(p, i == 0);
    }
}

static void put_literal(packer *p, uint8_t b) {
    put_bit(p, 1);
    put_byte(p, b);
}

static int gamma_cost(uint32_t v) {
    int nb = 0;
    for (; v; v >>= 1)
        nb++;
    return 2 * (nb - 1);
}

static int match_cost(uint32_t off, uint32_t L, uint32_t last_off) {
    int b       = 1 + (off == last_off ? 2 : gamma_cost((off + APLIB_OFFSET_BIAS) >> 8) + 8);
    uint32_t Lb = L - 1 - (off > APLIB_FAR_THRESHOLD ? 1 : 0);
    b += (Lb <= 3) ? 2 : 2 + gamma_cost(Lb - 2);
    return b;
}

static void put_match(packer *p, uint32_t off, uint32_t matchlen, uint32_t *last_off) {
    put_bit(p, 0);
    if (off == *last_off) {
        put_gamma(p, APLIB_REUSE_GAMMA);
    } else {
        uint32_t raw = off + APLIB_OFFSET_BIAS;
        put_gamma(p, raw >> 8);
        put_byte(p, (uint8_t)(raw & 0xFF));
        *last_off = off;
    }
    uint32_t bonus = (off > APLIB_FAR_THRESHOLD) ? 1 : 0;
    uint32_t Lbase = matchlen - 1 - bonus;
    if (Lbase <= 3) {
        put_bit(p, (int)(Lbase >> 1));
        put_bit(p, (int)(Lbase & 1));
    } else {
        put_bit(p, 0);
        put_bit(p, 0);
        put_gamma(p, Lbase - 2);
    }
}

#define HBITS     17
#define HSIZE     (1 << HBITS)
#define MAX_MATCH 2048
#define COST_INF  0xFFFFFFFFu

/* Effort presets: how many match candidates to examine per position.
 *
 * The index is keyed on two bytes, which is the shortest legal match, so every
 * candidate is a real match and no level can miss one that a deeper search would
 * find -- it only stops looking sooner. A wider index was tried and rejected: it
 * shortens the chains, but on Machinedrum/Monomachine (68000 code, dense in
 * two-byte opcode patterns) it compressed worse than Elektron's own packer. */
static const uint16_t levels[] = {16, 64, 256, 2048};

static inline uint32_t hash2(const uint8_t *d) {
    return (((uint32_t)d[0] << 8) ^ d[1]) & (HSIZE - 1);
}

/* common-prefix length of data[a..] and data[b..], capped. */
static inline uint32_t match_run(const uint8_t *data, size_t a, size_t b, uint32_t cap) {
    uint32_t l = 0;
    while (l < cap && data[a + l] == data[b + l])
        l++;
    return l;
}

size_t ap_pack(const uint8_t *data, size_t len, uint8_t *out, size_t outcap, int level) {
    if (outcap < APLIB_SECT_HDR)
        return (size_t)-1;
    if (level < APLIB_LEVEL_MIN)
        level = APLIB_LEVEL_MIN;
    if (level > APLIB_LEVEL_MAX)
        level = APLIB_LEVEL_MAX;
    const int max_chain = levels[level];

    packer p = {out, outcap, APLIB_SECT_HDR, -1, 0, 0};

    if (len == 0) {
        memset(out, 0, APLIB_SECT_HDR);
        return APLIB_SECT_HDR;
    }

    int32_t *head  = malloc(HSIZE * sizeof(int32_t));
    int32_t *prev  = malloc(len * sizeof(int32_t));
    uint32_t *cost = malloc((len + 1) * sizeof(uint32_t));
    uint32_t *lo   = malloc((len + 1) * sizeof(uint32_t));
    int32_t *from  = malloc((len + 1) * sizeof(int32_t));
    uint32_t *toff = malloc((len + 1) * sizeof(uint32_t));
    uint32_t *tlen = malloc((len + 1) * sizeof(uint32_t)); /* 0 => literal */
    uint32_t *path = NULL;
    if (!head || !prev || !cost || !lo || !from || !toff || !tlen)
        goto oom;

    for (size_t k = 0; k < HSIZE; k++)
        head[k] = -1;
    for (size_t k = 0; k <= len; k++)
        cost[k] = COST_INF;
    cost[0] = 0;
    lo[0]   = 1;
    from[0] = -1;

#define RELAX(pos, nc, nl, frm, to, tl) \
    do {                                \
        if ((nc) < cost[pos]) {         \
            cost[pos] = (nc);           \
            lo[pos]   = (nl);           \
            from[pos] = (frm);          \
            toff[pos] = (to);           \
            tlen[pos] = (tl);           \
        }                               \
    } while (0)

    for (size_t i = 0; i < len; i++) {
        if (cost[i] == COST_INF)
            continue;
        uint32_t bi = cost[i], loi = lo[i];
        uint32_t cap = (uint32_t)(len - i);
        if (cap > MAX_MATCH)
            cap = MAX_MATCH;
        RELAX(i + 1, bi + APLIB_LIT_BITS, loi, (int32_t)i, 0u, 0u);
        if (i + 1 < len) {
            if (i >= loi) { /* last-offset reuse costs no offset field */
                uint32_t rl = match_run(data, i - loi, i, cap);
                uint32_t mn = (loi > APLIB_FAR_THRESHOLD) ? APLIB_MIN_MATCH + 1 : APLIB_MIN_MATCH;
                for (uint32_t cl = mn; cl <= rl; cl++)
                    RELAX(i + cl, bi + (uint32_t)match_cost(loi, cl, loi), loi, (int32_t)i, loi,
                          cl);
            }
            {
                int32_t j   = head[hash2(data + i)];
                int chain   = max_chain;
                uint32_t pm = 1;
                while (j >= 0 && chain--) {
                    uint32_t off = (uint32_t)(i - (size_t)j);
                    if (off > APLIB_MAX_OFFSET) {
                        /* Chains run newest-first, so everything past here is
                         * further away still. */
                        break;
                    }
                    /* A candidate cannot beat the incumbent unless it matches at
                     * pm too, so one byte rejects most of them without a full
                     * scan. This changes search cost only, never which match
                     * wins, so the output is unaffected. */
                    if (pm >= cap)
                        break;
                    if (data[(size_t)j + pm] != data[i + pm]) {
                        j = prev[j];
                        continue;
                    }
                    uint32_t l = match_run(data, (size_t)j, i, cap);
                    if (l > pm) {
                        uint32_t mn =
                            (off > APLIB_FAR_THRESHOLD) ? APLIB_MIN_MATCH + 1 : APLIB_MIN_MATCH;
                        uint32_t start = (pm + 1 > mn) ? pm + 1 : mn;
                        for (uint32_t cl = start; cl <= l; cl++)
                            RELAX(i + cl, bi + (uint32_t)match_cost(off, cl, loi), off, (int32_t)i,
                                  off, cl);
                        pm = l;
                        if (l >= cap)
                            break;
                    }
                    j = prev[j];
                }
            }
        }
        if (i + 1 < len) {
            uint32_t h = hash2(data + i);
            prev[i]    = head[h];
            head[h]    = (int32_t)i;
        }
    }
#undef RELAX

    size_t npos = 0;
    for (int32_t j = (int32_t)len; j > 0; j = from[j])
        npos++;
    path = malloc((npos ? npos : 1) * sizeof(uint32_t));
    if (!path)
        goto oom;
    {
        size_t k = npos;
        for (int32_t j = (int32_t)len; j > 0; j = from[j])
            path[--k] = (uint32_t)j;
    }

    uint32_t last_off = 1;
    for (size_t k = 0; k < npos; k++) {
        uint32_t pos = path[k];
        int32_t src  = from[pos];
        if (tlen[pos] == 0)
            put_literal(&p, data[src]);
        else
            put_match(&p, toff[pos], tlen[pos], &last_off);
        if (p.err)
            break;
    }

    /* End of stream: a match whose raw offset field decodes to
     * APLIB_OFFSET_BIAS. The depacker computes off = (gamma << 8) + byte in
     * uint32, so the wrap is deliberate: (0x1000002 << 8) + 0xFF truncates to
     * 0x2FF == 767. Plain gamma 2 cannot be used because the depacker reads
     * that as the last-offset-reuse marker instead. */
    put_bit(&p, 0);
    put_gamma(&p, 0x1000002u);
    put_byte(&p, 0xFF);

    int err = p.err;
    free(head);
    free(prev);
    free(cost);
    free(lo);
    free(from);
    free(toff);
    free(tlen);
    free(path);
    if (err)
        return (size_t)-1;

    uint32_t stream = (uint32_t)(p.n - APLIB_SECT_HDR);
    uint32_t ssum   = 0;
    for (size_t k = APLIB_SECT_HDR; k < p.n; k++)
        ssum += out[k];
    wr32be(out, stream);
    wr32be(out + 4, ssum);
    return p.n;

oom:
    free(head);
    free(prev);
    free(cost);
    free(lo);
    free(from);
    free(toff);
    free(tlen);
    free(path);
    return (size_t)-1;
}
