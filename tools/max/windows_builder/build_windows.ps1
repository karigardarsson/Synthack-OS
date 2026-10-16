$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$eft = Join-Path $here 'vendor\elektron-firmware-tool'
$gcc = 'C:\msys64\ucrt64\bin\gcc.exe'
if (!(Test-Path $gcc)) { throw 'MSYS2 UCRT64 GCC is required to package the bundled MIT container tool.' }
$sources = Get-ChildItem $eft -Filter '*.c' | ForEach-Object FullName
& $gcc -std=c11 -O2 -Wall -Wextra -o (Join-Path $here 'resources\elektron-firmware-tool.exe') $sources
if ($LASTEXITCODE -ne 0) { throw 'Failed to build elektron-firmware-tool.exe' }
Push-Location $here
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Syntakt-MAX-1.0-Builder --add-data "$here\resources;resources" --paths $here (Join-Path $here 'app.py')
Pop-Location
