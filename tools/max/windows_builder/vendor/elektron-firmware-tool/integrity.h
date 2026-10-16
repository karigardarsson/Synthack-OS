/* Integrity primitives: SHA-256 / HMAC-SHA256, the container content checksum,
 * CRC-32, and the per-device key derivation.
 *
 * SHA-256 and HMAC-SHA256 are implemented from FIPS 180-4 and RFC 2104; CRC-32
 * is the reflected ISO 3309 / zlib variant. */
#ifndef INTEGRITY_H
#define INTEGRITY_H

#include <stdint.h>
#include <stddef.h>

/* Content checksum stored in the transport preamble at [4:8]: a 32-bit word sum
 * where each big-endian word is XORed with its 1-based index. */
uint32_t syx_content_checksum(const uint8_t *container, size_t clen);

/* Standard CRC-32, used for the Analog Drive raw image. */
uint32_t crc32_calc(const uint8_t *d, size_t n);

/* out = HMAC-SHA256(key, container[0:len]) -- the ELE3 container trailer. */
void syx_content_digest(const uint8_t key[32], const uint8_t *container, size_t len,
                        uint8_t out[32]);

enum { ELEKTRON_KEY_STR_MAX = 64 }; /* max length of the key-derivation string */

/* Derive the device's HMAC key from decompressed firmware bytes: locate the key
 * material block, compute a candidate key, and accept it only if
 * HMAC(key, msg[0:msglen]) equals expect[32]. On success fills key[32] (and, if
 * sbuf is non-NULL, the derivation string) and returns 1; returns 0 if no
 * candidate verifies. */
int elektron_extract_key(const uint8_t *fw, size_t fwlen, const uint8_t *msg, size_t msglen,
                         const uint8_t expect[32], uint8_t key[32], char *sbuf, size_t scap);

#endif /* INTEGRITY_H */
