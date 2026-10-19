"""SHLZ codec shared with the authoritative development builder."""
from __future__ import annotations
import struct
MAGIC=b"SHLZ"; HDR=12; MIN=3; MAX_LEN=130; MAX_LIT=128; WINDOW=0xFFFF
def compress(data: bytes) -> bytes:
    n=len(data); out=bytearray(); lits=bytearray(); heads={}
    def flush():
        for k in range(0,len(lits),MAX_LIT):
            c=lits[k:k+MAX_LIT]; out.append(len(c)-1); out.extend(c)
        lits.clear()
    i=0
    while i<n:
        best_len=best_off=0
        if i+MIN<=n:
            key=bytes(data[i:i+MIN])
            for j in reversed(heads.get(key,[])[-64:]):
                if i-j>WINDOW: break
                length=MIN
                while length<MAX_LEN and i+length<n and data[j+length]==data[i+length]: length+=1
                if length>best_len:
                    best_len,best_off=length,i-j
                    if length==MAX_LEN: break
        step=best_len if best_len>=MIN else 1
        for k in range(i,min(i+step,n-MIN+1)): heads.setdefault(bytes(data[k:k+MIN]),[]).append(k)
        if best_len>=MIN:
            flush(); out.append(0x80|(best_len-MIN)); out.extend(struct.pack(">H",best_off))
        else: lits.append(data[i])
        i+=step
    flush()
    return MAGIC+struct.pack(">II",n,len(out))+bytes(out)
def decompress(blob: bytes) -> bytes:
    if blob[:4]!=MAGIC: raise ValueError("not SHLZ")
    n,clen=struct.unpack_from(">II",blob,4); src=blob[HDR:HDR+clen]; out=bytearray(); i=0
    while len(out)<n:
        c=src[i]; i+=1
        if c&0x80:
            length=(c&0x7f)+MIN; off=(src[i]<<8)|src[i+1]; i+=2
            if not 0<off<=len(out): raise ValueError("invalid SHLZ distance")
            for _ in range(length): out.append(out[-off])
        else: out+=src[i:i+c+1]; i+=c+1
    if len(out)!=n or i!=clen: raise ValueError("invalid SHLZ lengths")
    return bytes(out)
