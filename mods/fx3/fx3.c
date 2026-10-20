/* fx3: terza mandata effetti (Syntakt OS 1.41): chorus, flanger, phaser, crusher.
 *
 * Audio (funzione di mix a blocchi 0x4008F1CA, 32 campioni a 48 kHz):
 * - nel ciclo per traccia (0x4008F3A0) fx3_trk_hook prende i guadagni sinistro/destro della traccia
 *   (livello e pan) e il valore di SND3 (parola +106 del motore = id 72, salvato per traccia) e ne
 *   ricava il bersaglio mono della mandata (a meta': si sommano coppie di campioni), come l'OS fa per
 *   DEL e REV, e segnala quando un bersaglio cambia (fx3_moving): a regime la rampa non gira;
 * - dopo le somme del master (0x4008FB04) fx3_run somma le tracce nel bus 3 a 24 kHz (coppie di campioni
 *   mediate, EMAC: un passaggio per traccia se mandano una o due tracce, se no uno solo per tutte), lo
 *   passa all'effetto (a 24 kHz) e aggiunge il ritorno, scalato da VOL e riportato a 48 kHz per
 *   interpolazione lineare, al bus diretto (0x8000DAD0), con la convenzione di segno dell'OS;
 * - prima del delay del blocco seguente (0x4008F828) fx3_dsnd aggiunge l'uscita dell'effetto, scalata
 *   dalla mandata DEL, al bus d'ingresso del delay (0x8000DBD0): un blocco di ritardo (0,67 ms).
 * Il carico conta: l'OS usa gia' quasi tutta la CPU e l'interfaccia vive del resto. Senza mandate, con
 * VOL e DEL a zero o con gli ingressi muti (sequencer fermo) e la coda esaurita resta solo la somma o
 * nemmeno quella; i cicli caldi sono in assembly. Istruzioni per blocco in tests/test_fx3.py.
 *
 * Effetti (TYPE): CHOR e FLNG = una linea mono con due prese (L/R) modulate; PHSR = 4 celle allpass,
 * uscita destra complementare (WID); CRSH = tenuta del campione, bit ridotti e drive (mono).
 *
 * Interfaccia: pagina 2 del tab REVERB (pagina 25 dell'OS, "OB8", inutilizzata) con TYPE e 7 controlli:
 * id nascosti delle tracce MIDI (246..253) tramite mods/vparams. Nomi, testi e icone (prese da parametri
 * dell'OS simili) cambiano col tipo; il crusher lascia vuote le caselle che non usa. La
 * classe dei tab DELAY/REVERB disegna le caselle 5-6 come filtro: per la pagina 25 si usa il disegno
 * generico a 8 caselle (fx3_draw_hook). SND3 e la mandata DEL usano la grafica della mandata del delay.
 *
 * Salvataggio: nel kit del pattern (*0x800030BC = parametri della traccia FX, una parola per id interno),
 * 4 parole che l'OS non usa: id interni 0, 0x1A (tra delay e riverbero), 0x38 (id 144, "Delay Time"
 * dell'amp FX, nascosto) e 0x46 (dopo l'amp FX). Un byte per parametro, XOR il default: kit vecchi
 * (parole a zero) = valori di default.
 */

typedef unsigned int u32;
typedef int s32;
typedef short s16;
typedef unsigned short u16;

#include "fx3_tables.h"

#define DATA __attribute__((section(".data")))
#define H         16                                       /* campioni per blocco a 24 kHz */
#define DL        1024                                     /* linea a 24 kHz: 42 ms (TIME + DEP <= 38 ms) */
#define DL_M      ((s16 *)(MODAREA_RAM + 0xE000u))         /* linea mono + copia a +DL (area mod azzerata) */
#define MAXD      (8 << 8)                                 /* variazione massima del ritardo per blocco (Q8) */
#define SRC_D     0x80003D50u                              /* tracce digitali, 32 campioni a passo 128 B */
#define SRC_A     0x80003950u                              /* tracce analogiche (canali 0..3) */
#define OUT_A     ((s32 *)0x8000DAD0u)                     /* bus d'uscita, L/R alternati */
#define DLY_IN    ((s32 *)0x8000DBD0u)                     /* bus d'ingresso del delay, L/R alternati */
#define KIT       (*(char *const volatile *)0x800030BCu)   /* kit del pattern attivo */
#define LOUD      (10 << 16)                               /* ingresso udibile: oltre 10/32768 (-70 dB) */
#define UI_ROOT   (*(char *const volatile *)0x444E1334u)
#define PROJECT   (*(const u32 *const volatile *)0x444E13F4u)
#define ACTIVE_TRACK ((s32 (*)(u32))0x4001FF74u)
#define FX_TRACK  12
#define DESC      0x4022D59Cu
#define NO_STYLE  0x41B9FA68u
#define DRAW_TEXT ((void (*)(void *, const void *, s32, s32, s32, s32, const char *, const char *, ...))                    0x400F8C18u)                            /* (ctx, font, x, y, centrato, 0, sagoma, fmt, ...) */
#define FONT      ((const void *)0x402A91C0u)              /* 4x6 */

enum { P_TYPE, P_SPD, P_DEP, P_TIME, P_FDBK, P_WID, P_DSND, P_VOL, NP };
enum { CHOR, FLNG, PHSR, CRSH, NT };
static const unsigned short ids[NP] = {246, 247, 248, 250, 251, 252, 249, 253};
static const unsigned char maxv[NP] = {NT - 1, 127, 127, 127, 127, 127, 127, 127};
static const unsigned char defv[NP] = {0, 60, 64, 64, 0, 64, 0, 100};
static const unsigned char woff[4] = {0, 2 * 0x1A, 2 * 0x38, 2 * 0x46}; /* parole nel kit */
unsigned char fx3_p[NP] DATA = {0, 60, 64, 64, 0, 64, 0, 100};
static u16 fallback[0x47] DATA = {0};                     /* nessun kit (ancora): valori in RAM */
static u32 seen[2] DATA = {1, 1};                         /* ultime parole lette, a coppie (1: rilettura) */

s32 fx3_tgt[16] DATA = {0};                              /* bersagli mono (meta'): 0..7 digitali, 8..11 analogiche */
s32 fx3_cur[16] DATA = {0};                              /* guadagni del blocco (levigati verso i bersagli) */
s32 fx3_moving DATA = 0;                                  /* != 0: un bersaglio e' cambiato */
static u32 ramp DATA = 0;                                 /* != 0: un guadagno non ha ancora raggiunto il bersaglio */
static u32 live DATA = 0;                                 /* tracce con guadagno (bit 0..11) */
s32 fx3_bus[H] DATA = {0};                               /* bus 3 mono a 24 kHz */
s32 fx3_wet[2 * H] DATA = {0};                           /* uscita dell'effetto (scala 16 bit), L/R alternati */
s32 fx3_idle DATA = 1;                                    /* 1 = niente da fare (e fx3_wet non valido) */
static s32 ret_h[2] DATA = {0, 0}, dly_h[2] DATA = {0, 0}; /* ultimo mezzo campione L/R per l'interpolazione */
static u32 quiet DATA = 0;                                /* blocchi consecutivi senza ingresso ne' coda */
static u32 wpos DATA = 0, phase DATA = 0, dpos[2] DATA = {0, 0};
static u32 dsp_type DATA = 0;                             /* tipo per cui e' preparato lo stato dell'effetto */

/* ---- salvataggio nel kit */
static char *kit(void)
{
    char *k = KIT;
    return k ? k : (char *)fallback;
}

static u32 word(const char *k, u32 j)
{
    return *(const volatile u16 *)(k + woff[j]);
}

static u32 decode(u32 w, u32 i)                          /* byte del parametro i dalla sua parola */
{
    u32 v = ((i & 1 ? w : w >> 8) & 0xFF) ^ defv[i];
    return v > maxv[i] ? maxv[i] : v;
}

/* nomi e testi della pagina secondo il tipo (stringhe in RAM: i descrittori puntano qui) */
#include "fx3_names.h"
char fx3_page_s[4] DATA = "FX3";
char fx3_page_l[12] DATA = "Chorus";
static const char *const n_s[NT][5] = {{"SPD", "DEP", "TIME", "FDBK", "WID"},
                                       {"SPD", "DEP", "TIME", "FDBK", "WID"},
                                       {"SPD", "DEP", "FREQ", "FDBK", "WID"},
                                       {"SRR", "BITS", "DRV", "-", "-"}};
