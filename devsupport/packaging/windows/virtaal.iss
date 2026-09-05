; Inno Setup script for Virtaal's Windows installer.
;
; Compile with (from the repo root, after build_standalone.ps1 has produced
; dist\virtaal\):
;   iscc /DMyAppVersion=1.0.0 devsupport\packaging\windows\virtaal.iss
; (or via build_installer.ps1, which reads the version from
; virtaal/__version__.py itself rather than needing it typed in by hand.)
;
; File associations avoid claiming extensions unprompted or
; system-wide:
;   - opt-in (an unchecked [Tasks] entry - a bare install makes zero
;     registry changes)
;   - HKCU (per-user, no admin elevation needed), not HKCR
;   - a small, curated extension list, not an auto-enumerated one

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Virtaal"
#define MyAppPublisher "Translate"
#define MyAppURL "https://github.com/translate/virtaal"
#define MyAppExeName "virtaal.exe"
; Relative to this .iss file's own directory.
#define DistDir "..\..\..\dist\virtaal"
#define IconsDir "..\..\..\share\icons"

[Setup]
AppId={{6249E57B-4B71-4E69-8174-F261A0DD9DAE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Per-user by default (no admin elevation prompt) - matches the HKCU-only
; file-association approach below; a machine-wide install is available via
; the installer's own "install for all users" option if Inno Setup's
; automatic privilege handling decides it's needed, but isn't required.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\..\dist\installer
OutputBaseFilename=virtaal-{#MyAppVersion}-setup
SetupIconFile={#IconsDir}\virtaal.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; ChangesAssociations is needed either way for Explorer to notice new
; associations - the actual registry writes below only happen if the
; "fileassoc" task was checked, so a plain click-through install makes
; none regardless of this setting.
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "fileassoc"; Description: "Associate Virtaal with translation file types (.po, .xlf, .tmx, ...)"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; One ProgID per format (not one shared ProgID for all 12 extensions) -
; each gets its own label. Labels follow the same convention
; share/mime/packages/virtaal-mimetype.xml.in already uses on Linux
; (translatable file -> "XXX Translation File", TM -> "XXX Translation
; Memory", compiled -> "XXX Message File"), reusing its exact wording
; for the 5 formats both lists cover.
;
; All gated on the "fileassoc" task and under HKCU (per-user, no
; elevation) rather than HKCR (machine-wide) - see the file header.
; uninsdeletevalue/uninsdeletekey mean uninstalling cleanly removes
; exactly what this added, nothing more.
;
; Extension list is deliberately curated (translate-toolkit's
; factory.supported_files() is NOT auto-enumerated here) - excludes a
; few rarely-used extensions likely to clash with other software.
[Registry]
Root: HKCU; Subkey: "Software\Classes\Virtaal.PoFile"; ValueType: string; ValueName: ""; ValueData: "PO Translation File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.PoFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.PoFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.po"; ValueType: string; ValueData: "Virtaal.PoFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.XliffFile"; ValueType: string; ValueName: ""; ValueData: "XLIFF Translation File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.XliffFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.XliffFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.xlf"; ValueType: string; ValueData: "Virtaal.XliffFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.xliff"; ValueType: string; ValueData: "Virtaal.XliffFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.SdlXliffFile"; ValueType: string; ValueName: ""; ValueData: "SDL XLIFF Translation File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.SdlXliffFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.SdlXliffFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.sdlxliff"; ValueType: string; ValueData: "Virtaal.SdlXliffFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.GettextMoFile"; ValueType: string; ValueName: ""; ValueData: "Gettext Message File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.GettextMoFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.GettextMoFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mo"; ValueType: string; ValueData: "Virtaal.GettextMoFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.gmo"; ValueType: string; ValueData: "Virtaal.GettextMoFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.QmFile"; ValueType: string; ValueName: ""; ValueData: "Qt Message File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.QmFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.QmFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.qm"; ValueType: string; ValueData: "Virtaal.QmFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.TbxFile"; ValueType: string; ValueName: ""; ValueData: "TBX Glossary"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.TbxFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.TbxFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.tbx"; ValueType: string; ValueData: "Virtaal.TbxFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.TmxFile"; ValueType: string; ValueName: ""; ValueData: "TMX Translation Memory"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.TmxFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.TmxFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.tmx"; ValueType: string; ValueData: "Virtaal.TmxFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.QphFile"; ValueType: string; ValueName: ""; ValueData: "Qt Phrase Book"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.QphFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.QphFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.qph"; ValueType: string; ValueData: "Virtaal.QphFile"; Tasks: fileassoc; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Classes\Virtaal.FluentFile"; ValueType: string; ValueName: ""; ValueData: "Fluent Translation File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.FluentFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.FluentFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.ftl"; ValueType: string; ValueData: "Virtaal.FluentFile"; Tasks: fileassoc; Flags: uninsdeletevalue

; .ts also means MPEG-2 Transport Stream, likely already claimed by a
; video app - a secondary "Edit with Virtaal" verb instead of a
; default association, via SystemFileAssociations (Windows' own
; mechanism for a right-click/"Open with" action that doesn't touch
; whatever already owns the extension's default).
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ts\shell\VirtaalEdit"; ValueType: string; ValueName: ""; ValueData: "Edit with Virtaal"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ts\shell\VirtaalEdit\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ts\shell\VirtaalEdit\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc
