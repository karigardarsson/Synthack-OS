/* beat-repeat: ripetizione dal sequencer (Syntakt OS 1.41).
 *
 * Il gestore del tick del sequencer (0x4008C924) fa avanzare per ogni traccia t (0..12) l'indice di step
 * 0x43BD73FC + t, con ritorno a capo sulla lunghezza. Alla fine dell'iterazione di ogni traccia
 * (0x4008D152) br_step_hook chiama br_step: mentre la ripetizione e' attiva lo step torna nel segmento
 * di L step allineato alla griglia e si tiene la posizione "reale", ripresa al rilascio.
 * Si ripetono gli step (note e p-lock), quindi anche le tracce analogiche.
 *
 * Interfaccia: RPT1/RPT2 reuse MIDI ids 269 and 124 only in the FX TRIG context.
 * A scoped helper restores the MIDI properties outside that context; the controls show text ("1/16").
 * With the FX track active, hold retrig keys 13 (RPT1) or 14 (RPT2):
 * - pressione: ramo dei tasti 13-16 di KeyboardView::consumeKeyEvent (0x4002EA92), dopo i controlli
 *   di modo dell'OS; sulle altre tracce e con i tasti 15-16 resta il retrig originale;
 * - rilascio: anche dal dispatcher degli eventi (0x4000B420), cosi' vale pure dopo un cambio di traccia.
 * I rate si salvano col kit del pattern (*0x800030BC), nella parola dell'id interno 0x37 che l'OS non usa
 * (byte basso RPT1, alto RPT2, XOR i default: kit vecchi = 1/16 e 1/8); senza kit, in RAM.
 */

typedef unsigned int u32;
typedef int s32;

#define N_TRACKS  13
#define UI_ROOT   (*(char *const volatile *)0x444E1334u)   /* ridisegno: byte +96 */
#define PAT_MODE  136057                                    /* pattern: modo della lunghezza (0 = unica) */
#define PAT_LEN   136052                                    /* pattern: lunghezza (parola) */
#define TRK_LEN   969                                       /* traccia: lunghezza propria (parola) */
#define ID_RPT2   124
#define KEY_13    36                                        /* codici dei tasti di trig 1..16: 24..39 */
#define FX_TRACK  12
#define EV_DOWN   1u                                        /* evento: bit 0 premuto */
#define ACTIVE_TRACK ((s32 (*)(u32))0x4001FF74u)            /* traccia attiva (selettore della vista) */
#define DRAW_TEXT ((void (*)(void *, const void *, s32, s32, s32, s32, const char *, const char *, ...)) \
                   0x400F8C18u)                             /* (ctx, font, x, y, centrato, 0, sagoma, fmt, ...) */
#define FONT      ((const void *)0x402A91C0u)               /* 4x6 */
#define KIT       (*(unsigned char *const volatile *)0x800030BCu)   /* kit del pattern attivo */
#define KIT_RPT   (2 * 0x37)                                /* parola libera (filtro FX, dopo FPAN) */

#define DATA __attribute__((section(".data")))

static const unsigned char rpt_steps[6] = {1, 2, 3, 4, 8, 16};
static const char rpt_text[6][5] = {"1/16", "1/8", "3/16", "1/4", "1/2", "1BAR"};

unsigned char br_rate[2] DATA = {0, 0};          /* senza kit: parola {RPT2 ^ 1, RPT1} */
unsigned char br_held DATA = 0;                  /* bit r: tasto di RPTr tenuto */
unsigned char br_last DATA = 0;                  /* ultimo premuto */
static unsigned char key[2] DATA = {0xFF, 0xFF}; /* codice del tasto tenuto */
static unsigned char last[N_TRACKS] DATA = {0};  /* ultimo step visto */
static unsigned char real[N_TRACKS] DATA = {0};  /* step reale (senza ripetizione) */
static unsigned char anchor[N_TRACKS] DATA = {0};
static unsigned char k[N_TRACKS] DATA = {0};     /* posizione nel segmento */
static unsigned char seg[N_TRACKS] DATA = {0};   /* lunghezza del segmento in corso, 0 = inattivo */

