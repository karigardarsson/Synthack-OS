/* The loaded firmware model: a .syx file, its transport layer, and the container
 * inside it -- plus every integrity check, computed once. */
#ifndef FIRMWARE_H
#define FIRMWARE_H

#include "container.h"
#include "transport.h"
#include "util.h"

/* The sysex layer. Device id, checksum seed and marker are transport facts, so
 * they live here rather than in bin_info. */
typedef struct {
    uint8_t device;
    transport_stats ts;
    uint32_t content_cksum;
    int have_marker;
    uint8_t base;
    uint8_t info[SYX_MARKER_INFO];
} sysex_info;

typedef struct {
    uint8_t *raw; /* .syx bytes (owned)                    */
    size_t raw_len;
    uint8_t *stream; /* decoded stream (owned)                */
    size_t stream_len;
    size_t container_off; /* preamble occupies stream[0, off) */
    int sysex_ok;         /* the transport decoded            */
    sysex_info sysex;
    bin_info bin;
    uint8_t *scratch; /* one shared depack buffer (owned) */
    size_t scratch_cap;
} firmware;

/* Load and fully parse a .syx. Returns 0, -2 if it is not a supported OS .syx,
 * or -1 on an I/O or structural error. */
int fw_load(const char *path, firmware *fw);
void fw_free(firmware *fw);

/* ------------------------------ verification ------------------------------- */

typedef enum { CHK_ABSENT, CHK_OK, CHK_BAD } check_state;

typedef struct {
    uint32_t id;
    int in_range;
    int compressed;
    size_t stored_len;       /* bytes the stored stream occupies */
    size_t decompressed_len; /* 0 unless compressed             */
    check_state stream_sum;
    uint32_t sum_stored, sum_calc;
    uint8_t head[8]; /* first decompressed bytes, for pre-ELE naming */
    size_t head_len;
} section_result;

/* Every check the file supports, each computed exactly once. Absent checks are
 * CHK_ABSENT: not every container carries every gate. */
typedef struct {
    check_state packet_cksum;  /* per-packet transport checksum   */
    check_state packet_count;  /* marker's declared packet count  */
    check_state content_cksum; /* ELE3 preamble content checksum  */
    check_state image_crc;     /* AD raw image CRC-32             */
    check_state digest;        /* ELE3 HMAC-SHA256 trailer        */
    uint32_t content_stored, content_calc;
    uint32_t crc_stored, crc_calc;
    uint32_t declared_packets;
    uint8_t digest_stored[DIGEST_LEN], digest_calc[DIGEST_LEN];
    uint32_t nsections;
    section_result sections[ELE3_MAX_SECTIONS];
    int all_ok; /* every present check passed */
} verify_result;

void fw_verify(firmware *fw, verify_result *vr);

#endif /* FIRMWARE_H */
