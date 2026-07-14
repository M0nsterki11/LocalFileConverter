#include "generated_version.iss"

; IMPORTANT: Do not change this AppId after the first public installer.
; Changing it would create a separate installation instead of upgrading.
#define AppIdGuid "{{2B037AD6-19DE-43D9-9976-689D3202587F}"

[Setup]
AppId={#AppIdGuid}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\LocalFileConverter
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
OutputDir=..\installer_output
OutputBaseFilename={#AppSetupBaseName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

#if FileExists("..\resources\app_icon.ico")
SetupIconFile=..\resources\app_icon.ico
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Napravi precac na radnoj povrsini"; GroupDescription: "Precaci:"; Flags: checkedonce

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\LocalFileConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Local File Converter"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall Local File Converter"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Local File Converter"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Pokreni Local File Converter"; Flags: nowait postinstall skipifsilent

[Code]
function DetectLibreOffice(): Boolean;
begin
  Result :=
    FileExists(ExpandConstant('{pf}\LibreOffice\program\soffice.exe')) or
    FileExists(ExpandConstant('{pf32}\LibreOffice\program\soffice.exe')) or
    FileExists(ExpandConstant('{localappdata}\Programs\LibreOffice\program\soffice.exe'));
end;

function ShouldOfferLibreOffice(): Boolean;
begin
  { Disabled in phase 11A. See packaging\libreoffice_dependency.json. }
  Result := False;
end;

function DownloadPinnedLibreOffice(): Boolean;
begin
  Result := False;
end;

function VerifyLibreOfficeInstaller(): Boolean;
begin
  Result := False;
end;

function RunLibreOfficeInstaller(): Boolean;
begin
  Result := False;
end;

function DetectSofficeAfterInstall(): Boolean;
begin
  Result := DetectLibreOffice();
end;

function InitializeSetup(): Boolean;
begin
  { Keep LocalFileConverter installation independent from LibreOffice in phase 11A. }
  Result := True;
end;
