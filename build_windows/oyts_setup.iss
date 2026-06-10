; ============================================================
;  OYTS — Inno Setup 6.3+ kurulum script'i
; ============================================================
;  Önce PyInstaller ile dist/OYTS/ üretilmiş olmalı.
;  Sonra bu script Inno Setup ile derlenir → OYTS-Setup.exe
;
;  Inno Setup Compiler'ı aç → bu .iss dosyasını yükle → F9 (Compile)
;  Çıktı: build_windows\Output\OYTS-Setup-1.0.exe
; ============================================================

#define MyAppName "OYTS"
#define MyAppFullName "OYTS - Otonom Yangin Tespit Sistemi"
#define MyAppVersion "3.1.3"
#define MyAppPublisher "Piri Reis Universitesi - BIP 2012"
#define MyAppExeName "Baslat.exe"

[Setup]
AppId={{D4F8B2A1-5C3E-4A6D-9B1F-2E8C7D4A6B5E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppFullName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
; "lowest" — admin gerekmez, kullanıcı dizinine kurulur
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=OYTS-Setup-{#MyAppVersion}
; SetupIconFile kaldirildi — icon.ico repo'da yok, build patliyordu.
; Icon eklemek istersen build_windows/icon.ico koy ve asagi satirin yorumunu kaldir:
; SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
WizardImageFile=
ShowLanguageDialog=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne k&ısayol oluştur"; GroupDescription: "Ek k&ısayollar:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "&Hızlı başlatmaya kısayol oluştur"; GroupDescription: "Ek k&ısayollar:"; Flags: unchecked

[Files]
; PyInstaller çıktısı: dist\Baslat\ dizini
Source: "..\dist\Baslat\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; README + lisans
Source: "README_WINDOWS.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
; İkon
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Tek kısayol — Baslat.exe çift tıklanınca Tkinter launcher penceresi açılır,
; kullanıcı webcam / simulasyon / durdur seçimini oradan yapar.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Comment: "OYTS launcher — webcam / simulasyon penceresi"
Name: "{group}\Beni Oku"; Filename: "{app}\README_WINDOWS.txt"
Name: "{group}\Kaldır {#MyAppName}"; Filename: "{uninstallexe}"

Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} launcher'i simdi ac"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\kayitlar"
Type: filesandordirs; Name: "{app}\runs"