static const char *const n_l[NT][5] = {
    {"Chorus Speed", "Chorus Depth", "Chorus Delay", "Chorus Feedback", "Chorus Width"},
    {"Flanger Speed", "Flanger Depth", "Flanger Delay", "Flanger Feedback", "Flanger Width"},
    {"Phaser Speed", "Phaser Depth", "Phaser Frequency", "Phaser Feedback", "Phaser Width"},
    {"Crusher Rate", "Crusher Bits", "Crusher Drive", "-", "-"}};
static const char *const t_s[NT] = {"CHOR", "FLNG", "PHSR", "CRSH"};
static const char *const t_l[NT] = {"Chorus", "Flanger", "Phaser", "Crusher"};
static char *const name_s[5] = {fx3_n1_s, fx3_n2_s, fx3_n3_s, fx3_n4_s, fx3_n5_s};
static char *const name_l[5] = {fx3_n1_l, fx3_n2_l, fx3_n3_l, fx3_n4_l, fx3_n5_l};
static char *const desc_s[NP] = {fx3_n0_s, fx3_n1_s, fx3_n2_s, fx3_n3_s,
                                  fx3_n4_s, fx3_n5_s, fx3_n6_s, fx3_n7_s};
static char *const desc_l[NP] = {fx3_n0_l, fx3_n1_l, fx3_n2_l, fx3_n3_l,
                                  fx3_n4_l, fx3_n5_l, fx3_n6_l, fx3_n7_l};
static u32 named DATA = 0xFF;                             /* tipo di nomi, icone e caselle (0xFF: da fare) */

/* icone: per ogni casella la coppia (+36 grafica, +68 stile) di un parametro dell'OS dal significato
 * simile. Dei prototipi (std::function costruite all'avvio) si prende solo l'invoker (+12): nessuno di
 * quelli scelti usa i dati del functor; il gestore e' fx3_mgr (nessuna copia o distruzione sullo heap
 * condiviso col prototipo). 0 = vuoto. */
#define OBJ(id)   ((u32 *)(0x41B9FA24u + 84u * (id)))     /* oggetto del parametro */
#define SLOTS     ((u32 *)0x41B9F81Cu)                     /* caselle della pagina 25 */
enum {
    G_DEF = 0x41B9DCD0, G_LFO = 0x41B9DC70, G_SPD = 0x41B9D6B0, G_MOD = 0x41B9D730, G_STIM = 0x41B9D7D0,
    G_SDEP = 0x41B9D7E0, G_BAL = 0x41B9D740, G_TONE = 0x41B9D760, G_NCOL = 0x41B9D780, G_TICK = 0x41B9D830,
    G_OVER = 0x41B9DCB0, S_KNOB = 0x41B9D670, S_660 = 0x41B9D660, S_FDBK = 0x41B9D5E0
};
static const u32 look[NT][5][2] = {
    {{G_SPD, 0}, {G_MOD, 0}, {G_STIM, 0}, {G_DEF, S_FDBK}, {G_BAL, S_660}},     /* SPD 467, MOD 176, STIM 274, FDBK 109, BAL 216 */
    {{G_SPD, 0}, {G_SDEP, 0}, {G_STIM, 0}, {G_LFO, S_660}, {G_BAL, S_660}},     /* SDEP 283, LFO DEP 94 (bipolare) */
    {{G_SPD, 0}, {G_SDEP, 0}, {G_TONE, S_660}, {G_LFO, S_660}, {G_BAL, S_660}}, /* TONE 394 */
    {{G_NCOL, S_660}, {G_TICK, 0}, {G_OVER, S_KNOB}, {0, 0}, {0, 0}}};          /* NCOL 385, TICK 277, OVER 164 */
static const unsigned short knob_id[5] = {247, 248, 250, 251, 252};

static void put(char *buf, const char *s)
{
    while ((*buf++ = *s++))
        ;
}

int fx3_mgr(void *dst, const void *src, int op);

static void graphic(u32 *dst, u32 proto)
{
    dst[0] = dst[1] = 0;
    dst[2] = proto ? (u32)fx3_mgr : 0;
    dst[3] = proto ? ((const u32 *)proto)[3] : 0;
}

/*
 * IDs 246..253 are genuine MIDI-source descriptors on Syntakt. FX3 borrows
 * them only while the FX track owns the Reverb view, then restores every field
 * it changed. Keeping this transition here avoids a global descriptor alias.
 */
extern const void *const fx3_proto_type[4];
extern const void *const fx3_proto_spd[4];
extern const void *const fx3_proto_dep[4];
extern const void *const fx3_proto_del[4];
extern const void *const fx3_proto_fdbk[4];
extern const void *const fx3_proto_wid[4];
extern const void *const fx3_proto_vol[4];
extern const void *const fx3_proto_type_gfx[4];
static const void *const *const fx3_fmt_proto[NP] = {
    fx3_proto_type, fx3_proto_spd, fx3_proto_dep, fx3_proto_del,
    fx3_proto_fdbk, fx3_proto_wid, fx3_proto_vol, fx3_proto_vol
};
static void dress(void);
static u32 fx3_saved_obj[NP][14] DATA = {{0}};
static u32 fx3_saved_desc[NP][5] DATA = {{0}};
static u32 fx3_saved_slots[9] DATA = {0};
static u32 fx3_snapshot DATA = 0;
static u32 fx3_ui_owned DATA = 0;

static void fx3_capture_ui(void)
{
    u32 i, j;
    if (fx3_snapshot)
        return;
    for (i = 0; i < NP; i++) {
        u32 *d = (u32 *)(DESC + 52u * ids[i]);
        u32 *o = OBJ(ids[i]), *saved = fx3_saved_obj[i];
        u32 *saved_d = fx3_saved_desc[i];
        saved_d[0] = d[2];
        saved_d[1] = d[3];
        saved_d[2] = d[4];
        saved_d[3] = d[10];
        saved_d[4] = d[12];
        saved[0] = o[0];
        saved[1] = o[1];
        for (j = 0; j < 4; j++) {
            saved[2 + j] = o[5 + j];
            saved[6 + j] = o[9 + j];
            saved[10 + j] = o[17 + j];
        }
    }
    for (i = 0; i < 9; i++)
        fx3_saved_slots[i] = SLOTS[i];
    fx3_snapshot = 1;
}

static void fx3_restore_ui(void)
{
    u32 i, j;
    if (!fx3_ui_owned)
        return;
    for (i = 0; i < NP; i++) {
        u32 *d = (u32 *)(DESC + 52u * ids[i]);
        u32 *o = OBJ(ids[i]), *saved = fx3_saved_obj[i];
        u32 *saved_d = fx3_saved_desc[i];
        d[2] = saved_d[0];
        d[3] = saved_d[1];
        d[4] = saved_d[2];
        d[10] = saved_d[3];
        d[12] = saved_d[4];
        o[0] = saved[0];
        o[1] = saved[1];
        for (j = 0; j < 4; j++) {
            o[5 + j] = saved[2 + j];
            o[9 + j] = saved[6 + j];
            o[17 + j] = saved[10 + j];
        }
    }
    for (i = 0; i < 9; i++)
        SLOTS[i] = fx3_saved_slots[i];
    put(fx3_page_s, "OB8");
    put(fx3_page_l, "Outbox 8");
    named = 0xFF;
    fx3_ui_owned = 0;
}

static void fx3_claim_ui(void)
{
    u32 i;
    const u32 *donor;

    if (fx3_ui_owned)
        return;
    fx3_capture_ui();
    donor = OBJ(250);
    for (i = 0; i < NP; i++) {
        u32 *d = (u32 *)(DESC + 52u * ids[i]);
        u32 *o = OBJ(ids[i]);
        d[2] = 0;
        d[3] = (u32)maxv[i] << 8;
        d[4] = (u32)defv[i] << 8;
        d[10] = (u32)desc_l[i];
        d[12] = (u32)desc_s[i];
        o[0] = donor[0];
        o[1] = donor[1];
        graphic(o + 5, (u32)fx3_fmt_proto[i]);
    }
    graphic(OBJ(246) + 9, (u32)fx3_proto_type_gfx);
    graphic(OBJ(246) + 17, NO_STYLE);
    for (i = 0; i < NP; i++)
        SLOTS[i] = ids[i];
    SLOTS[NP] = 0;
    named = 0xFF;
    fx3_ui_owned = 1;
    dress();
}

s32 fx3_active_context(void)
{
    u32 project = (u32)PROJECT;

    if (!project || ACTIVE_TRACK(project + 48) != FX_TRACK) {
        fx3_restore_ui();
        return 0;
    }
    fx3_claim_ui();
    return 1;
}

/* nomi, icone e caselle secondo il tipo. Solo nel contesto dell'interfaccia (formattatori, grafica,
 * scrittura dei parametri): copiare una std::function mentre l'interfaccia la sta chiamando
 * porterebbe a saltare a un indirizzo sbagliato; l'interrupt audio aggiorna soltanto fx3_p. */
