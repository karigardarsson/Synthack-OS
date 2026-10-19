/* Integrity primitives. */
#include "integrity.h"
#include <string.h>

/* --------------------------------- SHA-256 --------------------------------- */

typedef struct {
    uint32_t h[8];
    uint64_t bits;
    uint8_t buf[64];
    size_t n;
} sha256;

static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

static uint32_t ror(uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
}

static void sha256_init(sha256 *c) {
    static const uint32_t iv[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                   0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(c->h, iv, sizeof iv);
    c->bits = 0;
    c->n    = 0;
}

static void sha256_blk(sha256 *c, const uint8_t *p) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[4 * i] << 24) | ((uint32_t)p[4 * i + 1] << 16) |
               ((uint32_t)p[4 * i + 2] << 8) | p[4 * i + 3];
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ror(w[i - 15], 7) ^ ror(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ror(w[i - 2], 17) ^ ror(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i]        = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = c->h[0], b = c->h[1], cc = c->h[2], d = c->h[3];
    uint32_t e = c->h[4], f = c->h[5], g = c->h[6], h = c->h[7];
    for (int i = 0; i < 64; i++) {
        uint32_t S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25), ch = (e & f) ^ (~e & g);
        uint32_t t1 = h + S1 + ch + K[i] + w[i];
        uint32_t S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22), mj = (a & b) ^ (a & cc) ^ (b & cc);
        uint32_t t2 = S0 + mj;
        h           = g;
        g           = f;
        f           = e;
        e           = d + t1;
        d           = cc;
        cc          = b;
        b           = a;
        a           = t1 + t2;
    }
    c->h[0] += a;
    c->h[1] += b;
    c->h[2] += cc;
    c->h[3] += d;
    c->h[4] += e;
    c->h[5] += f;
    c->h[6] += g;
    c->h[7] += h;
}

static void sha256_upd(sha256 *c, const uint8_t *d, size_t n) {
    c->bits += (uint64_t)n * 8;
    while (n) {
        size_t k = 64 - c->n;
        if (k > n)
            k = n;
        memcpy(c->buf + c->n, d, k);
        c->n += k;
        d += k;
        n -= k;
        if (c->n == 64) {
            sha256_blk(c, c->buf);
            c->n = 0;
        }
    }
}

static void sha256_fin(sha256 *c, uint8_t out[32]) {
    uint64_t bits = c->bits;
    uint8_t pad   = 0x80;
    sha256_upd(c, &pad, 1);
    uint8_t z = 0;
    while (c->n != 56)
        sha256_upd(c, &z, 1);
    uint8_t L[8];
    for (int i = 0; i < 8; i++)
        L[i] = (uint8_t)(bits >> (56 - 8 * i));
    sha256_upd(c, L, 8);
    for (int i = 0; i < 8; i++) {
        out[4 * i]     = (uint8_t)(c->h[i] >> 24);
        out[4 * i + 1] = (uint8_t)(c->h[i] >> 16);
        out[4 * i + 2] = (uint8_t)(c->h[i] >> 8);
        out[4 * i + 3] = (uint8_t)c->h[i];
    }
}

static void hmac_sha256(const uint8_t *key, size_t kl, const uint8_t *d, size_t dl,
                        uint8_t out[32]) {
    uint8_t k[64] = {0}, ip[64], op[64], ih[32];
    sha256 c;
    if (kl > 64) {
        sha256_init(&c);
        sha256_upd(&c, key, kl);
        sha256_fin(&c, k);
    } else {
        memcpy(k, key, kl);
    }
    for (int i = 0; i < 64; i++) {
        ip[i] = k[i] ^ 0x36;
        op[i] = k[i] ^ 0x5c;
    }
    sha256_init(&c);
    sha256_upd(&c, ip, 64);
    sha256_upd(&c, d, dl);
    sha256_fin(&c, ih);
    sha256_init(&c);
    sha256_upd(&c, op, 64);
    sha256_upd(&c, ih, 32);
    sha256_fin(&c, out);
}

void syx_content_digest(const uint8_t key[32], const uint8_t *container, size_t len,
                        uint8_t out[32]) {
    hmac_sha256(key, 32, container, len, out);
}

/* ---------------------------- homebrew checksums --------------------------- */

uint32_t syx_content_checksum(const uint8_t *container, size_t clen) {
    uint32_t acc  = 0;
    size_t nwords = clen / 4;
    for (size_t k = 0; k < nwords; k++) {
        uint32_t w = ((uint32_t)container[4 * k] << 24) | ((uint32_t)container[4 * k + 1] << 16) |
                     ((uint32_t)container[4 * k + 2] << 8) | (uint32_t)container[4 * k + 3];
        acc += ((uint32_t)(k + 1)) ^ w;
    }
    return acc;
}

uint32_t crc32_calc(const uint8_t *d, size_t n) {
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        c ^= d[i];
        for (int k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320u & (uint32_t) - (int32_t)(c & 1));
    }
    return c ^ 0xFFFFFFFFu;
}

/* ------------------------------ key derivation ---------------------------- */

/* Recompute the key from its material block: a string s and a 32-byte constant. */
static void derive_key(const uint8_t *s, size_t slen, const uint8_t *cnst, uint8_t key[32]) {
    uint8_t rev[ELEKTRON_KEY_STR_MAX], h[32], hr[32];
    sha256 c;
    for (size_t i = 0; i < slen; i++)
        rev[i] = s[slen - 1 - i];
    sha256_init(&c);
    sha256_upd(&c, s, slen);
    sha256_fin(&c, h);
    sha256_init(&c);
    sha256_upd(&c, rev, slen);
    sha256_fin(&c, hr);
    for (int i = 0; i < 32; i++)
        key[i] = h[i] ^ hr[i] ^ cnst[i];
}

int elektron_extract_key(const uint8_t *fw, size_t fwlen, const uint8_t *msg, size_t msglen,
                         const uint8_t expect[32], uint8_t key[32], char *sbuf, size_t scap) {
    static const uint8_t anchor[8] = {0xbe, 0xf9, 0xa3, 0xf7, 0xc6, 0x71, 0x78, 0xf2};
    for (size_t i = 0; i + 8 <= fwlen; i++) { /* <=: the last window counts too */
        if (memcmp(fw + i, anchor, 8))
            continue;
        size_t s = i + 8, p = s;
        while (p < fwlen && fw[p] >= 0x20 && fw[p] < 0x7f && p - s < ELEKTRON_KEY_STR_MAX)
            p++;
        size_t slen = p - s;
        if (!slen || p >= fwlen || fw[p] != 0 || p + 1 + 32 > fwlen)
            continue;
        uint8_t cand[32], dig[32];
        derive_key(fw + s, slen, fw + p + 1, cand);
        hmac_sha256(cand, 32, msg, msglen, dig);
        if (memcmp(dig, expect, 32))
            continue;
        memcpy(key, cand, 32);
        if (sbuf && scap) {
            size_t n = slen < scap - 1 ? slen : scap - 1;
            memcpy(sbuf, fw + s, n);
            sbuf[n] = 0;
        }
        return 1;
    }
    return 0;
}