static s32 word(const unsigned char *p)          /* parola con segno, anche non allineata */
{
    return (short)((p[0] << 8) | p[1]);
}

static volatile unsigned char *rpt_word(void)
{
    unsigned char *k = KIT;
    return k ? k + KIT_RPT : br_rate;
}

static u32 rate(u32 r)                           /* posizione 0..5 di RPT1 (r = 0) o RPT2 (r = 1) */
{
    u32 v = rpt_word()[r ? 0 : 1] ^ r;
    return v > 5 ? 5 : v;
}

static u32 cur_len(void)                         /* L in step, 0 = nessuna ripetizione */
{
    u32 h = br_held, r = br_last;

    if (!h)
        return 0;
    if (!((h >> r) & 1))
        r ^= 1;
    return rpt_steps[rate(r)];
}

void br_step(u32 next_track, unsigned char *step, const unsigned char *pat, const unsigned char *trk)
{
    u32 t = next_track - 1, L = cur_len(), p;
    s32 len = pat[PAT_MODE] ? word(trk + TRK_LEN) : word(pat + PAT_LEN);
    unsigned char cur = *step;

    if (t >= N_TRACKS || len <= 0)
        return;
    if (!L) {                                   /* rilascio: si riprende dove si sarebbe */
        if (seg[t]) {
            seg[t] = 0;
            *step = real[t];
        }
        last[t] = *step;
        return;
    }
    if (cur == last[t])                         /* nessun avanzamento in questo tick */
        return;
    if (seg[t] == L) {                          /* dentro il segmento */
        real[t] = (unsigned char)(real[t] + 1u >= (u32)len ? 0 : real[t] + 1);
        k[t]++;
    } else {                                    /* inizio o cambio di rate: segmento che contiene */
        if (seg[t]) {                           /* lo step reale appena suonato */
            p = real[t];
            real[t] = (unsigned char)(p + 1 >= (u32)len ? 0 : p + 1);
        } else {
            p = last[t];
            real[t] = cur;
        }
        seg[t] = (unsigned char)L;
        anchor[t] = (unsigned char)(p - p % L);
        k[t] = (unsigned char)(p - anchor[t] + 1);
    }
    {
        s32 v = anchor[t] + k[t] % L;
        *step = (unsigned char)(v >= len ? v % len : v);
    }
    last[t] = *step;
}

/* tasti 13-16 di KeyboardView: -1 = non nostro (prosegue l'originale), 1 = gestito */
s32 br_kbd(const char *view, const unsigned char *ev, u32 code)
{
    u32 r = code - KEY_13;

    if (r > 1 || ACTIVE_TRACK(*(const u32 *)(view + 160)) != FX_TRACK)
        return -1;
    if (*(const u32 *)(ev + 16) & EV_DOWN) {
        key[r] = (unsigned char)code;
        br_last = (unsigned char)r;
        br_held |= (unsigned char)(1u << r);
    } else
        br_held &= (unsigned char)~(1u << r);
    return 1;
}

void br_ev(void *root, const unsigned char *ev)  /* ogni evento di tasto: rilascio ovunque */
{
    u32 code = *(const u32 *)(ev + 12), fl = *(const u32 *)(ev + 16), r;

    (void)root;
    if (fl & EV_DOWN)
        return;
    for (r = 0; r < 2; r++)
        if (key[r] == code)
            br_held &= (unsigned char)~(1u << r);
}

/* RPT1 e RPT2 (vparams): lettura e scrittura con lo stack delle funzioni dell'OS */
s32 br_get(void *obj, s32 id)
{
    (void)obj;
    return (s32)rate(id == ID_RPT2) << 8;
}

s32 br_set(void *obj, s32 id, s32 value)
{
    char *ui = UI_ROOT;
    (void)obj;
    value = (value + 0x80) >> 8;
    value = value < 0 ? 0 : value > 5 ? 5 : value;
    rpt_word()[id == ID_RPT2 ? 0 : 1] = (unsigned char)(value ^ (id == ID_RPT2));
    if (ui)
        ui[96] = 1;                             /* ridisegno subito, come i setter originali */
    return 0;
}

static const char *text(s32 value)
{
    value = (value + 0x80) >> 8;
    return rpt_text[value < 0 ? 0 : value > 5 ? 5 : value];
}

