"""Selection-matrix and release-profile checks against official OS 1.41."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import modular_builder as modular


class ModularBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = modular.load_manifest()
        stock = os.environ.get("SYNTAKT_STOCK")
        if not stock:
            raise unittest.SkipTest("SYNTAKT_STOCK is not configured")
        cls.stock = Path(stock)
        if modular.digest_path(cls.stock) != cls.manifest["stock_sha256"]:
            raise AssertionError("stock fixture does not match the official OS 1.41 hash")
        tool = os.environ.get("EFT_BIN")
        if not tool:
            raise unittest.SkipTest("EFT_BIN is not configured")
        sys.path.insert(0, str(Path(os.environ["SYNTHACK_SOURCE"]) / "tools" / "unpack"))
        import eft
        cls.temp = tempfile.TemporaryDirectory(prefix="modular-test-")
        paths = eft.unpack(cls.stock, Path(cls.temp.name) / "stock", ids=[3, 7])
        cls.sections = {sid: path.read_bytes() for sid, path in paths.items()}

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def test_all_255_nonempty_feature_selections(self):
        keys = [key for key, _, _ in modular.FEATURES]
        results = {}
        for mask in range(1, 1 << len(keys)):
            selected = frozenset(key for index, key in enumerate(keys) if mask & (1 << index))
            result = modular.validate_static(selected, self.sections, self.manifest)
            self.assertGreater(result["patches"], 0)
            self.assertLessEqual(result["modarea_bytes"], 0xfff0)
            results[mask] = result
        self.assertEqual(len(results), 255)
        self.assertEqual(results[255]["mods"], [mod["name"] for mod in self.manifest["mods"]])

    def test_preset_dependencies_and_layout(self):
        self.assertEqual(modular.resolve(modular.PRESETS["FM4 ONLY"], self.manifest)[0]["name"], "modarea")
        self.assertEqual(modular.resolve(modular.PRESETS["Original MAX 1.0"], self.manifest)[0]["name"], "splash")
        full = modular.validate_static(modular.PRESETS["MAX FULL + FM4"], self.sections, self.manifest)
        self.assertIn("fm4", full["mods"])
        self.assertIn("sy-chord", full["mods"])
        self.assertIn("deja-vu", full["mods"])

    def test_empty_or_unknown_selection_rejected(self):
        with self.assertRaises(modular.BuildError):
            modular.resolve((), self.manifest)
        with self.assertRaises(modular.BuildError):
            modular.resolve(("arp",), self.manifest)

    def test_stock_preimage_and_overlap_guards(self):
        bad = dict(self.sections)
        altered = bytearray(bad[3])
        altered[0x400004b2 - modular.base.LOAD] ^= 1
        bad[3] = bytes(altered)
        with self.assertRaises(modular.BuildError):
            modular.validate_static(modular.PRESETS["FM4 ONLY"], bad, self.manifest)
        duplicate = dict(self.manifest)
        duplicate["mods"] = [dict(mod) for mod in self.manifest["mods"]]
        fm4 = next(mod for mod in duplicate["mods"] if mod["name"] == "fm4")
        fm4["patches"] = [*fm4["patches"], fm4["patches"][0]]
        with self.assertRaises(modular.BuildError):
            modular.validate_static(modular.PRESETS["FM4 ONLY"], self.sections, duplicate)

    def test_fm4_loader_matches_compiled_addresses(self):
        mods = modular.resolve(modular.PRESETS["FM4 ONLY"], self.manifest)
        loader = next(mod for mod in mods if mod["name"] == "modarea")
        fm4 = next(mod for mod in mods if mod["name"] == "fm4")
        self.assertEqual(loader["layout"]["ram"].lower(), "0x444e38d0")
        self.assertTrue(any(p.get("hex", "").lower() == "444e8944"
                            for p in fm4["patches"] if p.get("what") == "FM4 SYN knob descriptor"))
        self.assertEqual(self.manifest["golden_sha256"]["MAX FULL + FM4"],
                         "3eaaf21ca0ed137eba14e321269d69383769da9210f818d0ad1db24356696d89")

    @unittest.skipUnless(os.environ.get("SYNTAKT_BUILD_PROFILES") == "1", "slow firmware profile build not requested")
    def test_real_preset_builds_and_custom_wave_only(self):
        helper = Path(os.environ["EFT_BIN"])
        original = modular.base.eft_path
        modular.base.eft_path = lambda: helper
        try:
            with tempfile.TemporaryDirectory(prefix="modular-build-test-") as name:
                work = Path(name)
                for profile, selection in [*modular.PRESETS.items(),
                                           ("CUSTOM CHORD", frozenset({"sy_chord"}))]:
                    image = work / (profile.replace(" ", "_") + ".syx")
                    report = modular.build(self.stock, image, selection)
                    self.assertEqual(report["output_sha256"], modular.digest_path(image))
                    self.assertGreaterEqual(report["boot_margin"], 4096)
                    self.assertTrue(image.with_suffix(".json").is_file())
                    expected = self.manifest["golden_sha256"].get(profile)
                    if expected:
                        self.assertEqual(report["output_sha256"], expected)
                    print(profile, report["output_sha256"], report["boot_margin"])
        finally:
            modular.base.eft_path = original


if __name__ == "__main__":
    unittest.main()
