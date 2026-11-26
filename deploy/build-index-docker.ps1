# Сборка полного индекса (OCR + BGE-M3) внутри образа web.
# Требует: Docker, каталог data/manuals с PDF, при первом запуске — скачивание BGE (~2 ГБ в HF cache внутри контейнера).
param(
    [switch]$SkipVectors,
    [switch]$SkipOcr
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$Root\data\manuals")) {
    Write-Error "Нет $Root\data\manuals — скопируйте PDF по app/manuals.py"
}
Set-Location $Root

docker compose build web

$ocrFlag = if ($SkipOcr) { "" } else { "--ocr" }
$vecFlag = if ($SkipVectors) { "--skip-vectors" } else { "" }

docker compose run --rm -v "${Root}/data:/app/data" web python -m app.rag $ocrFlag $vecFlag
Write-Host "Готово. Синхронизация на VPS — deploy/DATA-SYNC.md"