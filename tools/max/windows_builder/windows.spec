# Windows 10/11 packaging: UCRT and APISet DLLs are supplied by the OS.
# See tools/max/release_1_0/RUNTIME_REDISTRIBUTION.md for source evidence.
from pathlib import Path
import sys

root = Path(SPECPATH)
a = Analysis(
    [str(root / 'app.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'resources'), 'resources')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)

def os_runtime(name):
    name = Path(name).name.lower()
    return name == 'ucrtbase.dll' or name.startswith(('api-ms-win-', 'ext-ms-win-'))

removed = [entry for entry in a.binaries if os_runtime(entry[0])]
a.binaries = [entry for entry in a.binaries if not os_runtime(entry[0])]
print('Excluded Windows OS runtime DLLs:', len(removed))
for name, source, kind in a.binaries:
    if name.lower().endswith('.dll') and not Path(source).resolve().is_relative_to(Path(sys.base_prefix).resolve()):
        raise RuntimeError('Runtime DLL outside the documented Python installation: ' + source)

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Syntakt-MAX-1.0-Builder', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[],
    runtime_tmpdir=None, console=False, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None, codesign_identity=None,
    entitlements_file=None,
)