/* formattatore del testo (+20, std::function come in readable-values) */
void br_invoke(const void *fn, s32 value, char *buf)
{
    const char *s = text(value);
    (void)fn;
    while ((*buf++ = *s++))
        ;
}

/* grafica della casella (+36): la divisione come testo, centrata come le destinazioni degli LFO */
void br_gfx(const void *fn, s32 value, void *ctx, s32 x, s32 y)
{
    (void)fn;
    DRAW_TEXT(ctx, FONT, x + 8, y + 5, 1, 0, "XXXX", "%s", text(value));
}

int br_mgr(void *dst, const void *src, int op)
{
    (void)dst;
    (void)src;
    (void)op;
    return 0;
}

const void *const br_proto[4] __attribute__((aligned(4))) = {0, 0, (const void *)br_mgr, (const void *)br_invoke};
const void *const br_gfx_proto[4] __attribute__((aligned(4))) = {0, 0, (const void *)br_mgr, (const void *)br_gfx};

const char br_name1_s[] = "RPT1";
const char br_name2_s[] = "RPT2";
const char br_name1_l[] = "Beat Repeat 1";
const char br_name2_l[] = "Beat Repeat 2";

/* trampolini */
__asm__(
    "        .globl  br_step_hook\n"
    "br_step_hook:\n"                           /* fine dell'iterazione di una traccia (0x4008D152) */
    "        lea     -16(%sp),%sp\n"
    "        movem.l %d0-%d1/%a0-%a1,(%sp)\n"
    "        move.l  %a3,-(%sp)\n"              /* dati della traccia */
    "        move.l  %a2,-(%sp)\n"              /* pattern */
    "        move.l  %a4,-(%sp)\n"              /* &step[traccia] */
    "        move.l  %d2,-(%sp)\n"              /* traccia + 1 */
    "        jsr     br_step\n"
    "        lea     16(%sp),%sp\n"
    "        movem.l (%sp),%d0-%d1/%a0-%a1\n"
    "        lea     16(%sp),%sp\n"
    "        addq.l  #1,%d3\n"                  /* istruzioni sostituite */
    "        addq.l  #1,%a6\n"
    "        addq.l  #1,%a5\n"
    "        rts\n"
    "        .globl  br_kbd_hook\n"
    "br_kbd_hook:\n"                            /* tasti 13-16 (0x4002EA92): d0 = codice, d2 = evento, */
    "        move.l  %d0,-(%sp)\n"              /* a2 = vista */
    "        move.l  %d0,-(%sp)\n"
    "        move.l  %d2,-(%sp)\n"
    "        move.l  %a2,-(%sp)\n"
    "        jsr     br_kbd\n"
    "        lea     12(%sp),%sp\n"
    "        tst.l   %d0\n"
    "        bmi.s   1f\n"
    "        addq.l  #4,%sp\n"
    "        jmp     0x4002E954\n"              /* gestito: d3 = 1, uscita */
    "1:      move.l  (%sp)+,%d0\n"
    "        moveq   #35,%d1\n"                 /* istruzioni sostituite */
    "        cmp.l   %d0,%d1\n"
    "        bge.s   2f\n"
    "        jmp     0x4002EA9A\n"
    "2:      jmp     0x4002EBA6\n"
    "        .globl  br_ev_hook\n"
    "br_ev_hook:\n"                             /* al posto di jsr 0x4000839e (dispatcher) */
    "        move.l  8(%sp),-(%sp)\n"
    "        move.l  8(%sp),-(%sp)\n"
    "        jsr     br_ev\n"
    "        addq.l  #8,%sp\n"
    "        jmp     0x4000839E\n"
    "        .globl  br_page_stub\n"
    "br_page_stub:\n"                           /* al posto di clr.l 0x41B9F928: caselle 1 e 2 */
    "        move.l  %d0,-(%sp)\n"
    "        move.l  #269,%d0\n"
    "        move.l  %d0,0x41B9F924\n"
    "        moveq   #124,%d0\n"
    "        move.l  %d0,0x41B9F928\n"
    "        move.l  (%sp)+,%d0\n"
    "        rts\n");
