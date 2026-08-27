<#
.SYNOPSIS
    Inicia Chrome com CDP na porta 9222 e abre o dev server do BlazesBot no agent-browser.
    Mantém o Chrome rodando em background para comandos subsequentes.

.DESCRIPTION
    Workaround para o agent-browser no Windows: o daemon não consegue lançar Chrome
    diretamente (exit code 21). Este script inicia o Chrome manualmente com --remote-debugging-port=9222
    e configura o viewport 1200x800 (tamanho real da WebView2).

.EXAMPLE
    .\test-web.ps1                    # Inicia tudo
    .\test-web.ps1 -Build             # Faz build antes (npm run build)
    .\test-web.ps1 -Dist              # Abre dist/index.html em vez do dev server
    .\test-web.ps1 -Stop              # Para o Chrome/CDP
#>

param(
    [switch]$Build,       # Faz npm run build antes
    [switch]$Dist,        # Usa dist/index.html (file://) em vez de dev server
    [switch]$Stop,        # Para o Chrome/CDP
    [switch]$NoSnapshot,  # Não tira snapshot inicial
    [switch]$NoWait       # Não espera ENTER (para uso em npm scripts/CI)
)

$ErrorActionPreference = "Stop"

$ProjectRoot = "D:\Versoes do Bot\BlazesBot22 - Copia"
$ChromeExe = "C:\Users\bruno\.agent-browser\browsers\chrome-152.0.7977.42\chrome.exe"
$ChromeProfile = "C:\temp\chrome-profile-blazesbot"
$CDPPort = 9222
$DevServerUrl = "http://localhost:5173"
$DistUrl = "file:///" + ($ProjectRoot.Replace("\", "/")) + "/dist/index.html"

function Test-CDPReady {
    # Usa curl.exe (mais confiável que Invoke-WebRequest no PowerShell)
    $result = curl.exe -s -f --max-time 2 "http://localhost:$CDPPort/json/version" 2>$null
    return $LASTEXITCODE -eq 0
}

function Get-ChromeCDPProcess {
    # Usa WMI/CIM para pegar CommandLine completo (Get-Process não funciona bem)
    Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" |
    Where-Object { $_.CommandLine -match "remote-debugging-port=$CDPPort" } |
    Select-Object -First 1 -ExpandProperty ProcessId
}

function Start-ChromeCDP {
    Write-Host "Iniciando Chrome com CDP na porta $CDPPort..." -ForegroundColor Cyan

    # Verifica se já tem Chrome rodando na porta
    if (Test-CDPReady) {
        Write-Host "Chrome já está rodando na porta $CDPPort" -ForegroundColor Green
        return $true
    }

    if (-not (Test-Path $ChromeExe)) {
        Write-Host "Chrome não encontrado em: $ChromeExe" -ForegroundColor Red
        Write-Host "   Rode: agent-browser install" -ForegroundColor Yellow
        exit 1
    }

    # Cria diretório do perfil
    if (-not (Test-Path $ChromeProfile)) {
        New-Item -ItemType Directory -Path $ChromeProfile -Force | Out-Null
    }

    # Inicia Chrome em background
    $chromeArgs = @(
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--remote-debugging-port=$CDPPort",
        "--user-data-dir=$ChromeProfile",
        "--window-size=1200,800"
    )

    if ($Dist) {
        $chromeArgs += $DistUrl
    } else {
        $chromeArgs += $DevServerUrl
    }

    $process = Start-Process -FilePath $ChromeExe -ArgumentList $chromeArgs -PassThru -WindowStyle Hidden
    Write-Host "   Chrome PID: $($process.Id)" -ForegroundColor Gray

    # Aguarda CDP ficar pronto
    Write-Host "Aguardando CDP ficar disponível..." -NoNewline
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-CDPReady) {
            Write-Host " OK" -ForegroundColor Green
            return $true
        }
        Write-Host "." -NoNewline -ForegroundColor Gray
        Start-Sleep -Milliseconds 500
    }
    Write-Host " TIMEOUT" -ForegroundColor Red
    return $false
}

