/* Byte-order helpers, alignment, and this tool's own capacity limits. */
#ifndef UTIL_H
#define UTIL_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* Implementation limits, not format facts. A section does not record its
 * decompressed size, so the depacker needs a ceiling to write into. */
enum {
    SCRATCH_CAP     = 64u << 20, /* buffer for one decompressed section */
    CONTAINER_ALIGN = 16,        /* section start and HMAC alignment    */
    DIGEST_LEN      = 32,        /* SHA-256 / HMAC-SHA256 output        */
};

static inline uint32_t be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static inline void wr32be(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

static inline size_t align_up(size_t v, size_t a) {
    return (v + a - 1) & ~(a - 1);
}

/* Room for n bytes at pos in a buffer of cap bytes. */
static inline int fits(size_t cap, size_t pos, size_t n) {
    return pos <= cap && n <= cap - pos;
}

/* Allocation failure is not recoverable here, so bail rather than thread NULL
 * through every caller. */
static inline void *xalloc(size_t n) {
    void *p = calloc(1, n ? n : 1);
    if (!p) {
        fprintf(stderr, "out of memory (%zu bytes)\n", n);
        exit(1);
    }
    return p;
}

/* Read a whole file. Returns NULL (after reporting) on any failure. */
static inline uint8_t *read_file(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror(path);
        return NULL;
    }
    long n = -1;
    if (fseek(f, 0, SEEK_END) == 0)
        n = ftell(f); /* -1 on a directory or a pipe */
    if (n < 0 || fseek(f, 0, SEEK_SET) != 0) {
        perror(path);
        fclose(f);
        return NULL;
    }
    uint8_t *b = (uint8_t *)xalloc((size_t)n);
    if (fread(b, 1, (size_t)n, f) != (size_t)n) {
        perror(path);
        fclose(f);
        free(b);
        return NULL;
    }
    fclose(f);
    *len = (size_t)n;
    return b;
}

#endif /* UTIL_H */