static void dress(void)
{
    char *ui = UI_ROOT;
    u32 t = fx3_p[P_TYPE], i;

    if (t == named)
        return;
    named = t;
    for (i = 0; i < 5; i++) {
        put(name_s[i], n_s[t][i]);
        put(name_l[i], n_l[t][i]);
        graphic(OBJ(knob_id[i]) + 9, look[t][i][0]);
        graphic(OBJ(knob_id[i]) + 17, look[t][i][1]);
    }
    SLOTS[4] = t == CRSH ? 0 : 251;                        /* il crusher non usa FDBK e WID: */
    SLOTS[5] = t == CRSH ? 0 : 252;                        /* caselle vuote */
    put(fx3_page_l, t_l[t]);
    if (ui)
        ui[96] = 1;
}

/* a ogni blocco: parametri dal kit (cambia col pattern), solo se le parole sono cambiate */
static void sync(void)
{
    const char *k = kit();
    u32 lo = word(k, 0) << 16 | word(k, 1), hi = word(k, 2) << 16 | word(k, 3), i;

    if (lo == seen[0] && hi == seen[1])
        return;
    seen[0] = lo;
    seen[1] = hi;
    for (i = 0; i < NP; i++)
        fx3_p[i] = (unsigned char)decode(word(k, i >> 1), i);
}

/* ---- effetti */
static s32 lfo(u32 ph)                                    /* seno unipolare 0..32767 */
{
    u32 i = ph >> 24, f = (ph >> 8) & 0xFFFF;
    s32 a = SIN_T[i], b = SIN_T[i + 1];
    return (a + (((b - a) * (s32)(f >> 1)) >> 15) + 32768) >> 1;
}

static u32 inc(const u16 *rate)                           /* passo di fase per blocco da mHz */
{
    return ((u32)rate[fx3_p[P_SPD]] * 183252u >> 10) * H;  /* 2^32 / 24000 / 1000 = 178.96 */
}

static u32 q8(u32 us)                                     /* microsecondi -> campioni a 24 kHz, Q8 */
{
    return us * 6144u / 1000;                             /* 30 ms: 1.8e8, nessun traboccamento */
}

static s32 bip(u32 v, s32 max)                           /* 0..127, centro 64 -> -max..max */
{
    s32 x = ((s32)v - 64) * max / 63;
    return x > max ? max : x < -max ? -max : x;
}

static const s32 zero[H] = {0};

/* CHOR / FLNG: ciclo in assembly (fx3_cho, sotto): 16 campioni, due prese interpolate dalla linea
 * doppia, retroazione mono saturata a 16 bit; due varianti (con/senza retroazione). Le posizioni partono
 * sotto DL e in un blocco avanzano di 16 +- MAXD campioni: le letture restano nella copia, senza ritorno
 * a capo. La retroazione sta subito prima della linea (muls.l non accetta indirizzi assoluti). */
struct cho { s16 *line; const s32 *in; s32 *wet; u32 pl, pr, il, ir, w; s32 yl, yr; };
#define CHO_FB    (*(volatile s32 *)((char *)DL_M - 4))
void fx3_cho(struct cho *c);
void fx3_sum(s32 *dst, const s32 *g, u32 which);         /* dst[n] = -sum g[k] (x_k[2n] + x_k[2n+1]) */
void fx3_sum1(s32 *dst, u32 src, s32 g, u32 add);         /* una traccia: dst[n] (+)= -g (x[2n] + x[2n+1]) */
void fx3_ret(const s32 *wet, s32 gain, s32 *a, s32 *h);  /* a -= 2 * wet * gain a 48 kHz (saturato) */

static u32 glide(u32 to, u32 from)                       /* TIME girato di colpo: scivola */
{
    s32 d = (s32)(to - from);
    return d > MAXD ? from + MAXD : d < -MAXD ? from - MAXD : to;
}

/* una linea mono, due prese (L/R) modulate da un LFO calcolato a inizio e fine blocco e interpolato
 * linearmente (le posizioni di lettura avanzano di 1 - pendenza a campione). Ritorna 1 se la coda e'
 * (quasi) muta. */
static u32 chorus(const s32 *in, u32 fl)
{
    struct cho c;
    u32 base = q8((fl ? TIME_F : TIME_C)[fx3_p[P_TIME]]), dep = q8((fl ? DEP_F : DEP_C)[fx3_p[P_DEP]]);
    u32 off = (u32)fx3_p[P_WID] * 0x01020408u;             /* 0..180 gradi */
    u32 end = phase + inc(fl ? RATE_F : RATE_C);
    u32 el = glide(base + ((dep * (u32)lfo(end)) >> 15), dpos[0]);
    u32 er = glide(base + ((dep * (u32)lfo(end + off)) >> 15), dpos[1]);

    c.line = DL_M;
    c.in = in;
    c.wet = fx3_wet;
    c.pl = ((wpos << 8) - dpos[0] - 256) & ((DL << 8) - 1);
    c.pr = ((wpos << 8) - dpos[1] - 256) & ((DL << 8) - 1);
    c.il = 256 - (u32)(((s32)(el - dpos[0])) >> 4);
    c.ir = 256 - (u32)(((s32)(er - dpos[1])) >> 4);
    c.w = wpos;
    CHO_FB = fl ? bip(fx3_p[P_FDBK], 31130) : 29490 * (s32)fx3_p[P_FDBK] / 127; /* 95 % / 90 % */
    fx3_cho(&c);
    wpos = c.w & (DL - 1);                                 /* multiplo di H: nel blocco non torna a capo */
    phase = end;
    dpos[0] = el;
    dpos[1] = er;
    /* coda muta sotto 10/32768 (-70 dB): con la retroazione l'arrotondamento puo' lasciare un residuo
     * costante di qualche unita' che non si spegnerebbe mai */
    return (u32)(c.yl + 10) <= 20 && (u32)(c.yr + 10) <= 20;
}

/* PHSR: 4 celle allpass del primo ordine in cascata (coefficiente per blocco, Q12, dalla frequenza
 * spazzata dall'LFO in ottave), retroazione dall'uscita; sinistra = (x + y) / 2, destra = sinistra -
 * WID * y (a WID massimo (x - y) / 2: notch e picchi scambiati). Ciclo in assembly (fx3_phs). */
struct phs { const s32 *in; s32 *wet; s32 a, fb, w; s32 s[5]; };
static struct phs ph DATA;
void fx3_phs(struct phs *p);

static u32 phaser(const s32 *in)
{
    u32 end = phase + inc(RATE_F);
    u32 x = FIDX_P[fx3_p[P_TIME]] + (49152u * fx3_p[P_DEP] / 127 * (u32)lfo(end) >> 15);  /* 0..6 ottave */
    u32 i, f;

    if (x > (PH_N - 2) << 8)
        x = (PH_N - 2) << 8;
    i = x >> 8;
    f = x & 0xFF;
    ph.in = in;
    ph.wet = fx3_wet;
    ph.a = PH_A[i] + (((PH_A[i + 1] - PH_A[i]) * (s32)f) >> 8);
    ph.fb = bip(fx3_p[P_FDBK], 29491);                     /* 90 % */
    ph.w = 16384 * (s32)fx3_p[P_WID] / 127;                /* Q14 */
    fx3_phs(&ph);
    phase = end;
    return (u32)(ph.s[4] + 10) <= 20 && (u32)(fx3_wet[2 * H - 2] + 10) <= 20 && (u32)(fx3_wet[2 * H - 1] + 10) <= 20;
}

/* CRSH: tenuta del campione (24 kHz / 1..32), bit 16..1, drive 0..24 dB con saturazione; mono */
static u32 cr_cnt DATA = 0;
static s32 cr_hold DATA = 0;

static u32 crusher(const s32 *in)
{
    u32 n = 1 + (31 * fx3_p[P_SPD] + 63) / 127, k;
    u32 sh = (15 * fx3_p[P_DEP] + 63) / 127;               /* bit tolti */
    s32 g = DRV_G[fx3_p[P_TIME]], mask = -(1 << sh), *w = fx3_wet;

    for (k = 0; k < H; k++) {
        if (++cr_cnt >= n) {
            s32 x = ((in[k] >> 16) * g) >> 8;
            cr_cnt = 0;
            x = x > 32767 ? 32767 : x < -32768 ? -32768 : x;
            cr_hold = x & mask;
        }
        w[2 * k] = w[2 * k + 1] = cr_hold;
    }
    return (u32)(cr_hold + 10) <= 20;
}

