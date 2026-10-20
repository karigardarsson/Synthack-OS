/* Scoped Beat Repeat UI ownership for Syntakt OS 1.41. */
typedef unsigned int u32;
typedef int s32;

#define DATA __attribute__((section(".data")))
#define PROJECT (*(u32 * volatile const)0x444E13F4u)
#define ACTIVE_TRACK ((s32 (*)(u32))0x4001FF74u)
#define FX_TRACK 12
#define DESC_BASE 0x4022D59Cu
#define OBJS_BASE 0x41B9FA24u
#define TRIG_SLOTS ((u32 *)0x41B9F924u)
#define NO_STYLE 0x41B9FA68u
#define RPT1 269u
#define RPT2 124u

#ifndef BR_PROTO
#error BR_PROTO must be supplied by the generator
#endif
#ifndef BR_NAME1_S
#error Beat Repeat name addresses must be supplied by the generator
#endif

static const u32 ids[2] = {RPT1, RPT2};
static const u32 defaults[2] = {0, 0x100};
static const char *const long_names[2] = {
    (const char *)BR_NAME1_L, (const char *)BR_NAME2_L};
static const char *const short_names[2] = {
    (const char *)BR_NAME1_S, (const char *)BR_NAME2_S};

static u32 saved_desc[2][5] DATA = {{0}};
static u32 saved_obj[2][4] DATA = {{0}};
static u32 saved_slots[2] DATA = {0};
static u32 captured DATA = 0;
static u32 owned DATA = 0;

static u32 *desc(u32 id) { return (u32 *)(DESC_BASE + 52u * id); }
static u32 *obj(u32 id) { return (u32 *)(OBJS_BASE + 84u * id); }

static void capture(void)
{
    u32 i;
    if (captured) return;
    for (i = 0; i < 2; i++) {
        u32 *d = desc(ids[i]), *o = obj(ids[i]);
        saved_desc[i][0] = d[2]; saved_desc[i][1] = d[3]; saved_desc[i][2] = d[4];
        saved_desc[i][3] = d[10]; saved_desc[i][4] = d[12];
        saved_obj[i][0] = o[0]; saved_obj[i][1] = o[5];
        saved_obj[i][2] = o[9]; saved_obj[i][3] = o[17];
        saved_slots[i] = TRIG_SLOTS[i];
    }
    captured = 1;
}

static void restore(void)
{
    u32 i;
    if (!owned) return;
    for (i = 0; i < 2; i++) {
        u32 *d = desc(ids[i]), *o = obj(ids[i]);
        d[2] = saved_desc[i][0]; d[3] = saved_desc[i][1]; d[4] = saved_desc[i][2];
        d[10] = saved_desc[i][3]; d[12] = saved_desc[i][4];
        o[0] = saved_obj[i][0]; o[5] = saved_obj[i][1];
        o[9] = saved_obj[i][2]; o[17] = saved_obj[i][3];
        TRIG_SLOTS[i] = saved_slots[i];
    }
    owned = 0;
}

static void claim(void)
{
    u32 i;
    if (owned) return;
    capture();
    for (i = 0; i < 2; i++) {
        u32 *d = desc(ids[i]), *o = obj(ids[i]);
        d[2] = 0; d[3] = 0x500; d[4] = defaults[i];
        d[10] = (u32)long_names[i]; d[12] = (u32)short_names[i];
        o[0] = 0; o[5] = BR_PROTO; o[9] = BR_GFX_PROTO; o[17] = NO_STYLE;
        TRIG_SLOTS[i] = ids[i];
    }
    owned = 1;
}

s32 br_active_context(void)
{
    u32 project = PROJECT;
    if (!project || ACTIVE_TRACK(project + 48u) != FX_TRACK) {
        restore();
        return 0;
    }
    claim();
    return 1;
}
