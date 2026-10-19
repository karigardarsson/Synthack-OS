/* SysEx transport: the F0..F7 message stream that carries a container.
 *
 * Block-streaming transfer, each message wrapped in F0..F7:
 *   start marker (14B body)  : 00 20 3C dev 00 7F 01 <7B info>
 *   data packet  (126B body) : 00 20 3C dev 00 7E blk[2] seq <116B 8-in-7> cksum
 *   end marker   (14B body)  : 00 20 3C dev 00 7F 02 <7B info>
 * The 116B payload is 8-in-7: 14 full groups plus a partial => 101 decoded bytes.
 *
 * Machinedrum/Monomachine and Octatrack use an older 14-byte-header transport
 * with no block/seq and a nibble checksum; MD/MM additionally pack 2+7+7 (three
 * payload bytes per 16-bit word) instead of 8-in-7. */
#ifndef TRANSPORT_H
#define TRANSPORT_H

#include <stdint.h>
#include <stddef.h>

/* Elektron manufacturer id: first 3 bytes of every message body. */
enum { SYX_MFR_0 = 0x00, SYX_MFR_1 = 0x20, SYX_MFR_2 = 0x3C };
#define SYX_MFR_INIT {SYX_MFR_0, SYX_MFR_1, SYX_MFR_2}

/* Command byte (body[5]). */
enum { SYX_CMD_DATA = 0x7E, SYX_CMD_MARKER = 0x7F };
/* Marker kind (body[6] when cmd == SYX_CMD_MARKER). */
enum { MARKER_START = 0x01, MARKER_END = 0x02 };

/* SysEx framing and 7-bit-data constants. */
enum {
    SYX_START      = 0xF0, /* SysEx start byte                             */
    SYX_END        = 0xF7, /* SysEx end byte                               */
    SYX_MASK7      = 0x7F, /* 7-bit data mask (all SysEx data bytes)       */
    SYX_HIGH_BIT   = 0x80, /* MSB carried out-of-band by 8-in-7            */
    SYX_7IN8_GROUP = 7,    /* data bytes per 8-in-7 group (1 MSB + 7 data) */
    SYX_PREAMBLE   = 8,    /* decoded stream prefix: [size:4][checksum:4]  */
};

/* Packet geometry. All counts are body bytes, i.e. between F0 and F7. */
enum {
    SYX_PKT         = 126, /* data-packet body size                  */
    SYX_HDR         = 9,   /* header before payload (mfr..seq)       */
    SYX_ENC_PAY     = 116, /* 8-in-7 encoded payload bytes           */
    SYX_DEC_PER_PKT = 101, /* decoded bytes carried by one packet    */
    SYX_CKSUM_OFF   = 125, /* body offset of the per-packet checksum */
    SYX_MARKER      = 14,  /* marker body size                       */
    SYX_MARKER_INFO = 7,   /* marker info bytes (body[7..13])        */
    SYX_BLOCK_PKTS  = 128, /* packets per block (seq 0..127)         */
};

/* Field offsets within a data-packet body, shared by decoder and encoder. */
enum {
    PK_DEV         = 3,
    PK_CMD         = 5,
    PK_BLOCK       = 6,
    PK_SEQ         = 8,
    PK_PAYLOAD     = 9,
    PK_MARKER_KIND = 6, /* marker body[6]: MARKER_START / MARKER_END      */
    PK_MARKER_BASE = 7, /* start-marker info[0]: the checksum 'base' seed */
    /* the byte-125 checksum covers body[PK_BLOCK .. SYX_CKSUM_OFF-1] */
    SYX_CKSUM_SPAN = SYX_CKSUM_OFF - PK_BLOCK, /* = 119 bytes */
};

/* Legacy transport (Machinedrum/Monomachine and Octatrack). */
enum {
    LEGACY_THDR    = 14, /* transport header size                             */
    LEGACY_CK_HI   = 6,  /* per-packet checksum nibbles (body[6], body[7])    */
    LEGACY_CK_LO   = 7,
    LEGACY_NIB     = 8,      /* 6 counter nibbles, body[8..13]                    */
    PREELE_PKT     = 110,    /* MD/MM data-packet body size                       */
    PREELE_DEC_PKT = 64,     /* decoded bytes carried by one MD/MM data packet    */
    PREELE_COUNTER = 0x4000, /* per-packet counter S = base + decoded byte offset  */
    ELEK_PKT       = 86,     /* Octatrack data-packet body size                   */
    ELEK_DEC_PKT   = 63,     /* decoded bytes carried by one Octatrack packet     */
};

