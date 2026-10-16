import hashlib, json, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import max_builder as b
class BuilderTests(unittest.TestCase):
    def test_manifest_is_source_patch_data(self):
        data=json.loads((ROOT/"resources/max-1.0-manifest.json").read_text())
        self.assertEqual(data["stock_sha256"],"8e2488f462c4a5656396a895f113bcd415e9900fa8709340dccf45d4cb9ed19e")
        self.assertEqual(data["golden_sha256"],"7cb4bfd3da4af9c417ae812ec205036a85a430f3be62263cf58e6ae31df2c093")
        self.assertEqual([m["name"] for m in data["mods"]],["splash","dual-mono","modarea","vparams","master-comp","readable-values","beat-repeat","fx3","workbench-max"])
        self.assertNotIn(".syx",json.dumps(data).lower())
    def test_wrong_hash_stops_before_container_tool(self):
        with tempfile.TemporaryDirectory() as td:
            stock=Path(td)/"wrong.syx"; stock.write_bytes(b"not firmware")
            with self.assertRaisesRegex(b.BuildError,"official Syntakt OS 1.41"):
                b.build(stock,Path(td)/"out.syx")
            self.assertFalse((Path(td)/"out.syx").exists())
    def test_patch_guard_rejects_modified_stock(self):
        sections={3:bytearray(b"abcd"),7:bytearray(b"abcd")}
        p={"name":"x","os":"1.41","patches":[{"section":3,"addr":"0x40000400","len":2,"hex":"0102","expect_sha256":"0"*64}]}
        with self.assertRaisesRegex(b.BuildError,"patch guard"):
            b.apply(sections,[p])
    def test_patch_overlap_rejected(self):
        h=hashlib.sha256(b"ab").hexdigest()
        sections={3:bytearray(b"abcd"),7:bytearray(b"abcd")}
        mods=[{"name":"a","os":"1.41","patches":[{"section":3,"addr":"0x40000400","len":2,"hex":"0102","expect_sha256":h}]},{"name":"b","os":"1.41","patches":[{"section":3,"addr":"0x40000401","len":2,"hex":"0304","expect_sha256":hashlib.sha256(b"bc").hexdigest()}]}]
        with self.assertRaisesRegex(b.BuildError,"overlaps"):
            b.apply(sections,mods)
    def test_shlz_roundtrip(self):
        data=(b"MAX"*1000)+bytes(range(128))*5
        self.assertEqual(b.lz.decompress(b.lz.compress(data)),data)
if __name__=="__main__": unittest.main()
