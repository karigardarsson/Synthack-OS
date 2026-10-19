$ErrorActionPreference = 'Stop'
$nativeHere = Split-Path -Parent $MyInvocation.MyCommand.Path
function Get-ShortPath([string]$Path) {
  $command = 'for %I in ("{0}") do @echo %~sI' -f $Path
  $short = (& cmd.exe /d /c $command).Trim()
  if (!$short -or !(Test-Path -LiteralPath $short)) {
    throw "Unable to obtain an ASCII-compatible Windows path for: $Path"
  }
  return $short
}

$shortHere = Get-ShortPath $nativeHere
$vendor = Join-Path $shortHere 'vendor\elektron-firmware-tool'
$gcc = 'C:\msys64\ucrt64\bin\gcc.exe'
if (!(Test-Path $gcc)) { throw 'MSYS2 UCRT64 GCC is required to package the bundled MIT container tool.' }
$python = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$savedPath = $env:PATH
$savedTemp = $env:TEMP
$savedTmp = $env:TMP
try {
  $nativeTemp = Join-Path $env:LOCALAPPDATA 'Temp\syntakt-max-modular-builder'
  New-Item -ItemType Directory -Force -Path $nativeTemp | Out-Null
  $env:TEMP = Get-ShortPath $nativeTemp
  $env:TMP = $env:TEMP
  $env:PATH = 'C:\msys64\ucrt64\bin;' + $env:PATH
  $sources = Get-ChildItem $vendor -Filter '*.c' | ForEach-Object FullName
  & $gcc -std=c11 -O2 -Wall -Wextra -o (Join-Path $shortHere 'resources\elektron-firmware-tool.exe') $sources
  if ($LASTEXITCODE -ne 0) { throw 'Failed to build elektron-firmware-tool.exe' }
  Push-Location -LiteralPath $nativeHere
  try {
    & $python -m PyInstaller --noconfirm --clean (Join-Path $nativeHere 'windows.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to package the Windows builder' }
  } finally { Pop-Location }
} finally {
  $env:PATH = $savedPath
  $env:TEMP = $savedTemp
  $env:TMP = $savedTmp
}
