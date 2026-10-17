$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$eft = Join-Path $here 'vendor\elektron-firmware-tool'
$gcc = 'C:\msys64\ucrt64\bin\gcc.exe'
if (!(Test-Path $gcc)) { throw 'MSYS2 UCRT64 GCC is required to package the bundled MIT container tool.' }
$python = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$savedPath = $env:PATH
try {
  # gcc starts cc1.exe; its UCRT64 runtime DLLs must be discoverable by that child.
  $env:PATH = 'C:\msys64\ucrt64\bin;' + $env:PATH
  $sources = Get-ChildItem $eft -Filter '*.c' | ForEach-Object FullName
  & $gcc -std=c11 -O2 -Wall -Wextra -o (Join-Path $here 'resources\elektron-firmware-tool.exe') $sources
  if ($LASTEXITCODE -ne 0) { throw 'Failed to build elektron-firmware-tool.exe' }
  Push-Location $here
  try {
    & $python -m PyInstaller --noconfirm --clean (Join-Path $here 'windows.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to package the Windows builder' }
  } finally {
    Pop-Location
  }
} finally {
  $env:PATH = $savedPath
}
