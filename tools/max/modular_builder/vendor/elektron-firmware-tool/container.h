/* Container formats carried inside the SysEx transport.
 *
 * Five layouts exist. All fields are big-endian.
 *   ELE3     multi-section table, content checksum, HMAC-SHA256 trailer
 *   ELE2     single OS section, no table, no digest
 *   ELEK     Octatrack: header + single [size][sum] aPLib section
 *   AD       Analog Drive: 16-byte header + raw uncompressed image, CRC-32
 *   pre-ELE  Machinedrum/Monomachine: positional [size][sum] aPLib sections,
 *            no magic and no header table */
#ifndef CONTAINER_H
#define CONTAINER_H

#include <stdint.h>
#include <stddef.h>
#include "integrity.h"

typedef enum { CT_NONE, CT_ELE3, CT_ELE2, CT_ELEK, CT_AD, CT_PREELE } container_type;

/* ELE3: multi-section table. */
enum {
    ELE3_BUILD_OFF    = 0x07,
    ELE3_VERSION_OFF  = 0x13, /* where the version sits; located by pattern, not this */
    ELE3_COUNT_OFF    = 0x1C,
    ELE3_TABLE_OFF    = 0x20,
    ELE3_ENTRY_SZ     = 16,
    ELE3_MAX_SECTIONS = 64,
};

/* ELE2 and ELEK: a single OS section. */
enum {
    ELE2_BUILD_OFF   = 0x04,
    ELE2_VERSION_OFF = 0x0F, /* as above: documented, not used for lookup */
    ELE2_DEST_OFF    = 0x14,
    ELE2_SECT_OFF    = 0x18,
    ELEK_BUILD_OFF   = 0x04,
    /* Unlike ELE2/ELE3, ELEK's version is a fixed 10-byte field, right-justified
     * and space-padded, running from here up to ELEK_SECT_OFF. A 5-character
     * version such as "1.40C" therefore starts at 0x0D, which is why that offset
     * passes for the field start on a single sample. */
    ELEK_VERSION_OFF = 0x08,
    ELEK_SECT_OFF    = 0x12,
};

/* AD (Analog Drive). */
enum {
    AD_LEN_OFF = 0x04,
    AD_CRC_OFF = 0x08,
    AD_IMG_OFF = 0x10,
};

/* pre-ELE section framing. */
enum {
    PREELE_SECT_HDR = 8,  /* [u32 comp_size BE][u32 byte-sum BE] */
    PREELE_MIN_SECT = 16, /* smallest plausible section stream    */
};

typedef struct {
    uint32_t id, offset, comp_len, dest;
} ele3_section;

/* A parsed container: the bin layer inside the .syx. */
typedef struct {
    const uint8_t *data; /* container bytes, pointing into the decoded stream */
    size_t len;
    size_t declared_size; /* from the transport preamble where present */
    container_type type;
    size_t trailer_bytes; /* bytes past the 16-aligned end of sections */
    uint32_t nsections;
    ele3_section sections[ELE3_MAX_SECTIONS];
    int have_key;
    uint8_t key[32];
    char key_str[ELEKTRON_KEY_STR_MAX + 1];
} bin_info;

/* A section replacement: raw decompressed bytes to store into section 'id'. */
typedef struct {
    uint32_t id;
    const char *file;
    uint8_t *data;
    size_t len;
} override;

/* Locate the container inside a decoded stream. pre-ELE carries no magic and is
 * identified by device id instead. Sets *off to the container start. */
container_type container_detect(const uint8_t *stream, size_t len, uint8_t dev, size_t *off);

/* Parse a container header and section table. preamble_size is the size field
 * from the transport preamble, or 0 for formats without one. Returns 0, or -1 on
 * a malformed section count, or -2 if the container is too short. */
int container_parse(const uint8_t *data, size_t len, container_type ct, size_t preamble_size,
                    bin_info *b);

/* Find the HMAC key from the container's own sections, verifying it against the
 * trailer digest. Fills b->have_key/key/key_str. Needs a scratch buffer. */
void container_find_key(bin_info *b, uint8_t *scratch, size_t scap);

/* Decompress one section into scratch. Returns the decompressed length, or
 * (size_t)-1 if the section is not an aPLib stream (i.e. stored raw). */
size_t container_section_depack(const bin_info *b, const ele3_section *sec, uint8_t *scratch,
                                size_t scap);

/* Bytes a section's stored stream occupies, clamped to the container. */
size_t container_section_stored_len(const bin_info *b, const ele3_section *sec);

/* The [size][sum] header check on a compressed section's stream. */
int container_section_stream_sum(const bin_info *b, const ele3_section *sec, uint32_t *stored,
                                 uint32_t *calc);

const ele3_section *container_find_section(const bin_info *b, uint32_t id);

/* One past the last byte of a container's text header. Scans for the build,
 * model or version string must stop here; beyond it is binary. */
int container_header_end(container_type ct);

/* Offset of the first "<digit>.<digit>" in c[from..lim), or -1. The version's
 * offset varies per device, so it is found by pattern rather than by offset. */
int container_find_version_pattern(const uint8_t *c, int from, int lim);

/* Locate the writable version field, setting voff and vend. Returns 0 on
 * success, -1 if no version field is present, -2 for a container type that has
 * no editable one. Note this is deliberately not how the version is located for
 * *display*: ELEK's field is at a fixed offset, but reports scan for it. */
int container_version_field(const uint8_t *c, size_t clen, container_type ct, int *voff, int *vend);

/* Overwrite the version string in place, space-padded to the field width
 * (right-justified for ELEK, whose field is fixed-width; left-justified at the
 * existing string's offset for ELE2/ELE3).
 * Returns 0, -1 no field, -2 unsupported container, -3 string too long. */
int container_set_version(uint8_t *c, size_t clen, container_type ct, const char *ver);

/* Assemble a new container into nc. Returns the new length, or (size_t)-1 if it
 * would not fit or a section failed to recompress. For ELE3 the return value is
 * the offset just past the last section; the caller appends the trailer. */
size_t container_build(const bin_info *b, uint8_t *nc, size_t cap, const override *ovs, int novs,
                       uint8_t *scratch, size_t scap, int level);

/* Append [pad][4 zero bytes][32-byte HMAC], the digest 16-byte aligned. */
size_t container_append_trailer(uint8_t *c, size_t cap, size_t end, const uint8_t key[32]);

#endif /* CONTAINER_H */
