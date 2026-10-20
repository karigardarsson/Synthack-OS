.text
.globl comp_draw_hook
comp_draw_hook:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        jsr     comp_ui_update
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        lea     -80(%sp),%sp
        movem.l %d2-%d7/%a2-%a6,(%sp)
        jmp     0x4003A24C
