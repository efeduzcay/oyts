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
#define MyAppVersion "3.1.1"
#define MyAppPublisher "Piri Reis Universitesi - BIP 2012"
#define MyAppExeName "OYTS.exe"

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
SetupIconFile=icon.ico
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
; PyInstaller çıktısı: dist\OYTS\ dizini
Source: "..\dist\OYTS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; README + lisans
Source: "README_WINDOWS.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme
; İkon
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName} (Simulasyon)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--source synthetic"; IconFilename: "{app}\icon.ico"; Comment: "Yangin sahnesi sentetik olarak — donanim gerekmez"
Name: "{group}\{#MyAppName} (Webcam)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--source webcam"; IconFilename: "{app}\icon.ico"; Comment: "Bilgisayar kamerasi — cakmak/mum testi"
Name: "{group}\{#MyAppName} (ESP32-CAM)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--source esp32"; IconFilename: "{app}\icon.ico"; Comment: "ESP32-CAM Wi-Fi stream — gercek robot"
Name: "{group}\Beni Oku"; Filename: "{app}\README_WINDOWS.txt"
Name: "{group}\Kaldır {#MyAppName}"; Filename: "{uninstallexe}"

Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--source synthetic"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} simülasyonu hemen baslat"; Flags: nowait postinstall skipifsilent; Parameters: "--source synthetic"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\kayitlar"
Type: filesandordirs; Name: "{app}\runs"
