/* Device and section name lookups. */
#include "device.h"
#include <string.h>

const char *elektron_device_name(uint8_t id) {
    switch (id) {
        case DEV_SIDSTATION: return "SidStation";
        case DEV_MACHINEDRUM: return "Machinedrum";
        case DEV_MONOMACHINE: return "Monomachine";
        case DEV_TM1: return "TM-1";
        case DEV_OCTATRACK: return "Octatrack";
        case DEV_ANALOG_FOUR: return "Analog Four / Analog Keys";
        case DEV_ANALOG_RYTM: return "Analog Rytm";
        case DEV_ANALOG_HEAT: return "Analog Heat";
        case DEV_ANALOG_DRIVE: return "Analog Drive";
        case DEV_DIGITAKT: return "Digitakt";
        case DEV_ANALOG_FOUR_II: return "Analog Four MKII";
        case DEV_ANALOG_RYTM_II: return "Analog Rytm MKII";
        case DEV_DIGITONE: return "Digitone / Digitone Keys";
        case DEV_ANALOG_HEAT_II: return "Analog Heat MKII";
        case DEV_MODEL_SAMPLES: return "Model:Samples";
        case DEV_MODEL_CYCLES: return "Model:Cycles";
        case DEV_ANALOG_HEAT_FX: return "Analog Heat +FX";
        case DEV_DIGITAKT_II: return "Digitakt II";
        case DEV_DIGITONE_II: return "Digitone II";
        case DEV_SYNTAKT: return "Syntakt";
        default: return "unknown";
    }
}

/* Section ids are not documented by Elektron; these names are inferred from
 * what the sections contain across the files we have, and are a convenience for
 * reports and extracted filenames rather than a statement about the format.
 * Treat them as labels, not as ground truth.
 *
 * Id 2 was called "DSP" until it was checked: on all 13 ELE3 images here it is
 * ColdFire code, not DSP data, and it names itself in its own strings --
 * "BOOTSTRAP UPGRADE", "OS UPGRADE", "STARTUP MENU", "PLEASE RESTART ME". It
 * also carries a uniform [u32 payload_size][u32 0x80010000] header, a load
 * address distinct from MAIN OS at 0x40000000. Hence "bootstrap", the
 * firmware's own word. Id 6 keeps "boot": it is ColdFire too but only ~1.5 kB
 * and carries no strings, so it is a separate stub, not this. */
const char *elektron_section_name(uint32_t id) {
    switch (id) {
        case 1: return "FPGA";
        case 2: return "bootstrap";
        case 3: return "MAIN OS";
        case 4: return "updater";
        case 5: return "meta";
        case 6: return "boot";
        case 7: return "blob";
        default: return "?";
    }
}

/* Classified by a leading content signature; unmatched sections are data banks.
 * Coarse by design -- the file carries no finer type information. */
const char *elektron_preele_section_name(const uint8_t *d, size_t n) {
    static const struct {
        uint8_t sig[3];
        uint8_t len;
        const char *name;
    } tbl[] = {
        {{0x2e, 0x7c}, 2, "MAIN OS"},   /* CPU code image   */
        {{0x03, 0x00, 0x00}, 3, "DSP"}, /* DSP loader block */
    };
    for (size_t s = 0; s < sizeof tbl / sizeof tbl[0]; s++)
        if (n >= tbl[s].len && !memcmp(d, tbl[s].sig, tbl[s].len))
            return tbl[s].name;
    return "data";
}
