/* Scoped master-compressor UI ownership for Syntakt OS 1.41. */
typedef unsigned int u32;
typedef int s32;
typedef unsigned short u16;

#define DATA __attribute__((section(".data")))
#define PROJECT (*(u32 * volatile const)0x444E13F4u)
#define ACTIVE_TRACK ((s32 (*)(u32))0x4001FF74u)
#define FX_TRACK 12
#define DESC_BASE 0x4022D59Cu
#define OBJS_BASE 0x41B9FA24u
#define FX_SLOTS ((u32 *)0x41B9F950u)
#define NP 7u

#ifndef COMP_INIT
#error COMP_INIT must be supplied by the generator
#endif
#ifndef N_THR_S
#error parameter-name addresses must be supplied by the generator
#endif

static unsigned short ids[NP] DATA = {262,263,264,265,266,267,268};
static u32 maxv[NP] DATA = {0x7F00,0x7F00,0x7F00,0x7F00,0x7F00,0x7F00,0x100};
static u32 defv[NP] DATA = {D_THR,D_ATK,D_REL,D_MUP,D_RAT,0,0x100};
static u16 proto_from[NP] DATA = {144,122,91,101,125,59,0};
static u16 gfx_from[NP] DATA = {144,122,91,101,125,59,115};
static u16 style_from[NP] DATA = {0,122,0,0,125,59,115};
static char *long_names[NP] DATA = {
    (const char *)N_THR_L,(const char *)N_ATK_L,(const char *)N_REL_L,
    (const char *)N_MUP_L,(const char *)N_RAT_L,(const char *)N_GR_L,(const char *)N_COMP_L};
static char *short_names[NP] DATA = {
    (const char *)N_THR_S,(const char *)N_ATK_S,(const char *)N_REL_S,
    (const char *)N_MUP_S,(const char *)N_RAT_S,(const char *)N_GR_S,(const char *)N_COMP_S};

static u32 saved_obj[NP][14] DATA = {{0}};
static u32 saved_desc[NP][5] DATA = {{0}};
static u32 saved_slots[8] DATA = {0};
static u32 snapshot DATA = 0;
static u32 owned DATA = 0;

static u32 *obj(u32 id) { return (u32 *)(OBJS_BASE + 84u * id); }
static u32 *desc(u32 id) { return (u32 *)(DESC_BASE + 52u * id); }

static void copy4(u32 *dst, const u32 *src)
{
    dst[0] = src[0]; dst[1] = src[1]; dst[2] = src[2]; dst[3] = src[3];
}

static void capture(void)
{
    u32 i, j;
    if (snapshot) return;
    for (i = 0; i < NP; i++) {
        u32 *d = desc(ids[i]), *o = obj(ids[i]);
        saved_desc[i][0] = d[2]; saved_desc[i][1] = d[3]; saved_desc[i][2] = d[4];
        saved_desc[i][3] = d[10]; saved_desc[i][4] = d[12];
        saved_obj[i][0] = o[0]; saved_obj[i][1] = o[1];
        for (j = 0; j < 4; j++) {
            saved_obj[i][2+j] = o[5+j];
            saved_obj[i][6+j] = o[9+j];
            saved_obj[i][10+j] = o[17+j];
        }
    }
    for (i = 0; i < 8; i++) saved_slots[i] = FX_SLOTS[i];
    snapshot = 1;
}

static void restore(void)
{
    u32 i, j;
    if (!owned) return;
    for (i = 0; i < NP; i++) {
        u32 *d = desc(ids[i]), *o = obj(ids[i]);
        d[2] = saved_desc[i][0]; d[3] = saved_desc[i][1]; d[4] = saved_desc[i][2];
        d[10] = saved_desc[i][3]; d[12] = saved_desc[i][4];
        o[0] = saved_obj[i][0]; o[1] = saved_obj[i][1];
        for (j = 0; j < 4; j++) {
            o[5+j] = saved_obj[i][2+j];
            o[9+j] = saved_obj[i][6+j];
            o[17+j] = saved_obj[i][10+j];
        }
    }
    for (i = 0; i < 8; i++) FX_SLOTS[i] = saved_slots[i];
    owned = 0;
}

static void claim(void)
{
    u32 i;
    if (owned) return;
    capture();
    ((void (*)(void))COMP_INIT)();
    for (i = 0; i < NP; i++) {
        u32 *d = desc(ids[i]), *o = obj(ids[i]);
        d[2] = 0; d[3] = maxv[i]; d[4] = defv[i];
        d[10] = (u32)long_names[i]; d[12] = (u32)short_names[i];
        if (proto_from[i]) o[1] = obj(proto_from[i])[1];
        /* comp_init already gives THR..MUP the live DRIVE graphic. */
        if (i >= 4u) copy4(o + 9, obj(gfx_from[i]) + 9);
        if (style_from[i]) copy4(o + 17, obj(style_from[i]) + 17);
        FX_SLOTS[i] = ids[i];
    }
    owned = 1;
}

s32 comp_active_context(void)
{
    u32 project = PROJECT;
    if (!project || ACTIVE_TRACK(project + 48u) != FX_TRACK) {
        restore();
        return 0;
    }
    claim();
    return 1;
}

void comp_ui_update(void)
{
    (void)comp_active_context();
}
