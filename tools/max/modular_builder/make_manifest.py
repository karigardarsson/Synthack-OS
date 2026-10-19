"""Assemble the release manifest from pinned, source-derived mod manifests.

This developer tool reads patch data only. It never reads or packages stock firmware.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PINNED = {
    "max": "d3de471187cf4055779ceb889486961620914869d2bf74e1c0a964cf2dd2b3a6",
    "deja": "b8001c3836bb45a368c83381e514ea9020651bb84a590168dfe2b6275c816476",
    "chord": "3614a5eadd79e641f6f27825298bcc7c3ac80770109e407b8ee460c37a72418e",
    "fm4": "1fbf28cb59df0a4abdcf2c76093157d897bd104c095916956bdf8b717f46f298",
}
ORDER = ("splash", "dual-mono", "modarea", "vparams", "master-comp",
         "readable-values", "beat-repeat", "fx3", "deja-vu", "sy-chord", "fm4")


def pinned(path: Path, role: str) -> dict:
    data = path.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != PINNED[role]:
        raise ValueError(f"{role} manifest fingerprint changed: {got}")
    return json.loads(data)


def assemble(max_path: Path, deja_path: Path, chord_path: Path, fm4_path: Path) -> dict:
    max_release = pinned(max_path, "max")
    deja = pinned(deja_path, "deja")
    chord = pinned(chord_path, "chord")
    fm4_release = pinned(fm4_path, "fm4")
    max_mods = {mod["name"]: mod for mod in max_release["mods"]}
    if max_mods["modarea"]["layout"].get("ram", "").lower() != "0x444e38d0":
        raise ValueError("MAX manifest does not use the heap-reserved modarea")
    fm4_mods = {mod["name"]: mod for mod in fm4_release["mods"]}
    if fm4_mods["fm4"].get("requires") != ["modarea"]:
        raise ValueError("FM4 dependency changed")
    mods = [max_mods[name] for name in ORDER[:8]] + [deja, chord, fm4_mods["fm4"]]
    if tuple(mod["name"] for mod in mods) != ORDER:
        raise ValueError("unexpected feature manifest order")
    return {
        "format": 2,
        "name": "Syntakt MAX Modular OS 1.41",
        "os": "1.41",
        "stock_sha256": max_release["stock_sha256"],
        "golden_sha256": {
            "Original MAX 1.0": "7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093",
            "MAX FULL + FM4": "3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89",
            "FM4 ONLY": "1f74cad579848132aad0b25bc9371b7dd2bbee72961cd98a3e351cd8695e860e",
        },
        "historical_fm4_rc1_sha256": "8197f9c73175d89a527635b57ad42aa7ce243a495f20e0c8548d9cbb81d81a8a",
        "source_manifest_sha256": PINNED,
        "fm4_upstream_commit": "a596b6393fc43582fd3ae0234ac04e198b779edb",
        "workbench_commit": max_release["workbench_commit"],
        "mods": mods,
        "waves": max_release["waves"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in PINNED:
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = assemble(args.max, args.deja, args.chord, args.fm4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