/* nuovo tipo: niente coda del precedente */
static void retype(u32 t)
{
    u32 *l = (u32 *)DL_M, k;

    dsp_type = t;
    for (k = 0; k < DL; k++)                               /* linea e copia: 2 x DL campioni */
        l[k] = 0;
    for (k = 0; k < 5; k++)
        ph.s[k] = 0;
    cr_hold = 0;
    cr_cnt = 0;
}

static void rest(void)
{
    fx3_idle = 1;
    ret_h[0] = ret_h[1] = dly_h[0] = dly_h[1] = 0;
}

/* dopo le somme del master (MACSR impostato dal trampolino): bus 3, effetto e ritorno sul bus diretto
 * (come delay e riverbero con FX Routing spento; il bus 0x8000DFD0 passa dal blocco FX analogico).
 * I guadagni seguono i bersagli di 1/4 a blocco (~2.7 ms) e li raggiungono esatti quando sono vicini. */
void fx3_run(void)
{
    s32 *t = fx3_tgt, *c = fx3_cur;
    s32 vol;
    u32 k, mask = 0, loud = 0, silent;
    const s32 *in;

    sync();
    vol = VOL_Q15[fx3_p[P_VOL]];
    if (!(vol | fx3_p[P_DSND])) {                          /* nessuno ascolta l'uscita */
        rest();
        return;
    }
    if (!(fx3_moving | ramp | live) && quiet > DL / H) {   /* nessuna mandata e coda esaurita */
        rest();
        return;
    }
    if (fx3_moving | ramp) {
        fx3_moving = 0;
        ramp = 0;
        for (k = 0; k < 12; k++) {
            s32 g = c[k];
            if (t[k] != g) {
                s32 d = t[k] - g;                          /* senza l'aggancio un piccolo resto non si */
                g = d > -64 && d < 64 ? t[k] : g + (d >> 2); /* annullerebbe mai: FX3 sempre acceso */
                c[k] = g;
                ramp |= (u32)(t[k] - g);
            }
            if (g)
                mask |= 1u << k;
        }
        live = mask;
    }
    mask = live;
    if (mask) {
        u32 two = mask & (mask - 1);
        if (!(two & (two - 1))) {                          /* una o due tracce: un passaggio ciascuna */
            u32 add = 0;
            do {
                k = 31 - (u32)__builtin_clz(mask);         /* ff1 */
                mask ^= 1u << k;
                fx3_sum1(fx3_bus, k < 8 ? SRC_D + 128 * k : SRC_A + 128 * (k - 8), c[k], add);
                add = 1;
            } while (mask);
            mask = live;
        } else
            fx3_sum(fx3_bus, c, (mask & 0xFF ? 1 : 0) | (mask >> 8 ? 2 : 0));
        for (k = 0; k < H; k++)                            /* ingresso udibile? (tracce ferme: no) */
            if ((u32)(fx3_bus[k] + LOUD) > 2 * LOUD) {
                loud = 1;
                break;
            }
    }
    if (!loud && quiet > DL / H) {                         /* ingresso muto e coda esaurita */
        rest();
        return;
    }
    fx3_idle = 0;
    if (fx3_p[P_TYPE] != dsp_type)
        retype(fx3_p[P_TYPE]);
    in = mask ? fx3_bus : zero;
    switch (dsp_type) {
    case PHSR:
        silent = phaser(in);
        break;
    case CRSH:
        silent = crusher(in);
        break;
    default:
        silent = chorus(in, dsp_type == FLNG);
    }
    quiet = loud || !silent ? 0 : quiet + 1;
    if (vol)
        fx3_ret(fx3_wet, vol, OUT_A, ret_h);
    else
        ret_h[0] = ret_h[1] = 0;
}

/* prima del delay: l'uscita dell'effetto del blocco precedente nel suo bus d'ingresso (che ha la
 * convenzione del bus 3: si somma, quindi guadagno negativo) */
void fx3_dsnd(void)
{
    s32 ds = VOL_Q15[fx3_p[P_DSND]];

    if (ds)
        fx3_ret(fx3_wet, -ds, DLY_IN, dly_h);
    else
        dly_h[0] = dly_h[1] = 0;
}

/* ---- parametri della pagina (vparams): letti e scritti nel kit */
static s32 slot(s32 id)
{
    s32 i;
    for (i = 0; i < NP; i++)
        if (ids[i] == id)
            return i;
    return 0;
}

s32 fx3_get(void *obj, s32 id)
{
    s32 i = slot(id);
    (void)obj;
    return (s32)decode(word(kit(), (u32)i >> 1), (u32)i) << 8;
}

s32 fx3_set(void *obj, s32 id, s32 value)
{
    char *ui = UI_ROOT, *k = kit();
    u32 i = (u32)slot(id), v;
    volatile u16 *w = (volatile u16 *)(k + woff[i >> 1]);
    (void)obj;
    value = (value + 0x80) >> 8;
    v = (u32)(value < 0 ? 0 : value > maxv[i] ? maxv[i] : value);
    v ^= defv[i];
    *w = (u16)(i & 1 ? (*w & 0xFF00) | v : (*w & 0x00FF) | v << 8);
    fx3_p[i] = (unsigned char)decode(*w, i);
    dress();
    if (ui)
        ui[96] = 1;
    return 0;
}

/* ---- testi (std::function come in readable-values) */
static u32 pos(s32 value)
{
    value = (value + 0x80) >> 8;
    return (u32)(value < 0 ? 0 : value > 127 ? 127 : value);
}

static char *dec(char *buf, u32 n)                        /* intero senza segno */
{
    char t[10];
    u32 k = 0;
    do
        t[k++] = (char)('0' + n % 10);
    while ((n /= 10) && k < 10);
    while (k)
        *buf++ = t[--k];
    return buf;
}

static void fixed(char *buf, u32 n, u32 d, const char *unit) /* n / 10^d con d decimali (0..2) */
{
    u32 p = d == 2 ? 100 : d == 1 ? 10 : 1;
    buf = dec(buf, n / p);
    if (d) {
        *buf++ = '.';
        if (d == 2)
            *buf++ = (char)('0' + n / 10 % 10);
        *buf++ = (char)('0' + n % 10);
    }
    put(buf, unit);
}

static void hz_m(char *buf, u32 mhz)                      /* velocita': 0.05Hz .. 9.99Hz, 10.0 */
{
    if (mhz < 9995)
        fixed(buf, (mhz + 5) / 10, 2, "Hz");
    else
        fixed(buf, (mhz + 50) / 100, 1, "");
}

static void ms_u(char *buf, u32 us)                       /* tempi: 0.00ms, 1.0ms, 30ms */
{
    if (us < 995)
        fixed(buf, (us + 5) / 10, 2, "ms");
    else if (us < 9950)
        fixed(buf, (us + 50) / 100, 1, "ms");
    else
        fixed(buf, (us + 500) / 1000, 0, "ms");
}

static void hz(char *buf, u32 f)                          /* frequenze: 750Hz, 1.2kHz, 24kHz */
{
    if (f < 995)
        fixed(buf, f, 0, "Hz");
    else if (f < 9950)
        fixed(buf, (f + 50) / 100, 1, "kHz");
    else
        fixed(buf, (f + 500) / 1000, 0, "kHz");
}

static void sgn(char *buf, s32 x, const char *unit)       /* -95% 0% +95% */
{
    if (x)
        *buf++ = x < 0 ? '-' : '+';
    fixed(buf, (u32)(x < 0 ? -x : x), 0, unit);
}

static u32 type(void)
{
    return fx3_p[P_TYPE];
}

void fx3_fmt_type(const void *fn, s32 value, char *buf)
{
    u32 t = pos(value);
    (void)fn;
    put(buf, t_s[t < NT ? t : 0]);
}

void fx3_fmt_spd(const void *fn, s32 value, char *buf)
{
    u32 v = pos(value), t = type();
    (void)fn;
    dress();
    if (t == CRSH)
        hz(buf, 24000 / (1 + (31 * v + 63) / 127));
    else
        hz_m(buf, (t == CHOR ? RATE_C : RATE_F)[v]);
}

void fx3_fmt_dep(const void *fn, s32 value, char *buf)
{
    u32 v = pos(value), t = type();
    (void)fn;
    dress();
    if (t == CRSH)
        put(dec(buf, 16 - (15 * v + 63) / 127), "bit");
    else if (t == PHSR)
        fixed(buf, (60 * v + 63) / 127, 1, "oct");
    else
        ms_u(buf, (t == CHOR ? DEP_C : DEP_F)[v]);
}

void fx3_fmt_del(const void *fn, s32 value, char *buf)
{
    u32 v = pos(value), t = type();
    (void)fn;
    dress();
    if (t == CRSH)
        fixed(buf, (240 * v + 63) / 127, 1, "dB");
    else if (t == PHSR)
        hz(buf, FREQ_P[v]);
    else
        ms_u(buf, (t == CHOR ? TIME_C : TIME_F)[v]);
}

