# Запуск LiteLLM-прокси (API-окно и вообще любой запуск на этой машине).
# Использование: pwsh -File gateway\run_proxy.ps1  (или двойной клик из проводника)
# Делает три обязательных вещи (гигиена CLAUDE.md п.2 + урок 2026-07-12):
#   1) cwd = gateway/ (колбэк-импорты cwd-относительные);
#   2) ключи из gateway\.env в окружение (litellm сам .env НЕ читает);
#   3) PYTHONUTF8=1 (без него litellm-баннер падает на cp1251-консоли:
#      UnicodeEncodeError в click.echo, Application startup failed).
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Get-Content .env | ForEach-Object {
    $name, $value = $_ -split '=', 2
    if ($name -and $value) {
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}
$Host.UI.RawUI.WindowTitle = 'API-WINDOW PROXY (litellm :4000)'
Write-Host ''
Write-Host '=== ПРОКСИ ЗАПУСКАЕТСЯ: старт занимает ~10-15 секунд ===' -ForegroundColor Cyan
Write-Host 'Жди строку "Uvicorn running on http://0.0.0.0:4000" - ТОЛЬКО тогда порт открыт.' -ForegroundColor Cyan
Write-Host 'До неё идут баннер LITELLM и жёлтые WARNING про cost map - это НОРМА, не ошибка.' -ForegroundColor Cyan
Write-Host 'НЕ закрывай это окно, пока нужно API-окно. Проверка готовности - в другом окне:' -ForegroundColor Cyan
Write-Host '    Invoke-RestMethod http://localhost:4000/health/liveliness' -ForegroundColor DarkGray
Write-Host ''
litellm --config config.yaml
