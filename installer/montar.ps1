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

# 4. WebView2 (a janela própria do app): DLLs do pacote oficial da Microsoft no NuGet, versão
#    e conteúdo fixos. O motor em si (WebView2 Runtime) já vem no Windows 10/11.
$wv2Versao = "1.0.4258.31"
$wv2Hash = "56F7F4B8BF9AEE4B8EFEFBBDD4F67D5F74EBD1B100ED0806DA71BF76AF481AA9"
$wv2Zip = Join-Path $tmp "webview2.zip"
Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/$wv2Versao/microsoft.web.webview2.$wv2Versao.nupkg" -OutFile $wv2Zip
if ((Get-FileHash $wv2Zip -Algorithm SHA256).Hash -ne $wv2Hash) { throw "O pacote do WebView2 baixado não é o esperado" }
$wv2 = Join-Path $tmp "webview2"
Expand-Archive $wv2Zip -DestinationPath $wv2
$wv2Core = Join-Path $wv2 "lib\net462\Microsoft.Web.WebView2.Core.dll"
$wv2Forms = Join-Path $wv2 "lib\net462\Microsoft.Web.WebView2.WinForms.dll"
Copy-Item $wv2Core, $wv2Forms $dist
foreach ($arq in "x64", "arm64") {
    $destino = Join-Path $dist "runtimes\win-$arq\native"
    New-Item -ItemType Directory -Force $destino | Out-Null
    Copy-Item (Join-Path $wv2 "runtimes\win-$arq\native\WebView2Loader.dll") $destino
}

# 5. Lançador sem janelas de console (Radar3D.exe, C# no csc do .NET Framework), versão e leia-me.
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$icone = Join-Path $PSScriptRoot "radar3d.ico"
$saida = Join-Path $dist "Radar3D.exe"
$fonte = Join-Path $PSScriptRoot "lancador\Radar3D.cs"
$cscArgs = @("/nologo", "/target:winexe", "/optimize+", "/langversion:5", "/win32icon:$icone",
          "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll", "/r:$wv2Core", "/r:$wv2Forms",
          "/out:$saida", $fonte)
$log = & $csc @cscArgs 2>&1
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $saida)) {
    Write-Host "::error title=csc::$(($log | Out-String) -replace "`r?`n", '%0A')"
    throw "csc falhou ao compilar o lançador"
}
Copy-Item (Join-Path $PSScriptRoot "Parar.cmd"), (Join-Path $PSScriptRoot "radar3d.ico") $dist
Set-Content -Path (Join-Path $dist "VERSION") -Value $Versao -NoNewline -Encoding ascii
Copy-Item (Join-Path $PSScriptRoot "LEIA-ME.txt") $dist
Remove-Item -Recurse -Force $tmp
Write-Host "dist\Radar3D pronto (versão $Versao)"