void fx3_fmt_fdbk(const void *fn, s32 value, char *buf)
{
    u32 v = pos(value), t = type();
    (void)fn;
    dress();
    if (t == CRSH)
        put(buf, "-");
    else if (t == CHOR)
        fixed(buf, (90 * v + 63) / 127, 0, "%");
    else {
        s32 m = t == FLNG ? 95 : 90, x = ((s32)v - 64) * m, r = (x < 0 ? -x + 31 : x + 31) / 63;
        sgn(buf, x < 0 ? -(r > m ? m : r) : r > m ? m : r, "%");
    }
}

void fx3_fmt_wid(const void *fn, s32 value, char *buf)
{
    u32 v = pos(value), t = type();
    (void)fn;
    dress();
    if (t == CRSH)
        put(buf, "-");
    else if (t == PHSR)
        fixed(buf, (100 * v + 63) / 127, 0, "%");
    else
        fixed(buf, (180 * v + 63) / 127, 0, "deg");
}

void fx3_fmt_vol(const void *fn, s32 value, char *buf) { (void)fn; put(buf, VOL_TXT[pos(value)]); }

/* grafica di TYPE (+36): il tipo come testo, centrato come le destinazioni degli LFO */
void fx3_type_gfx(const void *fn, s32 value, void *ctx, s32 x, s32 y)
{
    u32 t = pos(value);
    (void)fn;
    dress();
    DRAW_TEXT(ctx, FONT, x + 8, y + 5, 1, 0, "XXXX", "%s", t_s[t < NT ? t : 0]);
}

int fx3_mgr(void *dst, const void *src, int op)
{
    (void)dst;
    (void)src;
    (void)op;
    return 0;
}

#define PROTO(name, inv) \
    const void *const name[4] __attribute__((aligned(4))) = {0, 0, (const void *)fx3_mgr, (const void *)inv}
PROTO(fx3_proto_type, fx3_fmt_type);
PROTO(fx3_proto_spd, fx3_fmt_spd);
PROTO(fx3_proto_dep, fx3_fmt_dep);
PROTO(fx3_proto_del, fx3_fmt_del);
PROTO(fx3_proto_fdbk, fx3_fmt_fdbk);
PROTO(fx3_proto_wid, fx3_fmt_wid);
PROTO(fx3_proto_vol, fx3_fmt_vol);
PROTO(fx3_proto_type_gfx, fx3_type_gfx);

const u32 fx3_reverb_pages[2] = {21, 25};                  /* tab REVERB: pagina dell'OS + la nostra */
const char fx3_snd_s[] = "FX3";
const char fx3_snd_l[] = "FX3 Send";

