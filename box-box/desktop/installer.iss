; Instalador do Box Box para Windows (Inno Setup 6).
; Gerado por build-windows.ps1 a partir de dist\BoxBox.
; Instala por usuário (sem pedir administrador).

#ifndef AppVersion
  #define AppVersion "2.5.1"
#endif

[Setup]
AppId={{6B40081A-FBEC-4065-A69A-4CE35884809E}
AppName=Box Box
AppVersion={#AppVersion}
AppPublisher=Box Box
DefaultDirName={localappdata}\Programs\Box Box
DefaultGroupName=Box Box
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=BoxBox-Setup-{#AppVersion}
SetupIconFile=boxbox.ico
UninstallDisplayIcon={app}\BoxBox.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Fecha o Box Box aberto antes de substituir os arquivos (ver [Code])
CloseApplications=force
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "dist\BoxBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Box Box"; Filename: "{app}\BoxBox.exe"
Name: "{group}\Box Box (no navegador)"; Filename: "{app}\BoxBox.exe"; Parameters: "--browser"
Name: "{group}\Pasta de dados do Box Box"; Filename: "{localappdata}\BoxBox"
Name: "{userdesktop}\Box Box"; Filename: "{app}\BoxBox.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BoxBox.exe"; Description: "Abrir o Box Box agora"; Flags: nowait postinstall skipifsilent

; As sessões baixadas ficam em %LOCALAPPDATA%\BoxBox e não são apagadas na
; desinstalação, para não perder downloads ao atualizar.

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /T /IM BoxBox.exe"; Flags: runhidden; RunOnceId: "FecharBoxBox"

[Code]
// Um Box Box ainda aberto (às vezes só na bandeja ou em segundo plano)
// trava os arquivos e a atualização falha com "arquivo em uso".
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM BoxBox.exe', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
  Result := '';
end;
