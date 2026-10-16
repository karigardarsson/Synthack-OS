# Provenance

This records how the code in this repository was produced, to document that it
is an independent implementation.

## Source code

All source in this repository was written independently by the author. No
Elektron source code, decompiler or disassembler output, or third-party
implementation was copied.

## File formats

The SysEx transport and container layouts were established by observing and
testing OS `.syx` files that were lawfully obtained (public downloads and files
present on hardware owned by the author). Only factual compatibility
information was used: manufacturer and product IDs, field offsets, packet
sizes, magic values, and checksum behaviour. No firmware code or content was
copied into this repository.

## Algorithms

The following are implemented from their public specifications, not from any
particular third-party source:

- SHA-256 and HMAC-SHA256 (FIPS 180-4, RFC 2104)
- CRC-32 (reflected, polynomial 0xEDB88320; ISO 3309 / zlib)
- an LZ77 + Elias-gamma codec resembling the aPLib format; written from a
  description of the format, containing no aPLib source

## Keys

No keys are stored in this repository. The per-device HMAC key is recomputed at
runtime from material contained in the user-supplied firmware image and is
accepted only if it reproduces that image's own digest.

## Records

Dated development notes describing what was observed and how the implementation
was written independently are retained privately and can be produced if the
provenance of this work is ever questioned.
