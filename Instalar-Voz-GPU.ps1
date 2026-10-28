$ErrorActionPreference="Stop"
Set-Location $PSScriptRoot
$python=Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Execute IAExpert.cmd primeiro." -ForegroundColor Yellow
    exit 1
}
Write-Host "Voz Chatterbox: instalação OPCIONAL, grande download e GPU NVIDIA CUDA obrigatória." -ForegroundColor Cyan
Write-Host "O modelo será baixado no primeiro uso; pode utilizar vários GB de disco/VRAM."
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Write-Host "Não encontrei nvidia-smi. O Chatterbox GPU não está disponível nesta máquina." -ForegroundColor Red
    exit 1
}
& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
if ($LASTEXITCODE -ne 0) {exit 1}
Write-Host "Instalando PyTorch com CUDA 12.8..."
& $python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) {exit 1}
Write-Host "Instalando Chatterbox..."
& $python -m pip install chatterbox-tts
if ($LASTEXITCODE -ne 0) {exit 1}
& $python -c "import torch; print('CUDA:',torch.cuda.is_available()); assert torch.cuda.is_available()"
exit $LASTEXITCODE