/* Byte-accurate view of a data-packet body (offsets 0..125, no F0/F7). */
typedef struct __attribute__((packed)) {
    uint8_t mfr[3];               /* 00 20 3C  Elektron manufacturer id     */
    uint8_t device;               /* elektron_device                        */
    uint8_t reserved;             /* 00                                     */
    uint8_t command;              /* SYX_CMD_DATA (0x7E)                    */
    uint8_t block[2];             /* 14-bit block number, big-endian        */
    uint8_t seq;                  /* packet index within the block (0..127) */
    uint8_t payload[SYX_ENC_PAY]; /* 8-in-7 encoded (=101 decoded bytes)    */
    uint8_t checksum;             /* per-packet checksum                    */
} syx_data_packet;

/* Byte-accurate view of a start/end marker body (offsets 0..13, no F0/F7). */
typedef struct __attribute__((packed)) {
    uint8_t mfr[3];                /* 00 20 3C                                */
    uint8_t device;                /* elektron_device                         */
    uint8_t reserved;              /* 00                                      */
    uint8_t command;               /* SYX_CMD_MARKER (0x7F)                   */
    uint8_t kind;                  /* MARKER_START (0x01) / MARKER_END (0x02) */
    uint8_t info[SYX_MARKER_INFO]; /* transfer length / block count / cksum   */
} syx_marker;

_Static_assert(sizeof(syx_data_packet) == SYX_PKT, "syx_data_packet must be 126 bytes");
_Static_assert(sizeof(syx_marker) == SYX_MARKER, "syx_marker must be 14 bytes");

/* Statistics gathered while decoding, for reporting. */
typedef struct {
    size_t file_size, nmsg, ndata, nmarker, decoded;
    size_t pkt_body, hdr, pay;
    size_t pkt_ck_ok, pkt_ck_bad; /* per-packet transport checksum verification */
    int nblocks, min_pk, max_pk;
    long first_block, seq0, seqN;
    uint8_t marker[2][16];
    int marker_len[2], nmarker_saved;
    /* Encoded payload of the last data packet. A partly-filled 8-in-7 group has
     * MSB bits, and a 2+7+7 word has low bits, that no decoded byte depends on;
     * the original encoder left values there that cannot be derived. Keeping the
     * bytes lets an unmodified file re-encode byte-exactly. */
    uint8_t last_pay[SYX_PKT];
    size_t last_pay_len;
} transport_stats;

/* Walk the F0..F7 messages in a file. Yields each message body (between the
 * framing bytes), skipping anything that is not a complete message. */
typedef struct {
    const uint8_t *buf;
    size_t len, pos;
} syx_iter;

static inline void syx_iter_init(syx_iter *it, const uint8_t *buf, size_t len) {
    it->buf = buf;
    it->len = len;
    it->pos = 0;
}
int syx_next(syx_iter *it, const uint8_t **body, size_t *body_len);

/* Decode the transport into a malloc'd stream (preamble + container; caller
 * frees). Sets dec_len and the device id. If ts is non-NULL it is filled with
 * statistics. Returns NULL if no data packets were found. */
uint8_t *syx_transport_decode(const uint8_t *buf, size_t fsz, size_t *dec_len, uint8_t *dev,
                              transport_stats *ts);

/* Encode preamble+container into a malloc'd .syx (caller frees), sets out_len. */
uint8_t *syx_encode(const uint8_t *container, size_t clen, uint8_t dev,
                    const uint8_t preamble[SYX_PREAMBLE], uint8_t base,
                    const uint8_t marker_info[SYX_MARKER_INFO], size_t *out_len, int verbose);

/* Legacy transports. Byte-identical to stock MD/MM (2+7+7) and OT (8-in-7).
 * tail/tail_len is the observed final-packet payload from transport_stats, or
 * NULL/0. It is used only if it decodes to exactly the bytes being emitted, so
 * substituting it can never change the content. */
uint8_t *preele_encode(const uint8_t *container, size_t clen, uint8_t dev, const uint8_t *tail,
                       size_t tail_len, size_t *out_len, int verbose);
uint8_t *elek_encode(const uint8_t *container, size_t clen, uint8_t dev, const uint8_t *tail,
                     size_t tail_len, size_t *out_len, int verbose);

/* Fill the preamble: [0:4] = container size, [4:8] = content checksum. */
void syx_build_preamble(uint8_t preamble[SYX_PREAMBLE], const uint8_t *container, size_t clen);

/* Per-packet checksum (byte 125) for the modern transport. */
uint8_t syx_block_checksum(const uint8_t *body, uint8_t base);

/* Legacy per-packet checksum: sum of the decoded payload bytes plus a
 * device-specific term over the 6 counter nibbles (body[8..13]). */
uint8_t legacy_packet_checksum(uint8_t dev, const uint8_t nib[6], unsigned payload_sum);

/* Locate the start marker's checksum base seed and info bytes. Returns 0 if the
 * file has no marker message. */
int syx_find_marker_info(const uint8_t *buf, size_t fsz, uint8_t *base,
                         uint8_t info[SYX_MARKER_INFO]);

#endif /* TRANSPORT_H */
