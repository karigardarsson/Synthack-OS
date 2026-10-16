/* Human-readable reporting. Everything here reads a verify_result; nothing here
 * recomputes a checksum. */
#ifndef REPORT_H
#define REPORT_H

#include "firmware.h"

const char *container_type_name(container_type ct);

/* ELE3 ids are typed; pre-ELE sections are classified from their content. */
const char *section_display_name(const bin_info *b, const section_result *sr);

void report_sysex(const firmware *fw);
void report_bin(const firmware *fw, const verify_result *vr, int verbose);
void report_full(const firmware *fw, const verify_result *vr, int verbose);

/* The one-glance default output: lists section ids so the user knows what to
 * pass to -d and -c. */
void report_summary(const firmware *fw, const verify_result *vr);

/* Printed when the transport decoded but no container magic was recognised. */
void report_unknown_container(void);

#endif /* REPORT_H */