/* cicli caldi in assembly */
__asm__(
    "        .globl  fx3_sum\n"
    "fx3_sum:\n"                                /* (dst, g[12], quali): 16 medie di coppie */
    "        lea     -44(%sp),%sp\n"
    "        movem.l %d2-%d7/%a2-%a6,(%sp)\n"
    "        movea.l 48(%sp),%a5\n"
    "        movea.l 52(%sp),%a6\n"
    "        movem.l (%a6),%d0-%d5/%d7/%a0-%a4\n" /* digitali d0-d5 d7 a0, analogiche a1-a4 */
    "        move.l  56(%sp),%d6\n"             /* 1 digitali, 2 analogiche, 3 tutte */
    "        movea.l #0x80003950,%a6\n"         /* analogiche a +128k, digitali a +1024+128k */
    "        subq.l  #2,%d6\n"
    "        beq.w   2f\n"
    "        bgt.w   3f\n"
    "1:      move.l  1024(%a6),%d6\n"           /* solo digitali */
    "        msac.l  %d0,%d6,1028(%a6),%d6,%acc0\n"
    "        msac.l  %d0,%d6,1152(%a6),%d6,%acc0\n"
    "        msac.l  %d1,%d6,1156(%a6),%d6,%acc0\n"
    "        msac.l  %d1,%d6,1280(%a6),%d6,%acc0\n"
    "        msac.l  %d2,%d6,1284(%a6),%d6,%acc0\n"
    "        msac.l  %d2,%d6,1408(%a6),%d6,%acc0\n"
    "        msac.l  %d3,%d6,1412(%a6),%d6,%acc0\n"
    "        msac.l  %d3,%d6,1536(%a6),%d6,%acc0\n"
    "        msac.l  %d4,%d6,1540(%a6),%d6,%acc0\n"
    "        msac.l  %d4,%d6,1664(%a6),%d6,%acc0\n"
    "        msac.l  %d5,%d6,1668(%a6),%d6,%acc0\n"
    "        msac.l  %d5,%d6,1792(%a6),%d6,%acc0\n"
    "        msac.l  %d7,%d6,1796(%a6),%d6,%acc0\n"
    "        msac.l  %d7,%d6,1920(%a6),%d6,%acc0\n"
    "        msac.l  %a0,%d6,1924(%a6),%d6,%acc0\n"
    "        msac.l  %a0,%d6,%acc0\n"
    "        addq.l  #8,%a6\n"
    "        movclr.l %acc0,%d6\n"
    "        move.l  %d6,(%a5)+\n"
    "        cmpa.l  #0x800039d0,%a6\n"
    "        bne.w   1b\n"
    "        bra.w   9f\n"
    "2:\n"
    "1:      move.l  (%a6),%d6\n"               /* solo analogiche */
    "        msac.l  %a1,%d6,4(%a6),%d6,%acc0\n"
    "        msac.l  %a1,%d6,128(%a6),%d6,%acc0\n"
    "        msac.l  %a2,%d6,132(%a6),%d6,%acc0\n"
    "        msac.l  %a2,%d6,256(%a6),%d6,%acc0\n"
    "        msac.l  %a3,%d6,260(%a6),%d6,%acc0\n"
    "        msac.l  %a3,%d6,384(%a6),%d6,%acc0\n"
    "        msac.l  %a4,%d6,388(%a6),%d6,%acc0\n"
    "        msac.l  %a4,%d6,%acc0\n"
    "        addq.l  #8,%a6\n"
    "        movclr.l %acc0,%d6\n"
    "        move.l  %d6,(%a5)+\n"
    "        cmpa.l  #0x800039d0,%a6\n"
    "        bne.w   1b\n"
    "        bra.w   9f\n"
    "3:\n"
    "1:      move.l  1024(%a6),%d6\n"           /* tutte */
    "        msac.l  %d0,%d6,1028(%a6),%d6,%acc0\n"
    "        msac.l  %d0,%d6,1152(%a6),%d6,%acc0\n"
    "        msac.l  %d1,%d6,1156(%a6),%d6,%acc0\n"
    "        msac.l  %d1,%d6,1280(%a6),%d6,%acc0\n"
    "        msac.l  %d2,%d6,1284(%a6),%d6,%acc0\n"
    "        msac.l  %d2,%d6,1408(%a6),%d6,%acc0\n"
    "        msac.l  %d3,%d6,1412(%a6),%d6,%acc0\n"
    "        msac.l  %d3,%d6,1536(%a6),%d6,%acc0\n"
    "        msac.l  %d4,%d6,1540(%a6),%d6,%acc0\n"
    "        msac.l  %d4,%d6,1664(%a6),%d6,%acc0\n"
    "        msac.l  %d5,%d6,1668(%a6),%d6,%acc0\n"
    "        msac.l  %d5,%d6,1792(%a6),%d6,%acc0\n"
    "        msac.l  %d7,%d6,1796(%a6),%d6,%acc0\n"
    "        msac.l  %d7,%d6,1920(%a6),%d6,%acc0\n"
    "        msac.l  %a0,%d6,1924(%a6),%d6,%acc0\n"
    "        msac.l  %a0,%d6,(%a6),%d6,%acc0\n"
    "        msac.l  %a1,%d6,4(%a6),%d6,%acc0\n"
    "        msac.l  %a1,%d6,128(%a6),%d6,%acc0\n"
    "        msac.l  %a2,%d6,132(%a6),%d6,%acc0\n"
    "        msac.l  %a2,%d6,256(%a6),%d6,%acc0\n"
    "        msac.l  %a3,%d6,260(%a6),%d6,%acc0\n"
    "        msac.l  %a3,%d6,384(%a6),%d6,%acc0\n"
    "        msac.l  %a4,%d6,388(%a6),%d6,%acc0\n"
    "        msac.l  %a4,%d6,%acc0\n"
    "        addq.l  #8,%a6\n"
    "        movclr.l %acc0,%d6\n"
    "        move.l  %d6,(%a5)+\n"
    "        cmpa.l  #0x800039d0,%a6\n"
    "        bne.w   1b\n"
    "9:      movem.l (%sp),%d2-%d7/%a2-%a6\n"
    "        lea     44(%sp),%sp\n"
    "        rts\n"
    "        .globl  fx3_sum1\n"
    "fx3_sum1:\n"                               /* (dst, src, g, somma?): una traccia */
    "        lea     -8(%sp),%sp\n"
    "        movem.l %d2-%d3,(%sp)\n"
    "        movea.l 12(%sp),%a0\n"
    "        movea.l 16(%sp),%a1\n"
    "        move.l  20(%sp),%d0\n"
    "        move.l  (%a1)+,%d1\n"
    "        moveq   #16,%d3\n"
    "        tst.l   24(%sp)\n"
    "        bne.s   2f\n"
    "1:      msac.l  %d0,%d1,(%a1)+,%d1,%acc0\n"/* dst = -g (x0 + x1) */
    "        msac.l  %d0,%d1,(%a1)+,%d1,%acc0\n"
    "        movclr.l %acc0,%d2\n"
    "        move.l  %d2,(%a0)+\n"
    "        subq.l  #1,%d3\n"
    "        bne.s   1b\n"
    "        bra.s   9f\n"
    "2:      move.l  (%a0),%d2\n"               /* dst += -g (x0 + x1) */
    "        move.l  %d2,%acc0\n"
    "        msac.l  %d0,%d1,(%a1)+,%d1,%acc0\n"
    "        msac.l  %d0,%d1,(%a1)+,%d1,%acc0\n"
    "        movclr.l %acc0,%d2\n"
    "        move.l  %d2,(%a0)+\n"
    "        subq.l  #1,%d3\n"
    "        bne.s   2b\n"
    "9:      movem.l (%sp),%d2-%d3\n"
    "        lea     8(%sp),%sp\n"
    "        rts\n"
    "        .globl  fx3_sum_end\n"
    "fx3_sum_end:\n"
    "        .globl  fx3_cho\n"
    "fx3_cho:\n"
    "        lea     -44(%sp),%sp\n"
    "        movem.l %d2-%d7/%a2-%a6,(%sp)\n"
    "        movea.l 48(%sp),%a6\n"
    "        movea.l (%a6),%a0\n"               /* linea (-4: retroazione Q15) */
    "        movea.l 4(%a6),%a1\n"              /* ingresso mono (parola alta di ogni campione) */
    "        movea.l 8(%a6),%a2\n"              /* uscita */
    "        lea     2048(%a0),%a3\n"           /* copia della linea */
    "        move.l  12(%a6),%d0\n"             /* pl, pr: posizioni di lettura Q8 */
    "        move.l  16(%a6),%d1\n"
    "        movea.l 20(%a6),%a4\n"             /* il, ir: passi */
    "        movea.l 24(%a6),%a5\n"
    "        move.l  28(%a6),%d4\n"             /* w: scrittura */
    "        moveq   #16,%d5\n"
    "        tst.l   -4(%a0)\n"
    "        bne.w   2f\n"
    "1:      add.l   %a4,%d0\n"                 /* un campione per giro (letture nella copia) */
    "        add.l   %a5,%d1\n"
    "        move.l  %d0,%d6\n"                 /* presa sinistra */
    "        lsr.l   #8,%d6\n"
    "        mvs.w   (%a0,%d6.l*2),%d7\n"
    "        mvs.w   2(%a0,%d6.l*2),%d6\n"
    "        sub.l   %d7,%d6\n"
    "        asr.l   #1,%d6\n"                  /* la differenza sta in 16 bit */
    "        mvz.b   %d0,%d2\n"
    "        muls.w  %d2,%d6\n"
    "        asr.l   #7,%d6\n"
    "        add.l   %d7,%d6\n"
    "        move.l  %d1,%d3\n"                 /* presa destra */
    "        lsr.l   #8,%d3\n"
    "        mvs.w   (%a0,%d3.l*2),%d7\n"
    "        mvs.w   2(%a0,%d3.l*2),%d3\n"
    "        sub.l   %d7,%d3\n"
    "        asr.l   #1,%d3\n"                  /* la differenza sta in 16 bit */
    "        mvz.b   %d1,%d2\n"
    "        muls.w  %d2,%d3\n"
    "        asr.l   #7,%d3\n"
    "        add.l   %d3,%d7\n"
    "        move.l  %d6,(%a2)+\n"
    "        move.l  %d7,(%a2)+\n"
    "        move.w  (%a1),%d2\n"               /* ingresso (parola alta) */
    "        addq.l  #4,%a1\n"
    "        move.w  %d2,(%a0,%d4.l*2)\n"
    "        move.w  %d2,(%a3,%d4.l*2)\n"
    "        addq.l  #1,%d4\n"
    "        subq.l  #1,%d5\n"
    "        bne.w   1b\n"
    "        bra.w   9f\n"
    "2:\n"
    "1:      add.l   %a4,%d0\n"                 /* un campione per giro (letture nella copia) */
    "        add.l   %a5,%d1\n"
    "        move.l  %d0,%d6\n"                 /* presa sinistra */
    "        lsr.l   #8,%d6\n"
    "        mvs.w   (%a0,%d6.l*2),%d7\n"
    "        mvs.w   2(%a0,%d6.l*2),%d6\n"
    "        sub.l   %d7,%d6\n"
    "        asr.l   #1,%d6\n"                  /* la differenza sta in 16 bit */
    "        mvz.b   %d0,%d2\n"
    "        muls.w  %d2,%d6\n"
    "        asr.l   #7,%d6\n"
    "        add.l   %d7,%d6\n"
    "        move.l  %d1,%d3\n"                 /* presa destra */
    "        lsr.l   #8,%d3\n"
    "        mvs.w   (%a0,%d3.l*2),%d7\n"
    "        mvs.w   2(%a0,%d3.l*2),%d3\n"
    "        sub.l   %d7,%d3\n"
    "        asr.l   #1,%d3\n"                  /* la differenza sta in 16 bit */
    "        mvz.b   %d1,%d2\n"
    "        muls.w  %d2,%d3\n"
    "        asr.l   #7,%d3\n"
    "        add.l   %d3,%d7\n"
    "        move.l  %d6,(%a2)+\n"
    "        move.l  %d7,(%a2)+\n"
    "        move.l  %d6,%d2\n"                 /* retroazione mono e ingresso, saturati a 16 bit */
    "        add.l   %d7,%d2\n"
    "        asr.l   #1,%d2\n"
    "        muls.l  -4(%a0),%d2\n"
    "        moveq   #15,%d3\n"
    "        asr.l   %d3,%d2\n"
    "        mvs.w   (%a1),%d3\n"
    "        addq.l  #4,%a1\n"
    "        add.l   %d3,%d2\n"
    "        cmpi.l  #32767,%d2\n"
    "        ble.s   3f\n"
    "        move.l  #32767,%d2\n"
    "3:      cmpi.l  #-32768,%d2\n"
    "        bge.s   4f\n"
    "        move.l  #-32768,%d2\n"
    "4:\n"
    "        move.w  %d2,(%a0,%d4.l*2)\n"
    "        move.w  %d2,(%a3,%d4.l*2)\n"
    "        addq.l  #1,%d4\n"
    "        subq.l  #1,%d5\n"
    "        bne.w   1b\n"
    "9:      move.l  %d0,12(%a6)\n"
    "        move.l  %d1,16(%a6)\n"
    "        move.l  %d4,28(%a6)\n"
    "        move.l  %d6,32(%a6)\n"
    "        move.l  %d7,36(%a6)\n"
    "        movem.l (%sp),%d2-%d7/%a2-%a6\n"
    "        lea     44(%sp),%sp\n"
    "        rts\n"
    "        .globl  fx3_ret\n"
    "fx3_ret:\n"                                /* (wet, guadagno Q15, a, h[2]): a -= 2 * wet * guadagno a 48 kHz, */
    "        lea     -28(%sp),%sp\n"            /* saturato; i campioni dispari sono quelli del chorus, */
    "        movem.l %d2-%d7/%a2,(%sp)\n"       /* i pari la media con il precedente (h = mezzo campione) */
    "        movea.l 32(%sp),%a0\n"
    "        move.l  36(%sp),%d1\n"
    "        movea.l 44(%sp),%a1\n"
    "        move.l  (%a1),%d2\n"
    "        move.l  4(%a1),%d3\n"
    "        movea.l 40(%sp),%a1\n"
    "        lea     256(%a1),%a2\n"            /* fine: 32 coppie L/R */
    "1:      movem.l (%a1),%d4-%d7\n"           /* L R di un campione pari e del dispari seguente */
    "        move.l  (%a0)+,%d0\n"
    "        muls.w  %d1,%d0\n"
    "        add.l   %d0,%d2\n"
    "        sub.l   %d2,%d4\n"
    "        sats.l  %d4\n"
    "        move.l  %d0,%d2\n"
    "        add.l   %d0,%d0\n"
    "        sub.l   %d0,%d6\n"
    "        sats.l  %d6\n"
    "        move.l  (%a0)+,%d0\n"
    "        muls.w  %d1,%d0\n"
    "        add.l   %d0,%d3\n"
    "        sub.l   %d3,%d5\n"
    "        sats.l  %d5\n"
    "        move.l  %d0,%d3\n"
    "        add.l   %d0,%d0\n"
    "        sub.l   %d0,%d7\n"
    "        sats.l  %d7\n"
    "        movem.l %d4-%d7,(%a1)\n"
    "        lea     16(%a1),%a1\n"
    "        cmpa.l  %a2,%a1\n"
    "        bne.s   1b\n"
    "        movea.l 44(%sp),%a1\n"
    "        move.l  %d2,(%a1)\n"
    "        move.l  %d3,4(%a1)\n"
    "        movem.l (%sp),%d2-%d7/%a2\n"
    "        lea     28(%sp),%sp\n"
    "        rts\n");