function Stop-ChromeCDP {
    Write-Host "Parando Chrome/CDP..." -ForegroundColor Yellow
    $chromePid = Get-ChromeCDPProcess
    if ($chromePid) {
        Stop-Process -Id $chromePid -Force -ErrorAction SilentlyContinue
        # Aguarda processos filhos morrerem
        Start-Sleep -Milliseconds 500
        $remaining = Get-ChromeCDPProcess
        if (-not $remaining) {
            Write-Host "Chrome parado (PID $chromePid)" -ForegroundColor Green
        } else {
            Write-Host "Chrome principal parado, processos filhos podem permanecer" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Nenhum Chrome principal encontrado na porta $CDPPort" -ForegroundColor Gray
    }
}

function Setup-AgentBrowser {
    if ($NoWait) {
        # Em modo não-interativo, não roda comandos agent-browser (pipe fecha)
        Write-Host "Modo não-interativo: pule 'agent-browser --cdp 9222 set viewport 1200 800' manualmente se necessário" -ForegroundColor Gray
        return
    }

    Write-Host "Configurando agent-browser..." -ForegroundColor Cyan

    # Define viewport 1200x800 (tamanho oficial da WebView2)
    agent-browser --cdp $CDPPort set viewport 1200 800

    if (-not $NoSnapshot) {
        # Snapshot inicial para confirmar que tudo funciona
        Write-Host "Snapshot inicial:" -ForegroundColor Cyan
        agent-browser --cdp $CDPPort snapshot -i
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "=================================================================="
    Write-Host "  BlazesBot Web - Test Helper (agent-browser + CDP)"
    Write-Host "=================================================================="
    Write-Host "  Chrome rodando com CDP na porta 9222"
    Write-Host "  Viewport: 1200x800 (tamanho real da WebView2)"
    Write-Host "------------------------------------------------------------------"
    Write-Host "  Comandos uteis (rode em outro terminal):"
    Write-Host ""
    Write-Host "  # Snapshot elementos interativos"
    Write-Host "  agent-browser --cdp 9222 snapshot -i"
    Write-Host ""
    Write-Host "  # Clicar em aba (ex: @e6 = Estatisticas BC)"
    Write-Host "  agent-browser --cdp 9222 click @e6"
    Write-Host ""
    Write-Host "  # Screenshot anotado pagina inteira"
    Write-Host "  agent-browser --cdp 9222 screenshot --full --annotate"
    Write-Host ""
    Write-Host "  # Preencher campo Client.bat"
    Write-Host "  agent-browser --cdp 9222 fill @e23 \"C:\path\Client.bat\""
    Write-Host ""
    Write-Host "  # Ver logs do console"
    Write-Host "  agent-browser --cdp 9222 console"
    Write-Host ""
    Write-Host "  # Auditoria acessibilidade"
    Write-Host "  agent-browser --cdp 9222 a11y"
    Write-Host ""
    Write-Host "  # Para parar tudo:"
    Write-Host "  .\test-web.ps1 -Stop"
    Write-Host "=================================================================="
    Write-Host ""
}

# ============================================================
# MAIN
# ============================================================

Set-Location $ProjectRoot

if ($Stop) {
    Stop-ChromeCDP
    exit 0
}

if ($Build) {
    Write-Host "Buildando frontend..." -ForegroundColor Cyan
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build falhou" -ForegroundColor Red
        exit 1
    }
    Write-Host "Build OK" -ForegroundColor Green
}

if (-not $Dist -and -not (Test-Path "$ProjectRoot\node_modules")) {
    Write-Host "Instalando dependencias..." -ForegroundColor Cyan
    npm install
}

$ok = Start-ChromeCDP
if (-not $ok) { exit 1 }

Setup-AgentBrowser
Show-Help

Write-Host "Pronto! Chrome + CDP + agent-browser funcionando." -ForegroundColor Green

if ($NoWait) {
    Write-Host "Modo não-interativo: Chrome roda em background. Use 'test-web.ps1 -Stop' para parar." -ForegroundColor Yellow
    Write-Host "PID do Chrome principal: $(Get-ChromeCDPProcess)" -ForegroundColor Cyan
} else {
    Write-Host "   Mantenha esta janela aberta. Use outro terminal para comandos." -ForegroundColor Yellow
    Write-Host ""
    # Mantém o script vivo para o Chrome não morrer
    Read-Host "Pressione ENTER para parar o Chrome e sair"
    Stop-ChromeCDP
}