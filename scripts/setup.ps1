# Windows setup: creates .venv, installs PyTorch (CPU by default) and the pinned laya.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # CPU
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Cuda    # NVIDIA GPU (CUDA 12.8 build)
param([switch]$Cuda)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3 -m venv .venv }  # needs Python 3.10+ (py -0 lists installed versions)
$py = '.\.venv\Scripts\python.exe'
& $py -m pip install --upgrade pip
if ($Cuda) {
  & $py -m pip install torch --index-url https://download.pytorch.org/whl/cu128
} else {
  & $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
}
& $py -m pip install -r requirements.txt
& $py -I -c "import laya; print('laya', laya.__version__)"
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host 'Created .env from .env.example' }
