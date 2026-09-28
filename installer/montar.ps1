# Monta dist\Radar3D (tudo que o instalador copia) a partir do repositório.
# Uso (na raiz do repo, Windows, depois de `npm ci`):  pwsh installer\montar.ps1 -Versao 1.0.0
param(
    [Parameter(Mandatory = $true)][string]$Versao,
    [string]$NodeVersao = "",
    [string]$UvVersao = "0.8.17"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$raiz = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $raiz "dist\Radar3D"
$tmp = Join-Path $raiz "dist\tmp"
Remove-Item -Recurse -Force (Join-Path $raiz "dist") -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $dist, $tmp, (Join-Path $dist "runtime") | Out-Null

# 1. Telas: build standalone do Next (só precisa do node.exe para rodar).
Push-Location (Join-Path $raiz "frontend")
$env:RADAR_STANDALONE = "1"
npm run build
if ($LASTEXITCODE -ne 0) { throw "npm run build falhou" }
Pop-Location
$front = Join-Path $dist "frontend"
Copy-Item -Recurse (Join-Path $raiz "frontend\.next\standalone") $front
Copy-Item -Recurse (Join-Path $raiz "frontend\.next\static") (Join-Path $front ".next\static")
Copy-Item -Recurse (Join-Path $raiz "frontend\public") (Join-Path $front "public")
if (-not (Test-Path (Join-Path $front "server.js"))) { throw "server.js não foi gerado" }

# 2. Backend: código e o lock (as bibliotecas são baixadas na primeira execução pelo uv).
$back = Join-Path $dist "backend"
New-Item -ItemType Directory -Force $back | Out-Null
Copy-Item -Recurse (Join-Path $raiz "backend\app") (Join-Path $back "app")
foreach ($f in "pyproject.toml", "uv.lock", ".python-version") { Copy-Item (Join-Path $raiz "backend\$f") $back }
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $back | Remove-Item -Recurse -Force

# 3. Runtime: node.exe (última 22.x LTS, se não for passada) e uv.exe (versão fixa).
if (-not $NodeVersao) {
    $NodeVersao = ((Invoke-RestMethod "https://nodejs.org/dist/index.json") |
        Where-Object { $_.version -like "v22.*" } | Select-Object -First 1).version.TrimStart("v")
}
Write-Host "Node $NodeVersao, uv $UvVersao"
$nodeZip = Join-Path $tmp "node.zip"
Invoke-WebRequest "https://nodejs.org/dist/v$NodeVersao/node-v$NodeVersao-win-x64.zip" -OutFile $nodeZip
Expand-Archive $nodeZip -DestinationPath $tmp
Copy-Item (Join-Path $tmp "node-v$NodeVersao-win-x64\node.exe") (Join-Path $dist "runtime\node.exe")
$uvZip = Join-Path $tmp "uv.zip"
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$UvVersao/uv-x86_64-pc-windows-msvc.zip" -OutFile $uvZip
Expand-Archive $uvZip -DestinationPath (Join-Path $tmp "uv")
Copy-Item (Join-Path $tmp "uv\uv.exe") (Join-Path $dist "runtime\uv.exe")

# 4. Lançadores, versão e leia-me.
Copy-Item (Join-Path $PSScriptRoot "Radar3D.cmd"), (Join-Path $PSScriptRoot "Parar.cmd") $dist
Set-Content -Path (Join-Path $dist "VERSION") -Value $Versao -NoNewline -Encoding ascii
Copy-Item (Join-Path $PSScriptRoot "LEIA-ME.txt") $dist
Remove-Item -Recurse -Force $tmp
Write-Host "dist\Radar3D pronto (versão $Versao)"
