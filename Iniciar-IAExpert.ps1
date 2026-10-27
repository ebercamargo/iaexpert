$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "IAExpert - Assistente de Voz Local" -ForegroundColor Cyan

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python Launcher nao encontrado. Instale Python 3.11 (64-bit) com o launcher py." -ForegroundColor Yellow
    Write-Host "https://www.python.org/downloads/windows/"
    exit 1
}

& py -3.11 -c "import sys; assert sys.maxsize > 2**32" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.11 de 64 bits nao encontrado. Instale Python 3.11 (64-bit)." -ForegroundColor Yellow
    exit 1
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama nao foi encontrado. Instale pelo site oficial, abra-o e execute este arquivo novamente." -ForegroundColor Yellow
    Write-Host "https://ollama.com/download/windows"
    Write-Host "Opcional: winget install --id Ollama.Ollama --exact"
    exit 1
}

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2 | Out-Null
} catch {
    Write-Host "Iniciando servidor Ollama..."
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 3 | Out-Null
    } catch {
        Write-Host "O Ollama nao respondeu em http://127.0.0.1:11434. Abra o Ollama e tente novamente." -ForegroundColor Red
        exit 1
    }
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Criando ambiente Python isolado..."
    & py -3.11 -m venv ".venv"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$requirementsHash = (Get-FileHash "requirements.txt" -Algorithm SHA256).Hash
$marker = Join-Path $PSScriptRoot ".venv\iaexpert-requirements.sha256"
$oldHash = if (Test-Path $marker) { (Get-Content $marker -Raw).Trim() } else { "" }
if ($requirementsHash -ne $oldHash) {
    Write-Host "Instalando dependencias da aplicacao (primeira execucao pode demorar)..."
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $venvPython -m pip install -r "requirements.txt"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Set-Content -Path $marker -Value $requirementsHash
}

$availableModels = & ollama list
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nao foi possivel consultar os modelos do Ollama." -ForegroundColor Red
    exit 1
}
if (-not ($availableModels | Select-String -Pattern "^\s*qwen3\.5:2b\s")) {
    Write-Host "Baixando o modelo local qwen3.5:2b. O arquivo ocupa varios GB..." -ForegroundColor Cyan
    & ollama pull "qwen3.5:2b"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Nao foi possivel baixar o modelo de IA." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "Abrindo o IAExpert..." -ForegroundColor Green
& $venvPython -m iaexpert
exit $LASTEXITCODE
