"""Offline, guarded Syntakt OS 1.41 modular firmware builder."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import legacy_max_core as base
import lz

BuildError = base.BuildError
digest_path = base.digest_path

FEATURES = (
    ("master_comp", "Master Compressor", "master-comp"),
    ("fx3", "FX3", "fx3"),
    ("beat_repeat", "Beat Repeat", "beat-repeat"),
    ("dual_mono", "Dual Mono Input", "dual-mono"),
    ("readable_values", "Readable Values", "readable-values"),
    ("deja_vu", "Déjà Vu LFO", "deja-vu"),
    ("sy_chord", "SY CHORD Wave Bank", "sy-chord"),
    ("fm4", "SY FM4", "fm4"),
)
FEATURE_TO_MOD = {key: mod for key, _, mod in FEATURES}
MAX_FEATURES = frozenset(FEATURE_TO_MOD) - {"fm4"}
PRESETS = {
    "MAX FULL + FM4": frozenset(FEATURE_TO_MOD),
    "Original MAX 1.0": MAX_FEATURES,
    "FM4 ONLY": frozenset({"fm4"}),
}


def manifest_path() -> Path:
    return base.resource("resources/modular-manifest.json")


def load_manifest() -> dict:
    manifest = json.loads(manifest_path().read_text(encoding="utf-8"))
    if manifest.get("format") != 2 or manifest.get("os") != "1.41":
        raise BuildError("modular release manifest has an unsupported format")
    if manifest.get("stock_sha256") != "8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e":
        raise BuildError("modular release manifest has an unexpected stock image")
    names = [mod["name"] for mod in manifest["mods"]]
    if len(names) != len(set(names)) or not set(FEATURE_TO_MOD.values()) <= set(names):
        raise BuildError("modular release manifest is incomplete or ambiguous")
    return manifest


def resolve(selection, manifest: dict | None = None) -> list[dict]:
    """Resolve user-visible features to the exact stock-guarded mod order."""
    manifest = manifest or load_manifest()
    chosen = frozenset(selection)
    unknown = chosen - set(FEATURE_TO_MOD)
    if unknown:
        raise BuildError("unknown feature selection: " + ", ".join(sorted(unknown)))
    if not chosen:
        raise BuildError("select at least one feature")
    needed = {FEATURE_TO_MOD[key] for key in chosen}
    if MAX_FEATURES <= chosen:
        needed.add("splash")
    if needed & {"master-comp", "fx3", "beat-repeat"}:
        needed.add("vparams")
    if needed & {"master-comp", "fx3", "beat-repeat", "readable-values", "fm4"}:
        needed.add("modarea")
    result = [mod for mod in manifest["mods"] if mod["name"] in needed]
    found = {mod["name"] for mod in result}
    if found != needed:
        raise BuildError("missing bundled mod: " + ", ".join(sorted(needed - found)))
    for mod in result:
        missing = set(mod.get("requires", ())) - found
        if missing:
            raise BuildError(f"{mod['name']} requires {', '.join(sorted(missing))}")
    if "fm4" in needed:
        layout = next((mod.get("layout") for mod in result if mod["name"] == "modarea"), None)
        if not layout or layout.get("ram", "").lower() != "0x444e38d0":
            raise BuildError("FM4 requires the heap-reserved modarea loader")
    return result


def profile_name(selection) -> str:
    chosen = frozenset(selection)
    for name, features in PRESETS.items():
        if chosen == features:
            return name
    return "CUSTOM"


def selected_manifest(selection, manifest: dict | None = None) -> dict:
    manifest = manifest or load_manifest()
    mods = resolve(selection, manifest)
    return {
        "format": 2,
        "os": "1.41",
        "stock_sha256": manifest["stock_sha256"],
        "mods": mods,
    }


def validate_static(selection, stock_sections: dict[int, bytes], manifest: dict | None = None) -> dict:
    """Check patch preimages, ownership, CPU2 guard and heap placement."""
    chosen = selected_manifest(selection, manifest)
    sections = {sid: bytearray(data) for sid, data in stock_sections.items()}
    base.apply(sections, chosen["mods"])
    layout = next((mod["layout"] for mod in chosen["mods"] if mod.get("layout", {}).get("compress") == "shlz"), None)
    area_bytes = 0
    if layout:
        if layout.get("ram", "").lower() != "0x444e38d0" or int(layout["size"], 16) != 0xfff0:
            raise BuildError("unexpected heap modarea ownership")
        off = int(layout["img"], 16) - base.LOAD
        if off < len(stock_sections[3]) or off > len(sections[3]):
            raise BuildError("invalid modarea image placement")
        area_bytes = len(sections[3]) - off
        if area_bytes > int(layout["size"], 16):
            raise BuildError(f"modarea exceeds its heap reservation: {area_bytes} bytes")
    if "fm4" in selection:
        manifest = manifest or load_manifest()
        for patch in next(mod for mod in manifest["mods"] if mod["name"] == "fm4")["patches"]:
            if patch["section"] == 7 and patch.get("append"):
                if int(patch["addr"], 16) + patch["len"] > base.LOAD + 0x60000 - 5:
                    raise BuildError("FM4 CPU2 payload exceeds its loader limit")
    return {"mods": [mod["name"] for mod in chosen["mods"]],
            "patches": sum(len(mod["patches"]) for mod in chosen["mods"]),
            "modarea_bytes": area_bytes}


def build(stock, destination, selection, progress=lambda _: None) -> dict:
    stock = Path(stock)
    destination = Path(destination)
    manifest = load_manifest()
    chosen = selected_manifest(selection, manifest)
    if digest_path(stock) != manifest["stock_sha256"]:
        raise BuildError("selected file is not the verified official Syntakt OS 1.41 image")
    if destination.suffix.lower() != ".syx":
        destination = destination.with_suffix(".syx")
    report_path = destination.with_suffix(".json")
    if destination.exists() or report_path.exists():
        raise BuildError("output or build manifest already exists; choose a new filename")
    progress("Validating stock firmware")
    info = base.info(stock)
    if "Syntakt" not in info.get("device", "") or info.get("version") != "1.41" or info.get("checksums") != "ok":
        raise BuildError("stock firmware container failed validation")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".syntakt-modular-", dir=destination.parent) as name:
        work = Path(name)
        files = base.unpack(stock, work / "stock", [3, 7])
        original = {sid: path.read_bytes() for sid, path in files.items()}
        checked = validate_static(selection, original, manifest)
        sections = {sid: bytearray(data) for sid, data in original.items()}
        progress("Applying guarded feature patches")
        base.apply(sections, chosen["mods"])
        layout = next((mod["layout"] for mod in chosen["mods"] if mod.get("layout", {}).get("compress") == "shlz"), None)
        if layout:
            off = int(layout["img"], 16) - base.LOAD
            area = bytes(sections[3][off:])
            del sections[3][off:]
            sections[3].extend(lz.compress(area))
        touched = {patch["section"] for mod in chosen["mods"] for patch in mod["patches"]}
        replacements = {}
        for sid in sorted(touched):
            replacement = work / f"section_{sid}.bin"
            replacement.write_bytes(sections[sid])
            replacements[sid] = replacement
        candidate = work / "candidate.syx"
        progress("Packing firmware container")
        args = ["-i", stock, "-l", "3"]
        for sid, path in replacements.items():
            args += ["-c", sid, path]
        base.run_eft(*args, "-o", candidate)
        progress("Verifying firmware and boot margin")
        built = base.info(candidate)
        if built.get("checksums") != "ok" or built.get("version") != "1.41":
            raise BuildError("output container checks failed")
        margin = base.margin(candidate)
        if margin < base.MIN_MARGIN:
            raise BuildError(f"unsafe boot margin: {margin} bytes")
        decoded = base.unpack(candidate, work / "decoded", sorted(touched))
        for sid in touched:
            if decoded[sid].read_bytes() != bytes(sections[sid]):
                raise BuildError(f"section {sid} differs after container packing")
        got = digest_path(candidate)
        profile = profile_name(selection)
        expected = manifest.get("golden_sha256", {}).get(profile)
        if expected and got != expected:
            raise BuildError(f"{profile} differs from its pinned expected output")
        report = {"profile": profile, "features": [key for key, _, _ in FEATURES if key in selection],
                  "mods": checked["mods"], "patches": checked["patches"],
                  "modarea_bytes": checked["modarea_bytes"], "boot_margin": margin,
                  "stock_sha256": manifest["stock_sha256"], "output_sha256": got,
                  "output": str(destination)}
        report_tmp = work / "build.json"
        report_tmp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        try:
            shutil.move(candidate, destination)
            shutil.move(report_tmp, report_path)
        except Exception:
            if destination.exists():
                destination.unlink()
            raise
    progress("Complete")
    return report