/* phaser */
__asm__(
    "        .globl  fx3_phs\n"
    "fx3_phs:\n"                                /* (p): 16 campioni */
    "        lea     -44(%sp),%sp\n"
    "        movem.l %d2-%d7/%a2-%a6,(%sp)\n"
    "        movea.l 48(%sp),%a2\n"
    "        movea.l (%a2),%a0\n"               /* ingresso */
    "        movea.l 4(%a2),%a1\n"              /* uscita */
    "        lea     64(%a0),%a3\n"             /* fine dell'ingresso */
    "        move.l  8(%a2),%d6\n"              /* coefficiente Q12 */
    "        movem.l 20(%a2),%d1-%d5\n"         /* stato */
    "        tst.l   12(%a2)\n"
    "        bne.w   2f\n"
    "1:      mvs.w   (%a0),%d0\n"               /* x (parola alta del bus) */
    "        addq.l  #4,%a0\n"
    "        move.l  %d0,%d7\n"                 /* y = a (x - s_k) + s_k-1, s0..s4 in d1..d5 */
    "        sub.l   %d2,%d7\n"
    "        muls.l  %d6,%d7\n"
    "        asr.l   #8,%d7\n"
    "        asr.l   #4,%d7\n"
    "        add.l   %d1,%d7\n"
    "        move.l  %d0,%d1\n"
    "        move.l  %d7,%d0\n"
    "        sub.l   %d3,%d0\n"
    "        muls.l  %d6,%d0\n"
    "        asr.l   #8,%d0\n"
    "        asr.l   #4,%d0\n"
    "        add.l   %d2,%d0\n"
    "        move.l  %d7,%d2\n"
    "        move.l  %d0,%d7\n"
    "        sub.l   %d4,%d7\n"
    "        muls.l  %d6,%d7\n"
    "        asr.l   #8,%d7\n"
    "        asr.l   #4,%d7\n"
    "        add.l   %d3,%d7\n"
    "        move.l  %d0,%d3\n"
    "        move.l  %d7,%d0\n"
    "        sub.l   %d5,%d0\n"
    "        muls.l  %d6,%d0\n"
    "        asr.l   #8,%d0\n"
    "        asr.l   #4,%d0\n"
    "        add.l   %d4,%d0\n"
    "        move.l  %d7,%d4\n"
    "        move.l  %d0,%d5\n"
    "        move.l  %d0,%d7\n"                 /* sinistra (x + y) / 2 */
    "        add.l   %d1,%d7\n"
    "        asr.l   #1,%d7\n"
    "        cmpi.l  #32767,%d7\n"
    "        ble.s   3f\n"
    "        move.l  #32767,%d7\n"
    "3:      cmpi.l  #-32768,%d7\n"
    "        bge.s   4f\n"
    "        move.l  #-32768,%d7\n"
    "4:\n"
    "        move.l  %d7,(%a1)+\n"
    "        muls.l  16(%a2),%d0\n"             /* destra: sinistra - WID * y */
    "        asr.l   #8,%d0\n"
    "        asr.l   #6,%d0\n"
    "        sub.l   %d0,%d7\n"
    "        cmpi.l  #32767,%d7\n"
    "        ble.s   3f\n"
    "        move.l  #32767,%d7\n"
    "3:      cmpi.l  #-32768,%d7\n"
    "        bge.s   4f\n"
    "        move.l  #-32768,%d7\n"
    "4:\n"
    "        move.l  %d7,(%a1)+\n"
    "        cmpa.l  %a3,%a0\n"
    "        bne.w   1b\n"
    "        bra.w   9f\n"
    "2:\n"
    "1:      mvs.w   (%a0),%d0\n"               /* x (parola alta del bus) */
    "        addq.l  #4,%a0\n"
    "        move.l  %d5,%d7\n"                 /* + retroazione dall'uscita, saturato a 16 bit */
    "        muls.l  12(%a2),%d7\n"
    "        asr.l   #8,%d7\n"
    "        asr.l   #7,%d7\n"
    "        add.l   %d7,%d0\n"
    "        cmpi.l  #32767,%d0\n"
    "        ble.s   3f\n"
    "        move.l  #32767,%d0\n"
    "3:      cmpi.l  #-32768,%d0\n"
    "        bge.s   4f\n"
    "        move.l  #-32768,%d0\n"
    "4:\n"
    "        move.l  %d0,%d7\n"                 /* y = a (x - s_k) + s_k-1, s0..s4 in d1..d5 */
    "        sub.l   %d2,%d7\n"
    "        muls.l  %d6,%d7\n"
    "        asr.l   #8,%d7\n"
    "        asr.l   #4,%d7\n"
    "        add.l   %d1,%d7\n"
    "        move.l  %d0,%d1\n"
    "        move.l  %d7,%d0\n"
    "        sub.l   %d3,%d0\n"
    "        muls.l  %d6,%d0\n"
    "        asr.l   #8,%d0\n"
    "        asr.l   #4,%d0\n"
    "        add.l   %d2,%d0\n"
    "        move.l  %d7,%d2\n"
    "        move.l  %d0,%d7\n"
    "        sub.l   %d4,%d7\n"
    "        muls.l  %d6,%d7\n"
    "        asr.l   #8,%d7\n"
    "        asr.l   #4,%d7\n"
    "        add.l   %d3,%d7\n"
    "        move.l  %d0,%d3\n"
    "        move.l  %d7,%d0\n"
    "        sub.l   %d5,%d0\n"
    "        muls.l  %d6,%d0\n"
    "        asr.l   #8,%d0\n"
    "        asr.l   #4,%d0\n"
    "        add.l   %d4,%d0\n"
    "        move.l  %d7,%d4\n"
    "        move.l  %d0,%d5\n"
    "        move.l  %d0,%d7\n"                 /* sinistra (x + y) / 2 */
    "        add.l   %d1,%d7\n"
    "        asr.l   #1,%d7\n"
    "        cmpi.l  #32767,%d7\n"
    "        ble.s   3f\n"
    "        move.l  #32767,%d7\n"
    "3:      cmpi.l  #-32768,%d7\n"
    "        bge.s   4f\n"
    "        move.l  #-32768,%d7\n"
    "4:\n"
    "        move.l  %d7,(%a1)+\n"
    "        muls.l  16(%a2),%d0\n"             /* destra: sinistra - WID * y */
    "        asr.l   #8,%d0\n"
    "        asr.l   #6,%d0\n"
    "        sub.l   %d0,%d7\n"
    "        cmpi.l  #32767,%d7\n"
    "        ble.s   3f\n"
    "        move.l  #32767,%d7\n"
    "3:      cmpi.l  #-32768,%d7\n"
    "        bge.s   4f\n"
    "        move.l  #-32768,%d7\n"
    "4:\n"
    "        move.l  %d7,(%a1)+\n"
    "        cmpa.l  %a3,%a0\n"
    "        bne.w   1b\n"
    "9:      movem.l %d1-%d5,20(%a2)\n"
    "        movem.l (%sp),%d2-%d7/%a2-%a6\n"
    "        lea     44(%sp),%sp\n"
    "        rts\n");

