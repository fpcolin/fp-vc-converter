; Inno Setup script for the Flooring Partners VendorCafe CSV Converter.
; Compile with:  iscc build\installer.iss
; Requires Inno Setup 6+ (https://jrsoftware.org/isdl.php)

#define AppName        "VendorCafe CSV Converter"
; CI passes /DAppVersion=x.y.z; the fallback keeps local builds working.
#ifndef AppVersion
  #define AppVersion   "2.0.0"
#endif
#define AppPublisher   "Flooring Partners"
#define AppExeName     "FPVendorCafeConverter.exe"

[Setup]
; AppId is the identity Windows uses to recognise an upgrade. NEVER change it
; between releases, or every version installs side by side instead of replacing
; the previous one. This GUID is unique to this program - it must not match the
; QR Code Generator's, or the two would try to upgrade each other.
AppId={{AB4F23FC-7020-4D60-9CFC-3EB453F9A9BA}

AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppPublisher} {#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoVersion={#AppVersion}

; Per-user install into %LOCALAPPDATA%\Programs. This is the important choice:
; it means updates need no admin rights, so the in-app updater can run silently
; without a UAC prompt.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppPublisher}\{#AppName}
DefaultGroupName={#AppPublisher}
DisableProgramGroupPage=yes

OutputDir=..\dist\installer
OutputBaseFilename=FPVendorCafeConverter-{#AppVersion}-setup
SetupIconFile=..\src\fp.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppPublisher} {#AppName}

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

; Shut down a running copy so its files can be replaced, instead of demanding
; a reboot. This is what makes silent self-update work reliably.
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; The whole PyInstaller onedir output. recursesubdirs picks up _internal\.
Source: "..\dist\FPVendorCafeConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Interactive install: offer a checkbox on the Finished page.
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; Silent install: relaunch automatically. A silent run is almost always the
; self-updater, and the user was using the program a moment ago. Pass
; /NORELAUNCH to suppress this for unattended deployment.
Filename: "{app}\{#AppExeName}"; Flags: nowait; Check: ShouldRelaunch

[UninstallDelete]
; Remove the generated config on uninstall. Drop this section if you would
; rather preserve user settings across an uninstall/reinstall cycle.
Type: filesandordirs; Name: "{localappdata}\{#AppPublisher}\{#AppName}"

[Code]
function ShouldRelaunch: Boolean;
var
  I: Integer;
begin
  { Only silent installs reach here; interactive ones use the Finished page. }
  Result := WizardSilent;
  if Result then
    for I := 1 to ParamCount do
      if CompareText(ParamStr(I), '/NORELAUNCH') = 0 then
      begin
        Result := False;
        Exit;
      end;
end;
