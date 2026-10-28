$ErrorActionPreference="Continue"
Set-Location $PSScriptRoot
Write-Host "Diagnóstico GPU — IAExpert" -ForegroundColor Cyan
Write-Host "Placas identificadas pelo Windows:"
Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | Format-Table
Write-Host "NVIDIA CUDA:"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
} else {
    Write-Host "nvidia-smi não instalado: pode ser AMD, Intel ou NVIDIA sem CUDA."
}
$py=Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $py) {
    & $py -c "import ctranslate2;print('Whisper CUDA:', ctranslate2.get_supported_compute_types('cuda'))" 2>&1
    & $py -c "import torch;print('PyTorch CUDA:', torch.cuda.is_available())" 2>&1
}
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Local do modelo no Ollama (CPU/GPU):"
    & ollama ps
}
Write-Host "Tempos das últimas interações:"
$log=Join-Path $env:LOCALAPPDATA "IAExpert\performance.log"
if (Test-Path $log) {
    Get-Content $log -Tail 8
} else {
    Write-Host "Nenhum tempo registrado até agora."
}