/* trampolini */
__asm__(
    "        .globl  fx3_trk_hook\n"
    "fx3_trk_hook:\n"                           /* ciclo per traccia (0x4008F3A0): d0/d1 guadagni, */
    "        .word   0xae00, 0x0900\n"          /* d3 traccia, a3 struttura; istruzioni sostituite: */
    "        .word   0xae81, 0x0900\n"          /* msac.l d0,d7,acc0 ; msac.l d1,d7,acc1 */
    "        tst.w   106(%a3)\n"                /* SND3 (id 72) spenta e bersaglio gia' 0: niente */
    "        bgt.s   1f\n"                      /* da fare (il caso comune, 12 volte a blocco) */
    "        move.l  %a0,-(%sp)\n"
    "        lea     fx3_tgt,%a0\n"
    "        tst.l   (%a0,%d3.l*4)\n"
    "        bne.s   2f\n"
    "        movea.l (%sp)+,%a0\n"
    "        rts\n"
    "2:      movea.l (%sp)+,%a0\n"
    "1:      lea     -16(%sp),%sp\n"            /* bersaglio mono della traccia (meta', per le */
    "        movem.l %d0-%d2/%a0,(%sp)\n"       /* coppie): ((gl/2 + gr/2) >> 16) * (2 v^2 >> 16) */
    "        moveq   #12,%d2\n"                 /* 0..7 digitali, 8..11 analogiche */
    "        cmp.l   %d2,%d3\n"
    "        bcc.s   9f\n"
    "        move.l  -508(%fp),%d2\n"           /* maschera dei mute */
    "        btst    %d3,%d2\n"
    "        bne.s   8f\n"
    "        mvs.w   106(%a3),%d2\n"            /* SND3 (id 72) */
    "        tst.l   %d2\n"
    "        ble.s   8f\n"
    "        muls.w  %d2,%d2\n"                 /* (v/32768)^2 in Q31, come DEL e REV */
    "        add.l   %d2,%d2\n"
    "        swap    %d2\n"
    "        asr.l   #1,%d0\n"
    "        asr.l   #1,%d1\n"
    "        add.l   %d1,%d0\n"
    "        swap    %d0\n"
    "        muls.w  %d0,%d2\n"
    "        bra.s   7f\n"
    "8:      moveq   #0,%d2\n"
    "7:      lea     fx3_tgt,%a0\n"
    "        cmp.l   (%a0,%d3.l*4),%d2\n"
    "        beq.s   9f\n"
    "        move.l  %a0,fx3_moving\n"          /* bersaglio cambiato: la rampa riparte */
    "        move.l  %d2,(%a0,%d3.l*4)\n"
    "9:      movem.l (%sp),%d0-%d2/%a0\n"
    "        lea     16(%sp),%sp\n"
    "        rts\n"
    "        .globl  fx3_del_hook\n"
    "fx3_del_hook:\n"                           /* al posto di jsr 0x40096890 (delay), 0x4008F828 */
    "        tst.l   fx3_idle\n"
    "        bne.s   1f\n"
    "        lea     -16(%sp),%sp\n"
    "        movem.l %d0-%d1/%a0-%a1,(%sp)\n"
    "        jsr     fx3_dsnd\n"                /* chorus del blocco precedente nel bus del delay */
    "        movem.l (%sp),%d0-%d1/%a0-%a1\n"
    "        lea     16(%sp),%sp\n"
    "1:      jmp     0x40096890\n"              /* il delay, con gli argomenti al loro posto */
    "        .globl  fx3_mix_hook\n"
    "fx3_mix_hook:\n"                           /* 0x4008FB04: al posto di pea -296(fp) ; pea 0x8000E0F0 */
    "        lea     -16(%sp),%sp\n"
    "        movem.l %d0-%d1/%a0-%a1,(%sp)\n"
    "        .globl  fx3_macsr\n"
    "fx3_macsr:\n"
    "        move.l  #0xA0,%macsr\n"            /* come l'OS prima delle somme (lo e' gia') */
    "        jsr     fx3_run\n"
    "        movem.l (%sp),%d0-%d1/%a0-%a1\n"
    "        lea     16(%sp),%sp\n"
    "        move.l  (%sp)+,%a0\n"
    "        pea     -296(%fp)\n"               /* istruzioni sostituite */
    "        pea     0x8000E0F0\n"
    "        jmp     (%a0)\n"
    "        .globl  fx3_draw_hook\n"
    "fx3_draw_hook:\n"                          /* disegno dei tab DELAY/REVERB (0x40042CE0): la pagina 25 */
    "        movea.l 4(%sp),%a0\n"              /* usa il disegno generico a 8 caselle (0x4003A244) */
    "        move.l  144(%a0),%d0\n"            /* posizione della pagina corrente */
    "        movea.l 124(%a0),%a1\n"            /* vettore delle pagine */
    "        move.l  (%a1,%d0.l*4),%d0\n"
    "        moveq   #25,%d1\n"
    "        cmp.l   %d1,%d0\n"
    "        bne.s   1f\n"
    "        jsr     fx3_active_context\n"
    "        tst.l   %d0\n"
    "        beq.s   1f\n"
    "        jmp     0x4003A244\n"
    "1:      lea     -96(%sp),%sp\n"            /* istruzioni sostituite */
    "        movem.l %d2-%d7/%a2-%a6,(%sp)\n"
    "        jmp     0x40042CE8\n"
    /* Kit nel file (salvataggio, FUNC+YES/NO, progetto): il blocco della FX track passa da 0x400A6D96
     * (scrittura) e 0x400A6D2E (lettura) con una tabella di posizioni che perde le parole degli id
     * interni 0x1A e 0x46 e rilegge nella 0 il valore della 0x1A. Le tre parole di fx3 vanno nei byte
     * +148..+155 del blocco nel file, che l'OS azzera e non legge: marcatore "SH" e le tre parole. */
    "        .globl  fx3_kser_hook\n"
    "fx3_kser_hook:\n"                         /* al posto di 0x400A6D96 (file, kit) */
    "        move.l  8(%sp),-(%sp)\n"
    "        move.l  8(%sp),-(%sp)\n"
    "        bsr.s   1f\n"
    "        addq.l  #8,%sp\n"
    "        tst.b   %d0\n"
    "        beq.s   2f\n"
    "        movea.l 4(%sp),%a0\n"              /* blocco nel file */
    "        movea.l 8(%sp),%a1\n"              /* blocco nel kit: una parola per id interno */
    "        move.w  #0x5348,%d1\n"
    "        move.w  %d1,148(%a0)\n"
    "        move.w  (%a1),150(%a0)\n"
    "        move.w  52(%a1),152(%a0)\n"
    "        move.w  140(%a1),154(%a0)\n"
    "2:      rts\n"
    "1:      move.l  %a3,-(%sp)\n"             /* istruzioni sostituite */
    "        move.l  %a2,-(%sp)\n"
    "        movea.l 12(%sp),%a2\n"
    "        jmp     0x400A6D9E\n"
    "        .globl  fx3_kdes_hook\n"
    "fx3_kdes_hook:\n"                         /* al posto di 0x400A6D2E (kit, file) */
    "        move.l  8(%sp),-(%sp)\n"
    "        move.l  8(%sp),-(%sp)\n"
    "        bsr.s   1f\n"
    "        addq.l  #8,%sp\n"
    "        tst.b   %d0\n"
    "        beq.s   3f\n"
    "        movea.l 4(%sp),%a0\n"              /* blocco nel kit */
    "        movea.l 8(%sp),%a1\n"              /* blocco nel file */
    "        move.w  148(%a1),%d1\n"
    "        cmpi.w  #0x5348,%d1\n"
    "        bne.s   2f\n"
    "        move.w  150(%a1),(%a0)\n"
    "        move.w  152(%a1),52(%a0)\n"
    "        move.w  154(%a1),140(%a0)\n"
    "        rts\n"
    "2:      clr.w   (%a0)\n"                  /* file senza marcatore: valori di default */
    "        clr.w   52(%a0)\n"
    "        clr.w   140(%a0)\n"
    "3:      rts\n"
    "1:      lea     -12(%sp),%sp\n"           /* istruzioni sostituite */
    "        movem.l %a2-%a4,(%sp)\n"
    "        jmp     0x400A6D36\n"
    "        .globl  fx3_amp_stub\n"
    "fx3_amp_stub:\n"                           /* al posto di clr.l 0x41B9F6A0 (fine delle pagine AMP): */
    "        move.l  %d0,-(%sp)\n"              /* SND3 (72) in G della pagina 1, accanto a DEL e REV, */
    "        moveq   #72,%d0\n"                 /* PAN (80) in E della pagina 2; due varianti per pagina */
    "        move.l  %d0,0x41B9F624\n"          /* (inviluppo AHD / ADSR) */
    "        move.l  %d0,0x41B9F650\n"
    "        moveq   #80,%d0\n"
    "        move.l  %d0,0x41B9F674\n"
    "        move.l  %d0,0x41B9F6A0\n"
    "        move.l  (%sp)+,%d0\n"
    "        rts\n");
