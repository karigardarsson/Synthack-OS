| vparams -- shared virtual parameters for mods.
| A 16-byte entry is {id.w, reserved.w, get, set, optional zero-argument guard}.
| Guarded entries fall through to the stock path outside their owning context.

        .equ    VP_N,           32

        .text
        .globl  vp_kit, vp_get, vp_set

vp_find:
        lea     VP_TABLE,%a1
        moveq   #VP_N-1,%d1
1:      cmp.w   (%a1),%d0
        beq.s   2f
        lea     16(%a1),%a1
        subq.l  #1,%d1
        bge.s   1b
        suba.l  %a1,%a1
2:      move.l  %a1,%d1
        rts

vp_guard:
        movea.l 12(%a1),%a0
        tst.l   %a0
        beq.s   1f
        move.l  %a1,-(%sp)
        jsr     (%a0)
        movea.l (%sp)+,%a1
        tst.l   %d0
        beq.s   2f
1:      moveq   #1,%d0
        rts
2:      clr.l   %d0
        rts

vp_kit:
        move.l  8(%sp),%d0
        beq.s   9f
        bsr.s   vp_find
        beq.s   9f
        bsr.s   vp_guard
        beq.s   9f
        moveq   #1,%d0
        rts
9:      move.l  %d2,-(%sp)
        moveq   #124,%d2
        move.l  8(%sp),%d1
        jmp     0x4000D878

vp_get:
        move.l  8(%sp),%d0
        beq.s   9f
        bsr.s   vp_find
        beq.s   9f
        bsr.s   vp_guard
        beq.s   9f
        movea.l 4(%a1),%a0
        jmp     (%a0)
9:      move.l  %d2,-(%sp)
        move.l  8(%sp),%d1
        jmp     0x4000D950

vp_set:
        move.l  8(%sp),%d0
        beq.s   9f
        bsr.s   vp_find
        beq.s   9f
        bsr.s   vp_guard
        beq.s   9f
        movea.l 8(%a1),%a0
        jmp     (%a0)
9:      move.l  %d3,-(%sp)
        move.l  %d2,-(%sp)
        move.l  12(%sp),%d1
        jmp     0x4000DA3A
