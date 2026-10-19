/* Loading a .syx and verifying every integrity gate it carries. */
#include "firmware.h"
#include "aplib.h"
#include "util.h"

int fw_load(const char *path, firmware *fw) {
    memset(fw, 0, sizeof *fw);
    fw->raw = read_file(path, &fw->raw_len);
    if (!fw->raw)
        return -1;
    if (!(fw->raw_len > 0 && fw->raw[0] == SYX_START))
        return -2;

    size_t dlen = 0;
    fw->stream =
        syx_transport_decode(fw->raw, fw->raw_len, &dlen, &fw->sysex.device, &fw->sysex.ts);
    if (!fw->stream)
        return -1;
    fw->sysex_ok   = 1;
    fw->stream_len = dlen;

    size_t moff       = 0;
    container_type ct = container_detect(fw->stream, dlen, fw->sysex.device, &moff);
    fw->container_off = moff;

    const uint8_t *cdata = fw->stream + moff;
    size_t clen          = dlen - moff;
    fw->bin.type         = ct;
    fw->bin.data         = cdata;
    fw->bin.len          = clen;

    fw->scratch     = xalloc(SCRATCH_CAP);
    fw->scratch_cap = SCRATCH_CAP;

    /* ELEK and pre-ELE carry no transport preamble, so they never consult one. */
    if (ct == CT_PREELE || ct == CT_ELEK)
        return container_parse(cdata, clen, ct, 0, &fw->bin);

    if ((ct != CT_ELE3 && ct != CT_ELE2 && ct != CT_AD) || moff < SYX_PREAMBLE)
        return -2;

    fw->sysex.content_cksum = be32(fw->stream + 4);
    fw->sysex.have_marker =
        syx_find_marker_info(fw->raw, fw->raw_len, &fw->sysex.base, fw->sysex.info);

    int rc = container_parse(cdata, clen, ct, be32(fw->stream), &fw->bin);
    if (rc != 0)
        return rc;

    if (ct == CT_ELE3)
        container_find_key(&fw->bin, fw->scratch, fw->scratch_cap);
    return 0;
}

void fw_free(firmware *fw) {
    free(fw->raw);
    free(fw->stream);
    free(fw->scratch);
    fw->raw = fw->stream = fw->scratch = NULL;
}

/* ------------------------------ verification ------------------------------- */

void fw_verify(firmware *fw, verify_result *vr) {
    memset(vr, 0, sizeof *vr);
    const bin_info *b = &fw->bin;
    size_t size       = b->declared_size;
    int ok            = 1;

    /* transport: per-packet checksums */
    if (fw->sysex.ts.pkt_ck_ok + fw->sysex.ts.pkt_ck_bad > 0) {
        vr->packet_cksum = fw->sysex.ts.pkt_ck_bad ? CHK_BAD : CHK_OK;
        if (fw->sysex.ts.pkt_ck_bad)
            ok = 0;
    }

    /* transport: the start marker's declared packet count */
    if (fw->sysex.have_marker) {
        vr->declared_packets = ((uint32_t)fw->sysex.info[4] << 14) |
                               ((uint32_t)fw->sysex.info[5] << 7) | fw->sysex.info[6];
        vr->packet_count = (vr->declared_packets == fw->sysex.ts.ndata) ? CHK_OK : CHK_BAD;
        if (vr->packet_count == CHK_BAD)
            ok = 0;
    }

    /* AD is a special case: the image CRC is the only gate it carries, and it
     * alone decides the verdict. */
    if (b->type == CT_AD) {
        vr->crc_stored = be32(b->data + AD_CRC_OFF);
        vr->crc_calc   = crc32_calc(b->data + AD_IMG_OFF, b->sections[0].comp_len);
        vr->image_crc  = (vr->crc_stored == vr->crc_calc) ? CHK_OK : CHK_BAD;
        vr->all_ok     = (vr->image_crc == CHK_OK);
        vr->nsections  = b->nsections;
        for (uint32_t s = 0; s < b->nsections; s++) {
            vr->sections[s].id         = b->sections[s].id;
            vr->sections[s].in_range   = fits(b->len, b->sections[s].offset, APLIB_SECT_HDR);
            vr->sections[s].stored_len = container_section_stored_len(b, &b->sections[s]);
            vr->sections[s].stream_sum = CHK_ABSENT;
        }
        return;
    }

    if (b->type == CT_ELE3) {
        /* The stored value is always reported; calc is 0 when the declared size
         * runs past the container, and the verdict then ignores this gate. */
        vr->content_stored = fw->sysex.content_cksum;
        vr->content_calc   = (size <= b->len) ? syx_content_checksum(b->data, size) : 0;
        vr->content_cksum  = (vr->content_stored == vr->content_calc) ? CHK_OK : CHK_BAD;
        if (size <= b->len && vr->content_cksum == CHK_BAD)
            ok = 0;
    }

    /* sections: one depack each, into the shared scratch buffer */
    vr->nsections = b->nsections;
    for (uint32_t s = 0; s < b->nsections; s++) {
        const ele3_section *sec = &b->sections[s];
        section_result *sr      = &vr->sections[s];
        sr->id                  = sec->id;
        sr->in_range            = fits(b->len, sec->offset, APLIB_SECT_HDR);
        sr->stored_len          = container_section_stored_len(b, sec);
        sr->stream_sum          = CHK_ABSENT;
        if (!sr->in_range)
            continue;

        size_t dn      = container_section_depack(b, sec, fw->scratch, fw->scratch_cap);
        sr->compressed = (dn != (size_t)-1 && dn > 0);
        if (!sr->compressed)
            continue; /* stored raw: no stream sum to check */

        sr->decompressed_len = dn;
        sr->head_len         = dn < sizeof sr->head ? dn : sizeof sr->head;
        memcpy(sr->head, fw->scratch, sr->head_len);

        if (container_section_stream_sum(b, sec, &sr->sum_stored, &sr->sum_calc)) {
            sr->stream_sum = (sr->sum_stored == sr->sum_calc) ? CHK_OK : CHK_BAD;
            if (sr->stream_sum == CHK_BAD)
                ok = 0;
        }
    }

    /* container trailer: HMAC over everything before the digest */
    if (b->have_key && size >= 4 + DIGEST_LEN && size <= b->len) {
        memcpy(vr->digest_stored, b->data + size - DIGEST_LEN, DIGEST_LEN);
        syx_content_digest(b->key, b->data, size - DIGEST_LEN, vr->digest_calc);
        vr->digest = !memcmp(vr->digest_stored, vr->digest_calc, DIGEST_LEN) ? CHK_OK : CHK_BAD;
        /* Matches the original verdict order: the digest is only consulted when
         * everything before it already passed. */
        if (ok && vr->digest == CHK_BAD)
            ok = 0;
    }

    vr->all_ok = ok;
}
