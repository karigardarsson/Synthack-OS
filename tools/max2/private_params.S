| MAX 2 compatibility namespace. Stock descriptors and objects remain intact.
        .equ TABLE, 0x46010000
        .equ OBJECTS, 0x46017000
        .equ READY, 0x46017ffc
        .equ STOCK_TABLE, 0x4022d59c
        .equ STOCK_OBJECTS, 0x41b9fa24
        .equ COPY_FN, 0x401882be
        .text
        .globl private_descriptors, private_objects, private_object_get
private_descriptors:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        lea STOCK_TABLE,%a0
        lea TABLE,%a1
        move.l #6564,%d0
1:      move.l (%a0)+,(%a1)+
        subq.l #1,%d0
        bge.s 1b
        lea extra_descriptors,%a0
        move.l #220,%d0
2:      move.l (%a0)+,(%a1)+
        subq.l #1,%d0
        bge.s 2b
        clr.l READY
        movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        rts
        .org 0x80
private_objects:
        lea -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        tst.l READY
        bne.w 9f
        lea object_donors,%a4
        lea OBJECTS,%a2
        moveq #16,%d2
3:      move.l (%a4)+,%d0
        mulu.w #84,%d0
        lea STOCK_OBJECTS,%a3
        adda.l %d0,%a3
        move.l (%a4)+,(%a2)+
        lea 4(%a3),%a3
        moveq #4,%d3
4:      move.l %a3,-(%sp)
        move.l %a2,-(%sp)
        jsr COPY_FN
        addq.l #8,%sp
        lea 16(%a2),%a2
        lea 16(%a3),%a3
        subq.l #1,%d3
        bge.s 4b
        subq.l #1,%d2
        bge.s 3b
        lea object_overrides,%a4
5:      move.l (%a4)+,%a2
        move.l %a2,%d0
        beq.s 8f
        move.l (%a4)+,-(%sp)
        move.l %a2,-(%sp)
        jsr COPY_FN
        addq.l #8,%sp
        bra.s 5b
8:      moveq #1,%d0
        move.l %d0,READY
9:      movem.l (%sp),%d0-%d7/%a0-%a6
        lea 60(%sp),%sp
        rts
        .org 0x200
private_object_get:
        move.l 4(%sp),%d1
        cmpi.l #505,%d1
        bcs.s 1f
        cmpi.l #522,%d1
        bcc.s 1f
        jsr private_objects
        move.l %d1,%d0
        subi.l #505,%d0
        mulu.w #84,%d0
        addi.l #OBJECTS,%d0
        rts
1:      cmpi.l #505,%d1
        jmp 0x4007b9bc
        .org 0x300
extra_descriptors:
        .incbin "descriptors.bin"
object_donors:
        .include "objects.inc"
