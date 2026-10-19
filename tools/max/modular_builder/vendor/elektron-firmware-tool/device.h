/* Elektron SysEx product ids, and names for reporting. */
#ifndef DEVICE_H
#define DEVICE_H

#include <stdint.h>
#include <stddef.h>

/* SysEx product id (byte 3 of every Elektron SysEx message).
 * 0x00 = Turbo MIDI negotiation; 0x10 and 0x12 are unassigned. */
typedef enum {
    DEV_SIDSTATION     = 0x01, /* no .syx OS (EPROM)   */
    DEV_MACHINEDRUM    = 0x02,
    DEV_MONOMACHINE    = 0x03,
    DEV_TM1            = 0x04, /* USB/MIDI interface   */
    DEV_OCTATRACK      = 0x05,
    DEV_ANALOG_FOUR    = 0x06,
    DEV_ANALOG_RYTM    = 0x07,
    DEV_ANALOG_HEAT    = 0x08,
    DEV_ANALOG_DRIVE   = 0x09,
    DEV_DIGITAKT       = 0x0a,
    DEV_ANALOG_FOUR_II = 0x0b,
    DEV_ANALOG_RYTM_II = 0x0c,
    DEV_DIGITONE       = 0x0d,
    DEV_ANALOG_HEAT_II = 0x0e,
    DEV_MODEL_SAMPLES  = 0x0f,
    DEV_MODEL_CYCLES   = 0x11,
    DEV_ANALOG_HEAT_FX = 0x13,
    DEV_DIGITAKT_II    = 0x14,
    DEV_DIGITONE_II    = 0x15,
    DEV_SYNTAKT        = 0x16,
} elektron_device;

const char *elektron_device_name(uint8_t id);

/* ELE3 section type ids. */
const char *elektron_section_name(uint32_t id);

/* pre-ELE sections carry no type id, so they are classified by content. */
const char *elektron_preele_section_name(const uint8_t *d, size_t n);

#endif /* DEVICE_H */
