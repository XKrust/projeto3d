; Instalador do Radar 3D (Inno Setup 6). Montado pelo GitHub Actions
; (.github/workflows/instalador.yml) a partir de dist\Radar3D (ver montar.ps1).
; Instala só para o usuário atual (não pede administrador).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\Radar3D"
#endif

[Setup]
AppId={{7B3C2A41-5E2D-4C8B-9F1A-3D6E8B2C4A90}
AppName=Radar 3D
AppVersion={#AppVersion}
AppPublisher=Radar 3D
DefaultDirName={localappdata}\Programs\Radar3D
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Radar3D-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Radar 3D
UninstallDisplayIcon={app}\Radar3D.exe
SetupIconFile=radar3d.ico
CloseApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; Atualização: tira os arquivos da versão anterior (os dados ficam em %LOCALAPPDATA%\Radar3D).
Type: filesandordirs; Name: "{app}\frontend"
Type: filesandordirs; Name: "{app}\backend"
Type: files; Name: "{app}\Radar3D.cmd"
Type: files; Name: "{autoprograms}\Parar Radar 3D.lnk"

[Icons]
Name: "{autoprograms}\Radar 3D"; Filename: "{app}\Radar3D.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\Fechar o Radar 3D"; Filename: "{app}\Radar3D.exe"; Parameters: "--sair"; WorkingDir: "{app}"
Name: "{autodesktop}\Radar 3D"; Filename: "{app}\Radar3D.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Radar3D.exe"; Description: "Abrir o Radar 3D agora"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\Radar3D.exe"; Parameters: "--sair"; Flags: runhidden waituntilterminated; RunOnceId: "FecharRadar3D"
Filename: "{app}\Parar.cmd"; Flags: runhidden waituntilterminated; RunOnceId: "PararRadar3D"

[UninstallDelete]
; O Python e o ambiente baixados saem junto; os dados (data\: banco, análises, logs) ficam,
; para uma reinstalação não perder nada.
Type: filesandordirs; Name: "{localappdata}\Radar3D\venv"
Type: filesandordirs; Name: "{localappdata}\Radar3D\python"
Type: filesandordirs; Name: "{localappdata}\Radar3D\uv-cache"
Type: filesandordirs; Name: "{app}"

[Code]
// Antes de instalar por cima de uma versão aberta, desliga o Radar 3D (senão o node.exe e o
// Python ficam travando os arquivos).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  if FileExists(ExpandConstant('{app}\Radar3D.exe')) then
    Exec(ExpandConstant('{app}\Radar3D.exe'), '--sair', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if FileExists(ExpandConstant('{app}\Parar.cmd')) then
    Exec(ExpandConstant('{app}\Parar.cmd'), '', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
