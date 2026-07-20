#include "generated_version.iss"
#include "generated_libreoffice_dependency.iss"

; IMPORTANT: Do not change this AppId after the first public installer.
; Changing it would create a separate installation instead of upgrading.
#define AppIdGuid "{{2B037AD6-19DE-43D9-9976-689D3202587F}"

[Setup]
AppId={#AppIdGuid}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\MyFileConverter
DefaultGroupName={#AppName}
DisableDirPage=no
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
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
SetupIconFile=..\resources\app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\MyFileConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SOURCE_CODE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\PyMuPDF-COPYING"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{group}\MyFile Converter"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\License"; Filename: "{app}\LICENSE"
Name: "{group}\Third-Party Notices"; Filename: "{app}\THIRD_PARTY_NOTICES.txt"
Name: "{group}\Source Code Information"; Filename: "{app}\SOURCE_CODE.md"
Name: "{group}\Uninstall MyFile Converter"; Filename: "{uninstallexe}"; IconFilename: "{app}\{#AppExeName}"
Name: "{autodesktop}\MyFile Converter"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch MyFile Converter"; Flags: nowait postinstall skipifsilent

[Code]
const
  LibreOfficeVersion = '{#LibreOfficeVersion}';
  LibreOfficeFilename = '{#LibreOfficeFilename}';
  LibreOfficeDownloadUrl = '{#LibreOfficeDownloadUrl}';
  LibreOfficeSHA256 = '{#LibreOfficeSHA256}';
  LibreOfficeExpectedSofficePath = '{#LibreOfficeExpectedSofficePath}';

var
  LibreOfficePage: TInputOptionWizardPage;
  LibreOfficeDownloadPage: TDownloadWizardPage;

function LibreOfficeDownloadsEnabled(): Boolean;
begin
#if LibreOfficeEnabled
  Result := True;
#else
  Result := False;
#endif
end;

function IsSofficeExecutable(Path: String): Boolean;
var
  FileName: String;
begin
  FileName := ExtractFileName(Path);
  Result :=
    FileExists(Path) and
    (
      (CompareText(FileName, 'soffice.exe') = 0) or
      (CompareText(FileName, 'soffice.com') = 0) or
      (CompareText(FileName, 'soffice') = 0)
    );
end;

function DetectLibreOfficeCandidate(Candidate: String): Boolean;
begin
  Result := False;

  if Candidate = '' then
    Exit;

  if IsSofficeExecutable(Candidate) then begin
    Log('LibreOffice found: ' + Candidate);
    Result := True;
    Exit;
  end;

  if DirExists(Candidate) then begin
    if IsSofficeExecutable(AddBackslash(Candidate) + 'soffice.exe') then begin
      Log('LibreOffice found: ' + AddBackslash(Candidate) + 'soffice.exe');
      Result := True;
      Exit;
    end;

    if IsSofficeExecutable(AddBackslash(Candidate) + 'program\soffice.exe') then begin
      Log('LibreOffice found: ' + AddBackslash(Candidate) + 'program\soffice.exe');
      Result := True;
      Exit;
    end;
  end;
end;

function DetectLibreOfficeFromRegistryValue(RootKey: Integer; Subkey, ValueName: String): Boolean;
var
  Candidate: String;
begin
  Result := False;

  if RegQueryStringValue(RootKey, Subkey, ValueName, Candidate) then
    Result := DetectLibreOfficeCandidate(Candidate);
end;

function DetectLibreOfficeFromRegistry(): Boolean;
begin
  Result :=
    DetectLibreOfficeFromRegistryValue(
      HKCU,
      'Software\LocalFileConverter\Local File Converter\libreoffice',
      'executable_path'
    ) or
    DetectLibreOfficeFromRegistryValue(
      HKLM64,
      'SOFTWARE\LibreOffice\UNO',
      'InstallPath'
    ) or
    DetectLibreOfficeFromRegistryValue(
      HKLM32,
      'SOFTWARE\LibreOffice\UNO',
      'InstallPath'
    ) or
    DetectLibreOfficeFromRegistryValue(
      HKLM64,
      'SOFTWARE\The Document Foundation\LibreOffice\UNO',
      'InstallPath'
    ) or
    DetectLibreOfficeFromRegistryValue(
      HKLM32,
      'SOFTWARE\The Document Foundation\LibreOffice\UNO',
      'InstallPath'
    ) or
    DetectLibreOfficeFromRegistryValue(
      HKLM64,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\LibreOffice',
      'InstallLocation'
    ) or
    DetectLibreOfficeFromRegistryValue(
      HKLM32,
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\LibreOffice',
      'InstallLocation'
    );
end;

function DetectLibreOfficeFromPath(): Boolean;
var
  Candidate: String;
begin
  Candidate := FileSearch('soffice.exe', GetEnv('PATH'));

  if Candidate = '' then
    Candidate := FileSearch('soffice.com', GetEnv('PATH'));

  if Candidate = '' then
    Candidate := FileSearch('soffice', GetEnv('PATH'));

  Result := DetectLibreOfficeCandidate(Candidate);
end;

function DetectLibreOffice(): Boolean;
begin
  Result :=
    DetectLibreOfficeFromRegistry() or
    DetectLibreOfficeFromPath() or
    DetectLibreOfficeCandidate(ExpandConstant('{pf64}\LibreOffice\program\soffice.exe')) or
    DetectLibreOfficeCandidate(ExpandConstant('{pf32}\LibreOffice\program\soffice.exe')) or
    DetectLibreOfficeCandidate(ExpandConstant('{pf}\LibreOffice\program\soffice.exe')) or
    DetectLibreOfficeCandidate(ExpandConstant('{localappdata}\Programs\LibreOffice\program\soffice.exe')) or
    DetectLibreOfficeCandidate(LibreOfficeExpectedSofficePath);
end;

function ShouldOfferLibreOffice(): Boolean;
begin
  Result := False;

  if not LibreOfficeDownloadsEnabled() then
    Exit;

  if WizardSilent then
    Exit;

  if DetectLibreOffice() then
    Exit;

  Result := True;
end;

function UserSelectedLibreOfficeInstall(): Boolean;
begin
  Result := False;

  if not ShouldOfferLibreOffice() then
    Exit;

  if LibreOfficePage <> nil then
    Result := LibreOfficePage.Values[0];
end;

function LibreOfficeInstallerPath(): String;
begin
  Result := ExpandConstant('{tmp}\' + LibreOfficeFilename);
end;

procedure CleanupLibreOfficeInstaller();
var
  InstallerPath: String;
begin
  InstallerPath := LibreOfficeInstallerPath();

  if FileExists(InstallerPath) then begin
    if DeleteFile(InstallerPath) then
      Log('Removed temporary LibreOffice MSI: ' + InstallerPath)
    else
      Log('Could not remove temporary LibreOffice MSI: ' + InstallerPath);
  end;
end;

function DownloadPinnedLibreOffice(): Boolean;
var
  Error: String;
begin
  Result := False;

  LibreOfficeDownloadPage.Clear;
  LibreOfficeDownloadPage.Add(
    LibreOfficeDownloadUrl,
    LibreOfficeFilename,
    LibreOfficeSHA256
  );
  LibreOfficeDownloadPage.Show;

  try
    try
      LibreOfficeDownloadPage.Download;
      Result := True;
    except
      CleanupLibreOfficeInstaller();

      if LibreOfficeDownloadPage.AbortedByUser then begin
        Log('LibreOffice download cancelled by user.');
        SuppressibleMsgBox(
          'LibreOffice download was cancelled. MyFile Converter will still be installed.'#13#13 +
          'Office conversions can use Microsoft Office desktop applications. LibreOffice can be installed later as a fallback.',
          mbInformation,
          MB_OK,
          IDOK
        );
      end else begin
        Error := Format('%s: %s', [LibreOfficeDownloadPage.LastBaseNameOrUrl, GetExceptionMessage]);
        Log('LibreOffice download failed: ' + Error);
        SuppressibleMsgBox(
          'LibreOffice could not be downloaded or verified.'#13#13 +
          Error + #13#13 +
          'MyFile Converter will still be installed without LibreOffice.',
          mbCriticalError,
          MB_OK,
          IDOK
        );
      end;
    end;
  finally
    LibreOfficeDownloadPage.Hide;
  end;
end;

function VerifyLibreOfficeInstaller(): Boolean;
var
  InstallerPath: String;
  ActualSHA256: String;
begin
  Result := False;
  InstallerPath := LibreOfficeInstallerPath();

  if not FileExists(InstallerPath) then begin
    Log('LibreOffice MSI was not found for verification: ' + InstallerPath);
    Exit;
  end;

  ActualSHA256 := GetSHA256OfFile(InstallerPath);

  if CompareText(ActualSHA256, LibreOfficeSHA256) = 0 then begin
    Log('LibreOffice MSI SHA-256 verification passed.');
    Result := True;
    Exit;
  end;

  Log(
    'LibreOffice MSI SHA-256 verification failed. Expected ' +
    LibreOfficeSHA256 + ', got ' + ActualSHA256
  );
  CleanupLibreOfficeInstaller();
  SuppressibleMsgBox(
    'Security check failed for the downloaded LibreOffice installer.'#13#13 +
    'The downloaded MSI will not be started and has been removed.'#13#13 +
    'MyFile Converter will still be installed without LibreOffice.',
    mbCriticalError,
    MB_OK,
    IDOK
  );
end;

function RunLibreOfficeInstaller(): Boolean;
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  Result := False;
  InstallerPath := LibreOfficeInstallerPath();

  if not VerifyLibreOfficeInstaller() then
    Exit;

  Log('Starting LibreOffice MSI through msiexec: ' + InstallerPath);

  if not Exec(
    ExpandConstant('{sys}\msiexec.exe'),
    '/i "' + InstallerPath + '"',
    '',
    SW_SHOWNORMAL,
    ewWaitUntilTerminated,
    ResultCode
  ) then begin
    Log('Could not start msiexec for LibreOffice. Error code: ' + IntToStr(ResultCode));
    SuppressibleMsgBox(
      'LibreOffice installer could not be started.'#13#13 +
      'MyFile Converter will still be installed. You can install LibreOffice later.',
      mbError,
      MB_OK,
      IDOK
    );
    Exit;
  end;

  if (ResultCode = 0) or (ResultCode = 3010) then begin
    Log('LibreOffice MSI completed with code ' + IntToStr(ResultCode));
    Result := True;
    Exit;
  end;

  if ResultCode = 1602 then begin
    Log('LibreOffice MSI was cancelled by user.');
    SuppressibleMsgBox(
      'LibreOffice installation was cancelled. MyFile Converter will still be installed.'#13#13 +
      'Office conversions can use Microsoft Office desktop applications. LibreOffice can be installed later as a fallback.',
      mbInformation,
      MB_OK,
      IDOK
    );
  end else begin
    Log('LibreOffice MSI finished with non-success code ' + IntToStr(ResultCode));
    SuppressibleMsgBox(
      'LibreOffice installation did not complete successfully.'#13#13 +
      'MyFile Converter will still be installed. You can install LibreOffice later.'#13#13 +
      'LibreOffice installer exit code: ' + IntToStr(ResultCode),
      mbError,
      MB_OK,
      IDOK
    );
  end;
end;

function DetectSofficeAfterInstall(): Boolean;
begin
  Result := DetectLibreOffice();

  if Result then
    SuppressibleMsgBox(
      'LibreOffice was installed and soffice.exe was found.',
      mbInformation,
      MB_OK,
      IDOK
    )
  else
    SuppressibleMsgBox(
      'LibreOffice setup finished, but soffice.exe was not found automatically.'#13#13 +
      'DOCX, PPTX and XLSX to PDF conversion will not work until LibreOffice is installed or selected manually in the app settings.',
      mbInformation,
      MB_OK,
      IDOK
    );
end;

procedure ProcessOptionalLibreOfficeInstall();
begin
  if not UserSelectedLibreOfficeInstall() then
    Exit;

  if not DownloadPinnedLibreOffice() then
    Exit;

  try
    if RunLibreOfficeInstaller() then
      DetectSofficeAfterInstall();
  finally
    CleanupLibreOfficeInstaller();
  end;
end;

procedure InitializeWizard();
begin
  LibreOfficePage := CreateInputOptionPage(
    wpSelectDir,
    'Optional LibreOffice support',
    'Install LibreOffice as an Office conversion fallback?',
    'Microsoft Office desktop applications are used when available. LibreOffice remains an optional fallback for DOCX, PPTX and XLSX to PDF conversion.',
    False,
    False
  );
  LibreOfficePage.Add(
    'Download and install LibreOffice ' + LibreOfficeVersion + ' (approximately 355 MB)'
  );
  LibreOfficePage.Values[0] := False;

  LibreOfficeDownloadPage := CreateDownloadPage(
    SetupMessage(msgWizardPreparing),
    SetupMessage(msgPreparingDesc),
    nil
  );
  LibreOfficeDownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

procedure DeinitializeSetup();
begin
  CleanupLibreOfficeInstaller();
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  if (LibreOfficePage <> nil) and (PageID = LibreOfficePage.ID) then
    Result := not ShouldOfferLibreOffice()
  else
    Result := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = wpReady then
    ProcessOptionalLibreOfficeInstall();
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;
