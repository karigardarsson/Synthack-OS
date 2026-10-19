/* aPLib-variant codec: LZ77 + interlaced Elias-gamma. */
#ifndef APLIB_H
#define APLIB_H

#include <stdint.h>
#include <stddef.h>

/* The section header preceding every stream is [u32 length BE][u32 byte-sum BE]. */
enum {
    APLIB_OFFSET_BIAS   = 767,  /* off = rawoff - BIAS; rawoff == BIAS -> end marker */
    APLIB_REUSE_GAMMA   = 2,    /* gamma value selecting last-offset reuse (R0)      */
    APLIB_FAR_THRESHOLD = 3328, /* off > this: +1 length bonus, min match 3          */
    APLIB_MIN_MATCH     = 2,    /* min match length (3 when off > FAR_THRESHOLD)     */
    APLIB_SECT_HDR      = 8,    /* section-header bytes before the stream            */
    APLIB_LIT_BITS      = 9,    /* cost of a literal (1 control bit + 8 data)        */
};

/* Compression effort: how hard the packer looks for matches. Every level
 * produces a valid stream and every level compresses better than the streams
 * Elektron ships; the choice only trades time for size. Rebuilding a Digitakt II
 * OS, against the stock file:
 *     0   0.7 s   -2.2%        2   2.8 s   -5.4%
 *     1   1.1 s   -4.4%        3  12.7 s   -6.0%   */
enum {
    APLIB_LEVEL_MIN     = 0,
    APLIB_LEVEL_MAX     = 3,
    APLIB_LEVEL_DEFAULT = APLIB_LEVEL_MAX,
};

/* Farthest back a match may reference. The format itself permits more, but no
 * stock Elektron stream ever exceeds this: across ten device images the highest
 * offset observed is 2^20 - 4, and none reaches 2^20. Staying inside the
 * envelope their own compressor demonstrates costs about 0.1% of ratio and
 * avoids emitting offsets that no shipped firmware has ever contained -- which
 * the depacker on the device may not be prepared for. */
enum { APLIB_MAX_OFFSET = 1u << 20 };

/* Both operate on a whole section: the 8-byte header followed by the compressed
 * stream. src/out point at the header; the codec skips it on read and fills it
 * on write. allow_trunc returns partial output on input exhaustion instead of
 * failing. Both return the length produced, or (size_t)-1. */
size_t ap_depack(const uint8_t *src, size_t srclen, uint8_t *out, size_t outcap, int allow_trunc);
size_t ap_pack(const uint8_t *data, size_t len, uint8_t *out, size_t outcap, int level);

#endif /* APLIB_H */
