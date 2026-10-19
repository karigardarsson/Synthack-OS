"""Offline Syntakt MAX 1.0 builder. It never transfers firmware to hardware."""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import lz
LOAD=0x40000400; PROTECTED={2,6}; PATCHABLE={3,7}; MIN_MARGIN=4096
COUNT_OFF,TABLE_OFF,ENTRY=0x1c,0x20,16; SRC,DST=0x40200000,0x40000400
class BuildError(RuntimeError): pass
def digest_path(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def resource(name):
    root=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))
    return root/name
def manifest_path(): return resource("resources/max-1.0-manifest.json")
def eft_path(): return resource("resources/elektron-firmware-tool.exe")
def run_eft(*args):
    tool=eft_path()
    if not tool.is_file(): raise BuildError("bundled elektron-firmware-tool.exe is missing")
    p=subprocess.run([str(tool),*map(str,args)],capture_output=True,text=True,encoding="utf-8",errors="replace")
    if p.returncode: raise BuildError("firmware container tool failed: "+(p.stderr.strip() or p.stdout.strip()))
    return p.stdout
def parse_info(text):
    f=dict(re.findall(r"^(device|version|container|checksums)\s*:\s*(.*)$",text,re.M))
    return {k:v.strip() for k,v in f.items()}
def info(p): return parse_info(run_eft("-i",p))
def unpack(syx,outdir,ids):
    outdir.mkdir(parents=True,exist_ok=True); args=["-i",syx]
    for sid in ids: args+=["-d",str(sid)]
    run_eft(*args,"-o",outdir); ans={}
    for sid in ids:
        m=list(outdir.glob(f"section_{sid}_*"))
        if len(m)!=1: raise BuildError(f"container did not unpack section {sid}")
        ans[sid]=m[0]
    return ans
def read_stream(syx):
    with tempfile.TemporaryDirectory(prefix="max1-container-",dir=Path(syx).parent) as d:
        c=Path(d)/"container.bin"; run_eft("-i",syx,"--emit-container",c); data=c.read_bytes()
    count=int.from_bytes(data[COUNT_OFF:COUNT_OFF+4],"big")
    for k in range(count):
        at=TABLE_OFF+ENTRY*k; sid,off,clen,_=tuple(int.from_bytes(data[at+i:at+i+4],"big") for i in range(0,16,4))
        if sid==3:return data[off:off+clen]
    raise BuildError("section 3 is missing")
def margin(syx):
    stream=read_stream(syx); ip=8; op=tag=0; last=1; worst=1<<40
    def bit():
        nonlocal tag,ip
        tag=(tag<<1)&0xffff
        if not tag&0xff:
            by=stream[ip]; ip+=1; tag=(by<<1)|1; return by>>7
        return (tag>>8)&1
    def gamma():
        v=1
        while True:
            v=(v<<1)+bit()
            if bit(): return v
    try:
        while ip<len(stream):
            if bit(): ip+=1; op+=1
            else:
                g=gamma()
                if g==2: off=last
                else:
                    off=(g<<8)+stream[ip]; ip+=1
                    if off==767: break
                    off-=767; last=off
                length=2*bit()+bit(); length=length if length else gamma()+2
                if off>3328:length+=1
                op+=length+1
            worst=min(worst,(SRC-DST)+ip-op)
    except IndexError: pass
    return worst
def apply(sections, mods):
    patches=[]
    for mod in mods:
        if mod.get("os")!="1.41": raise BuildError(f"{mod.get('name')}: wrong OS declaration")
        patches += [(mod["name"],p) for p in mod["patches"]]
    seen={sid:[] for sid in PATCHABLE}; stock_len={sid:len(x) for sid,x in sections.items()}; decoded=[]
    for name,p in patches:
        sid=p["section"]
        if sid not in PATCHABLE: raise BuildError(f"{name}: protected or unsupported section {sid}")
        data=bytes.fromhex(p.get("hex","").replace(" ","")) if "hex" in p else p["ascii"].encode("ascii")
        if len(data)!=p["len"]: raise BuildError(f"{name}: patch length mismatch")
        off=int(p["addr"],16)-LOAD; end=off+len(data); append=p.get("append",False)
        if append and off<stock_len[sid]: raise BuildError(f"{name}: append overlaps stock")
        if not append:
            if off<0 or end>stock_len[sid]: raise BuildError(f"{name}: patch is outside stock section")
            if hashlib.sha256(sections[sid][off:end]).hexdigest()!=p["expect_sha256"].lower(): raise BuildError(f"{name}: stock patch guard rejected input")
        for a,b,other in seen[sid]:
            if off<b and a<end: raise BuildError(f"{name}: overlaps {other}")
        seen[sid].append((off,end,name)); decoded.append((sid,off,end,data))
    for sid,off,end,data in decoded:
        if end>len(sections[sid]): sections[sid].extend(b"\0"*(end-len(sections[sid])))
        sections[sid][off:end]=data
def build(stock, destination, progress=lambda _:None):
    stock=Path(stock); destination=Path(destination); manifest=json.loads(manifest_path().read_text(encoding="utf-8"))
    if digest_path(stock)!=manifest["stock_sha256"]: raise BuildError("selected file is not the official Syntakt OS 1.41 image")
    progress("Validating firmware container"); meta=info(stock)
    if "Syntakt" not in meta.get("device","") or meta.get("version")!="1.41" or meta.get("checksums")!="ok": raise BuildError("container validation failed")
    if destination.suffix.lower()!=".syx": destination=destination.with_suffix(".syx")
    if destination.exists(): raise BuildError("destination already exists; choose a new filename")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".max1-",dir=destination.parent) as td:
        td=Path(td); files=unpack(stock,td/"stock",[3,7]); sections={k:bytearray(v.read_bytes()) for k,v in files.items()}
        progress("Applying guarded MAX patches"); apply(sections,manifest["mods"])
        layout=next((m["layout"] for m in manifest["mods"] if m.get("layout",{}).get("compress")=="shlz"),None)
        if not layout: raise BuildError("release manifest lacks mod-area layout")
        img=int(layout["img"],16); size=int(layout["size"],16); off=img-LOAD; area=bytes(sections[3][off:])
        if len(area)>size: raise BuildError("MAX mod area exceeds its reserved heap block")
        del sections[3][off:]; sections[3].extend(lz.compress(area))
        replacement={}
        for sid,data in sections.items():
            p=td/f"section_{sid}.bin";p.write_bytes(data);replacement[sid]=p
        candidate=td/"candidate.syx"; progress("Repacking firmware container"); args=["-i",stock,"-l","3"]
        for sid,p in sorted(replacement.items()): args+=["-c",str(sid),p]
        run_eft(*args,"-o",candidate); progress("Verifying output"); built=info(candidate)
        if built.get("checksums")!="ok" or built.get("version")!="1.41": raise BuildError("output container checks failed")
        m=margin(candidate)
        if m<MIN_MARGIN: raise BuildError(f"section 3 boot margin unsafe: {m} bytes")
        got=digest_path(candidate)
        if got!=manifest["golden_sha256"]: raise BuildError("output does not match the verified MAX 1.0 golden hash")
        candidate.replace(destination)
    progress("Complete"); return {"output":str(destination),"sha256":got,"boot_margin":m}
