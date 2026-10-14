"""Build Syntakt MAX from verified stock 1.41 and a separate Workbench checkout.

The Workbench checkout must be next to Synthack-OS at the pinned revision.
Generated patches live only in a temporary directory; stock and baseline are untouched.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WB = ROOT.parent / "syntakt-firmware-workbench"
sys.path.insert(0, str(ROOT / "tools" / "unpack"))
sys.path.insert(0, str(ROOT / "tools" / "build"))
import eft  # noqa: E402
from build import BuildError, build, load_mod  # noqa: E402

STOCK = ROOT / "firmware" / "Syntakt_OS1.41.syx"
OUTPUT = ROOT / "out" / "synthack-max.syx"
STOCK_HASH = "8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e"
WB_COMMIT = "49a7a1e5ac1ac4c6869f01b94a820f2b625dada5"
MODS = ["splash", "dual-mono", "modarea", "vparams", "master-comp",
        "readable-values", "beat-repeat", "fx3"]
NODE = Path(os.environ.get("SYNTHACK_NODE") or shutil.which("node") or "node")
LOAD = 0x40000400


def digest(data):
    return hashlib.sha256(data).hexdigest()


def winpath(path):
    if NODE.suffix.lower() == ".exe":
        return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
    return str(Path(path).resolve())


def occupied():
    spans = {3: [], 7: []}
    for name in MODS:
        for p in load_mod(ROOT / "mods" / name, "1.41"):
            if not p.append:
                spans[p.section].append((p.offset, p.end, name))
    return spans


def generate_patches(original, target, regions, occupied_spans):
    patches = []
    for sid in (3, 7):
        old, new = original[sid], target[sid]
        if len(old) != len(new):
            raise BuildError(f"Workbench resized section {sid}")
        permitted = bytearray(len(old))
        for r in regions:
            if r["section"] == sid:
                if r["start"] < 0 or r["end"] > len(old):
                    raise BuildError(f"Workbench region outside section {sid}: {r}")
                permitted[r["start"]:r["end"]] = b"\x01" * (r["end"] - r["start"])
        blockers = bytearray(len(old))
        for a, b, _ in occupied_spans[sid]:
            blockers[a:b] = b"\x01" * (b - a)
        changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
        if not changed or any(not permitted[i] for i in changed):
            raise BuildError(f"Workbench has no changes or undeclared changes in section {sid}")
        conflict = next((i for i in changed if blockers[i]), None)
        if conflict is not None:
            owners = [n for a, b, n in occupied_spans[sid] if a <= conflict < b]
            raise BuildError(f"Workbench collides at section {sid} offset {conflict:#x}: {owners}")
        # Use each declared region minus occupied SyntHack sites. Full spans avoid
        # thousands of tiny patches in the 31-frame bank and picture table.
        for r in (r for r in regions if r["section"] == sid):
            pos = r["start"]
            while pos < r["end"]:
                while pos < r["end"] and blockers[pos]:
                    pos += 1
                start = pos
                while pos < r["end"] and not blockers[pos]:
                    pos += 1
                end = pos
                if start < end and old[start:end] != new[start:end]:
                    patches.append({"section": sid, "addr": f"0x{LOAD + start:08x}",
                                    "len": end - start, "expect_sha256": digest(old[start:end]),
                                    "hex": new[start:end].hex()})
    return patches


def main():
    global NODE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--node", type=Path, default=NODE)
    args = ap.parse_args()
    NODE = args.node.resolve()
    if digest(STOCK.read_bytes()) != STOCK_HASH:
        raise BuildError("stock Syntakt OS 1.41 SHA-256 mismatch")
    revision = subprocess.check_output(["git", "-C", str(WB), "rev-parse", "HEAD"], text=True).strip()
    if revision != WB_COMMIT:
        raise BuildError(f"Workbench revision {revision} does not match {WB_COMMIT}")
    if not args.node.exists():
        raise BuildError(f"Node runtime unavailable: {args.node}")
    baseline = OUTPUT.parent / "synthack.syx"
    baseline_hash = digest(baseline.read_bytes())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="synthack-max-", dir=OUTPUT.parent) as dirname:
        tmp = Path(dirname)
        files = eft.unpack(STOCK, tmp / "stock", ids=[3, 7])
        original = {sid: files[sid].read_bytes() for sid in (3, 7)}
        target_files = {sid: tmp / f"section_{sid}.max" for sid in (3, 7)}
        metadata = tmp / "workbench.json"
        subprocess.run([str(args.node), "tools/max/generate.mjs",
                        *[winpath(files[sid]) for sid in (3, 7)],
                        *[winpath(target_files[sid]) for sid in (3, 7)], winpath(metadata)],
                       cwd=ROOT, check=True)
        target = {sid: target_files[sid].read_bytes() for sid in (3, 7)}
        wb = json.loads(metadata.read_text())
        patches = generate_patches(original, target, wb["regions"], occupied())
        moddir = tmp / "workbench-max"
        moddir.mkdir()
        (moddir / "patch.json").write_text(json.dumps({"name": "workbench-max", "os": "1.41",
                                                        "patches": patches}))
        candidate = tmp / "synthack-max.syx"
        result = build(STOCK, [ROOT / "mods" / name for name in MODS] + [moddir], candidate)
        # The combined build may move/recompress sections, but the Workbench regions
        # must contain exactly the bytes its standalone generator produced.
        combined = eft.unpack(candidate, tmp / "combined", ids=[3, 7])
        retained = eft.unpack(baseline, tmp / "baseline", ids=[3, 7])
        for sid in (3, 7):
            data = combined[sid].read_bytes()
            earlier = retained[sid].read_bytes()
            if len(data) != len(earlier):
                raise BuildError(f"baseline section {sid} length changed")
            workbench_bytes = bytearray(len(data))
            for r in (r for r in wb["regions"] if r["section"] == sid):
                assert data[r["start"]:r["end"]] == target[sid][r["start"]:r["end"]]
                workbench_bytes[r["start"]:r["end"]] = b"\x01" * (r["end"] - r["start"])
            stray = next((i for i, (a, b) in enumerate(zip(earlier, data))
                          if a != b and not workbench_bytes[i]), None)
            if stray is not None:
                raise BuildError(f"baseline regression in section {sid} at {stray:#x}")
        if digest(STOCK.read_bytes()) != STOCK_HASH or digest(baseline.read_bytes()) != baseline_hash:
            raise BuildError("stock or baseline changed during build")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        candidate.replace(OUTPUT)
        report = {**result, "workbench_commit": revision, "baseline_sha256": baseline_hash,
                  "wave_bank": wb["waves"], "workbench_patch_count": len(patches)}
        OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
