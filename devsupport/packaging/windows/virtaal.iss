; Inno Setup script for Virtaal's Windows installer.
;
; Compile with (from the repo root, after build_standalone.ps1 has produced
; dist\virtaal\):
;   iscc /DMyAppVersion=1.0.0 devsupport\packaging\windows\virtaal.iss
; (or via build_installer.ps1, which reads the version from
; virtaal/__version__.py itself rather than needing it typed in by hand.)
;
; File-association design directly fixes the old #894 bug (ISSUE_TRIAGE.md):
; the previous, now-fully-removed InnoSetup script wrote HKEY_CLASSES_ROOT
; (machine-wide, needs admin) associations for every format
; translate-toolkit happened to recognise, unconditionally, with no
; installer checkbox - including generic extensions (OmegaT Glossary's
; .utf8/.tab) that weren't really Virtaal's to claim, which is the most
; likely actual source of the original user complaint. This version:
;   - is opt-in (an unchecked [Tasks] entry - a bare install makes zero
;     registry changes)
;   - uses HKCU (per-user, no admin elevation needed), not HKCR
;   - uses a small, deliberately curated extension list, not an
;     auto-enumerated one

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

; One [Registry] block per associated extension, all gated on the
; "fileassoc" task and all under HKCU (per-user, no elevation) rather than
; HKCR (machine-wide) - see the file header. uninsdeletevalue means
; uninstalling cleanly removes exactly what this added, nothing more.
;
; Extension list is deliberately curated (translate-toolkit's
; factory.supported_files() is NOT auto-enumerated here) - .po,
; .xlf/.xliff/.sdlxliff, .mo/.gmo, .qm, .tbx, .tmx, .ts, .qph, .ftl, .wxl.
; Notably absent: OmegaT Glossary's generic .utf8/.tab - the most likely
; actual offender in the original #894 complaint, and not really Virtaal's
; to claim regardless.
[Registry]
Root: HKCU; Subkey: "Software\Classes\Virtaal.TranslationFile"; ValueType: string; ValueName: ""; ValueData: "Virtaal Translation File"; Tasks: fileassoc; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Virtaal.TranslationFile\DefaultIcon"; ValueType: string; ValueData: "{app}\share\icons\x-translation.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\Virtaal.TranslationFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

#define Ext1 ".po"
#define Ext2 ".xlf"
#define Ext3 ".xliff"
#define Ext4 ".sdlxliff"
#define Ext5 ".mo"
#define Ext6 ".gmo"
#define Ext7 ".qm"
#define Ext8 ".tbx"
#define Ext9 ".tmx"
#define Ext10 ".ts"
#define Ext11 ".qph"
#define Ext12 ".ftl"

Root: HKCU; Subkey: "Software\Classes\{#Ext1}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext2}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext3}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext4}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext5}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext6}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext7}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext8}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext9}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext10}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext11}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\{#Ext12}"; ValueType: string; ValueData: "Virtaal.TranslationFile"; Tasks: fileassoc; Flags: uninsdeletevalue
; .wxl (Windows Installer XML localization) deliberately omitted from the
; numbered list above despite being in the design doc's original scope -
; .wxl is WiX's own format extension and Windows Installer XML has nothing
; to do with translation file review; kept out pending confirmation this
; was ever a real, intentional Virtaal association rather than inherited
; noise from the old auto-enumerated list.
