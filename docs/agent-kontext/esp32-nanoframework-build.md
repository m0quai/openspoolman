# ESP32-S3 / .NET nanoFramework – Build- und Toolchain-Dokumentation

## Letzte Aktualisierung

**2026-08-20 18:00 (lokale Uhrzeit)**

## Zweck

Diese Dokumentation beschreibt den auf dem Entwicklungsrechner tatsächlich verwendeten und bis zum CMake-Configure-Schritt erfolgreich verifizierten Aufbau der .NET-nanoFramework-Toolchain für den ESP32-S3 des OpenSpoolMan-NFC-Projekts.

Zielhardware:

- ESP32-S3
- 16 MB Flash
- 8 MB PSRAM
- USB-UART über CH343
- verwendeter COM-Port: `COM8`
- C# / .NET nanoFramework

Für das OpenSpoolMan-NFC-Projekt wird aktuell ein eigener nanoFramework-Target ohne PSRAM-Nutzung aufgebaut:

`ESP32_S3_N16_NOPSRAM`

Grund: Die offiziellen `ESP32_S3_OCTAL`-Images booten auf dem vorhandenen Board bis zur nanoFramework-Anwendung, stürzen anschließend jedoch reproduzierbar mit `IllegalInstruction` ab. Deshalb wird für dieses Projekt zunächst ein eigener, konservativer Build ohne PSRAM-Unterstützung verwendet.

---

# 1. Benötigte Software und Tools

## 1.1 Visual Studio 2022

Benötigt für:

- Entwicklung des C#-nanoFramework-Projekts
- Device Explorer
- Deployment und Debugging der späteren Managed-Anwendung

Zusätzlich installieren:

- **.NET nanoFramework Extension** aus dem Visual Studio Marketplace

Der Device Explorer ist danach in Visual Studio verfügbar.

---

## 1.2 Git

Benötigt zum Klonen von:

- `nf-interpreter`
- ESP-IDF
- Git-Submodulen

Prüfung:

```powershell
git --version
```

---

## 1.3 Python

Verwendete Installation:

```text
C:\Program Files\Python313\python.exe
```

Verwendete Python-Version im Build:

```text
3.13.15
```

Prüfung:

```powershell
python --version
```

Zusätzlich benötigte Python-Pakete:

### kconfiglib

Wird vom nanoFramework-Kconfig-System benötigt.

Installation:

```powershell
python -m pip install kconfiglib
```

Falls ein vollständiger Python-Pfad verwendet wird, muss PowerShell mit dem Call-Operator `&` gestartet werden:

```powershell
& "C:\Program Files\Python313\python.exe" -m pip install kconfiglib
```

### pyserial

Nur für Diagnose/seriellen Boot-Log erforderlich.

Installation:

```powershell
python -m pip install pyserial
```

Seriellen Monitor starten:

```powershell
python -m serial.tools.miniterm COM8 115200
```

Beenden:

```text
Ctrl+]
```

---

## 1.4 nanoff

Benötigt zum:

- Erkennen von COM-Ports
- Erkennen von nanoFramework-Geräten
- Flashen fertiger nanoFramework-Firmware
- Lesen der ESP32-Chipdetails

Verwendete Version:

```text
.NET nanoFramework Firmware Flasher 2.5.162
```

Prüfung:

```powershell
nanoff --version
```

COM-Ports anzeigen:

```powershell
nanoff --listports
```

nanoFramework-Geräte suchen:

```powershell
nanoff --listdevices --verbosity diag
```

Chipdetails lesen:

```powershell
nanoff --serialport COM8 --devicedetails
```

Der funktionierende USB-UART-Port des Boards ist aktuell:

```text
COM8
```

Die USB-Schnittstelle meldet sich über einen CH343-Adapter.

---

## 1.5 CMake

Benötigt für die Konfiguration des nativen nanoFramework-Builds.

Installation unter Windows:

```powershell
winget install Kitware.CMake
```

Danach neue PowerShell öffnen.

Prüfung:

```powershell
cmake --version
```

Im funktionierenden Configure-Lauf wurde verwendet:

```text
CMake 3.30.2
```

---

## 1.6 Ninja

Benötigt als Build-Generator.

Installation:

```powershell
winget install Ninja-build.Ninja
```

Danach neue PowerShell öffnen.

Prüfung:

```powershell
ninja --version
```

Verifiziert:

```text
1.13.2
```

---

## 1.7 SRecord / srec_cat

nanoFramework benötigt `srec_cat` während der CMake-Konfiguration bzw. Firmware-Erzeugung.

Verwendeter Installationspfad:

```text
C:\nanoFramework\srecord\bin
```

Erwartete Datei:

```text
C:\nanoFramework\srecord\bin\srec_cat.exe
```

Prüfung:

```powershell
Test-Path C:\nanoFramework\srecord\bin\srec_cat.exe
```

Der Pfad wird beim Configure explizit übergeben:

```powershell
-DTOOL_SRECORD_PREFIX="C:/nanoFramework/srecord/bin"
```

Wichtig: In CMake-Parametern Forward Slashes `/` verwenden.

---

## 1.8 ESP-IDF 5.5.4

Der aktuelle `nf-interpreter`-Stand erwartet:

```text
IDF_TAG = v5.5.4
```

Das wurde im Repository über `azure-pipelines.yml` verifiziert.

Installation:

```powershell
cd C:\nanoFramework

git clone -b v5.5.4 --recursive https://github.com/espressif/esp-idf.git

cd C:\nanoFramework\esp-idf

.\install.ps1 esp32s3
```

Danach die ESP-IDF-Umgebung in der aktuellen PowerShell aktivieren:

```powershell
cd C:\nanoFramework\esp-idf
.\export.ps1
```

Verwendeter ESP-IDF-Pfad:

```text
C:\nanoFramework\esp-idf
```

Im CMake-Aufruf:

```powershell
-DESP32_IDF_PATH="C:/nanoFramework/esp-idf"
```

Nach `export.ps1` wird der S3-Compiler gefunden.

Verifizierter Compiler:

```text
xtensa-esp32s3-elf-gcc.exe
```

Beispiel des tatsächlich erkannten Pfads:

```text
C:\Users\MichaelKuhlen\.espressif\tools\xtensa-esp-elf\esp-14.2.0_20260121\xtensa-esp-elf\bin\xtensa-esp32s3-elf-gcc.exe
```

Compiler-Version im erfolgreichen Configure-Lauf:

```text
GNU 14.2.0
```

Prüfung:

```powershell
Get-Command xtensa-esp32s3-elf-gcc
xtensa-esp32s3-elf-gcc --version
```

---

# 2. nanoFramework Interpreter Repository

Arbeitsordner:

```text
C:\nanoFramework\nf-interpreter
```

Repository klonen:

```powershell
cd C:\nanoFramework

git clone https://github.com/nanoframework/nf-interpreter.git

cd C:\nanoFramework\nf-interpreter
```

Git-Submodule unbedingt initialisieren:

```powershell
git submodule update --init --recursive
```

Prüfen:

```powershell
git submodule status
```

Dies ist notwendig, weil unter anderem `targets-community` als Submodule eingebunden ist.

---

# 3. Lokale CMake-Konfigurationsdateien

Ein frisch geklontes Repository enthält Vorlagen, aber nicht alle lokalen Benutzerdateien.

## 3.1 user-tools-repos.json

Erstellen:

```powershell
Copy-Item `
  .\config\user-tools-repos.TEMPLATE.json `
  .\config\user-tools-repos.json
```

Der lokale Preset-Name muss zum vom Repository erwarteten Namen passen.

Insbesondere den Template-Eintrag:

```text
user-tools-repos-local
```

auf:

```text
user-tools-repos
```

anpassen.

---

## 3.2 user-prefs.json

Erstellen:

```powershell
Copy-Item `
  .\config\user-prefs.TEMPLATE.json `
  .\config\user-prefs.json
```

Die meisten nicht für ESP32 benötigten Platzhalter können unverändert bleiben, solange die tatsächlich verwendeten Werte über CMake explizit gesetzt werden.

---

# 4. Eigenen Target ohne PSRAM anlegen

Ausgangsbasis:

```text
targets\ESP32\defconfig\ESP32_S3_OCTAL_defconfig
```

Neue Datei:

```text
targets\ESP32\defconfig\ESP32_S3_N16_NOPSRAM_defconfig
```

Wesentliche Änderung:

Die Octal-PSRAM-spezifische Reservierung wird entfernt:

```text
CONFIG_ESP32_RESERVE_SPIRAM_IDF_ALLOCATION_BYTES=1048576
```

wird nicht übernommen.

Statt:

```text
CONFIG_SDK_CONFIG_FILE="sdkconfig.default_octal_ble.esp32s3"
```

wird verwendet:

```text
CONFIG_SDK_CONFIG_FILE="sdkconfig.default.esp32s3"
```

Die Datei `sdkconfig.default.esp32s3` wurde im Repository unter folgendem Pfad verifiziert:

```text
targets\ESP32\_IDF\sdkconfig.default.esp32s3
```

Der Target behält unter anderem:

```text
CONFIG_NF_WP_TRANSPORT_USB_CDC_OR_SERIAL=y
CONFIG_TARGET_BOARD="ESP32_S3"
CONFIG_TARGET_SERIES="ESP32_S3"
```

---

# 5. CMake-Preset für den eigenen Target

Der neue ConfigurePreset heißt:

```text
ESP32_S3_N16_NOPSRAM
```

Er basiert auf:

```text
xtensa-esp32s3-preset
```

und verwendet:

```text
NF_TARGET_DEFCONFIG=targets/ESP32/defconfig/ESP32_S3_N16_NOPSRAM_defconfig
```

Zusätzlich existiert ein gleichnamiger BuildPreset.

Prüfen, ob der Target registriert ist:

```powershell
cmake --list-presets
```

In der Liste muss erscheinen:

```text
ESP32_S3_N16_NOPSRAM
```

---

# 6. ESP-IDF-Umgebung vor dem Build aktivieren

In einer neuen PowerShell zuerst:

```powershell
cd C:\nanoFramework\esp-idf
.\export.ps1
```

Danach:

```powershell
cd C:\nanoFramework\nf-interpreter
```

Prüfen:

```powershell
Get-Command xtensa-esp32s3-elf-gcc
```

Erst wenn der Compiler gefunden wird, mit CMake fortfahren.

---

# 7. Erfolgreich verifizierter Configure-Befehl

Dieser Befehl wurde erfolgreich ausgeführt:

```powershell
cmake --preset ESP32_S3_N16_NOPSRAM `
  -DTOOL_SRECORD_PREFIX="C:/nanoFramework/srecord/bin" `
  -DESP32_IDF_PATH="C:/nanoFramework/esp-idf"
```

Erfolgreiches Ergebnis:

```text
-- Configuring done
-- Generating done
-- Build files have been written to: C:/nanoFramework/nf-interpreter/build
```

Damit ist die komplette Toolchain bis einschließlich CMake-Konfiguration verifiziert.

Während dieses Laufs wurden erfolgreich erkannt:

- Python 3.13.15
- kconfiglib
- ESP-IDF 5.5.4
- ESP32-S3 GCC/G++ 14.2.0
- Ninja
- SRecord
- eigener Defconfig
- eigener ConfigurePreset
- ESP32-S3 Target
- nanoFramework Debug-Build

---

# 8. Build

Build starten mit:

```powershell
cmake --build --preset ESP32_S3_N16_NOPSRAM
```

Der Build läuft aktuell weit in den nativen nanoFramework-Build hinein und erzeugt bereits unter anderem die Partitionstabelle.

Beispiel:

```text
factory,app,factory,0x10000,1664K
deploy,data,132,0x1b0000,1984K
config,data,littlefs,0x3c0000,256K
```

---

# 9. Aktueller offener Build-Blocker

**Stand 2026-08-20 17:43: Der Build ist noch nicht vollständig erfolgreich.**

Er stoppt aktuell bei ungefähr:

```text
[1033/1287]
```

in:

```text
nanoFramework.Device.Bluetooth
```

Fehler:

```text
error: variable 'pkey' set but not used [-Werror=unused-but-set-variable]
cc1plus.exe: all warnings being treated as errors
```

Betroffene Datei:

```text
targets/ESP32/_nanoCLR/nanoFramework.Device.Bluetooth/
sys_dev_ble_native_nanoFramework_Device_Bluetooth_Security.cpp
```

Dies ist aktuell der nächste zu lösende Schritt.

Wichtig:

- Die Toolchain selbst ist aufgebaut.
- CMake-Konfiguration funktioniert.
- ESP-IDF wird korrekt verwendet.
- GCC/G++ funktionieren.
- Ninja startet den Build.
- Der Fehler ist jetzt ein echter C++-Compilerfehler im nanoFramework-Quellcode bzw. in der verwendeten Warnungs-/Compiler-Kombination und kein fehlendes Tool mehr.

Für das OpenSpoolMan-NFC-Projekt ist Bluetooth nicht erforderlich. Daher ist eine mögliche nächste Optimierung, Bluetooth aus dem eigenen `ESP32_S3_N16_NOPSRAM`-Defconfig zu entfernen, statt diesen Bluetooth-Quellcode für unser NFC-Projekt mitzubauen.

---

# 10. Flashen fertiger Firmware

Sobald der eigene Build vollständig erfolgreich ist, wird die erzeugte Firmware auf den ESP32-S3 über `COM8` geflasht.

Für offizielle nanoFramework-Images wurde bereits erfolgreich verifiziert, dass COM8 den ESP32-S3-ROM-Bootloader erreicht und Flashen funktioniert.

Beispiel des bereits funktionierenden Flashwegs:

```powershell
nanoff --target ESP32_S3_OCTAL `
  --update `
  --serialport COM8 `
  --masserase `
  --baud 115200
```

Dieser offizielle Octal-Build ist für das konkrete Board jedoch **nicht als endgültige Firmware geeignet**, weil die Runtime nach dem Boot mit `IllegalInstruction` abstürzt.

COM8 selbst und der Flashweg sind dagegen bestätigt.

---

# 11. Diagnosebefehle

## COM-Ports

```powershell
nanoff --listports
```

## nanoFramework-Geräte

```powershell
nanoff --listdevices --verbosity diag
```

## Chipdetails

```powershell
nanoff --serialport COM8 --devicedetails
```

## Bootlog

```powershell
python -m serial.tools.miniterm COM8 115200
```

Danach am ESP32-S3 kurz `RST` drücken.

---

# 12. Bekannte funktionierende Hardware-Erkennung

Über COM8 wurden folgende Hardwaredaten erfolgreich gelesen:

```text
ESP32-S3
Revision v0.2
16 MB Flash
8 MB PSRAM
40 MHz Crystal
```

Der Flashvorgang über COM8 und CH343 funktioniert zuverlässig.

---

# 13. Empfohlene Reihenfolge für einen neuen Entwicklungsrechner

1. Visual Studio 2022 installieren.
2. .NET nanoFramework Visual-Studio-Erweiterung installieren.
3. Git installieren.
4. Python installieren.
5. `kconfiglib` installieren.
6. optional `pyserial` für Diagnose installieren.
7. `nanoff` installieren.
8. CMake installieren.
9. Ninja installieren.
10. SRecord nach `C:\nanoFramework\srecord` installieren.
11. `nf-interpreter` klonen.
12. Git-Submodule initialisieren.
13. `user-tools-repos.json` aus Template erstellen.
14. `user-prefs.json` aus Template erstellen.
15. ESP-IDF **v5.5.4** inklusive Submodule klonen.
16. `ESP-IDF\install.ps1 esp32s3` ausführen.
17. Vor jedem Build `ESP-IDF\export.ps1` ausführen.
18. eigenen Target `ESP32_S3_N16_NOPSRAM` einrichten.
19. Preset mit `cmake --list-presets` prüfen.
20. CMake mit explizitem ESP-IDF- und SRecord-Pfad konfigurieren.
21. Build mit dem BuildPreset starten.
22. Nach erfolgreichem Build Firmware auf COM8 flashen.
23. Mit `nanoff --listdevices` prüfen, ob die Runtime sauber startet.
24. Erst danach Deployment/Debugging des C#-Projekts aus Visual Studio verwenden.

---

# 14. Projektentscheidung

Für das OpenSpoolMan-NFC-Projekt wird kein PSRAM benötigt.

Die geplanten Aufgaben des ESP32-S3 sind hauptsächlich:

- NTAG215/NFC lesen
- Hardware-UID erfassen
- NDEF-URL schreiben
- AMS-Slot erfassen
- Netzwerkkommunikation mit OpenSpoolMan
- Zuordnungsdaten übertragen

Daher wird Stabilität gegenüber der Nutzung der vorhandenen 8 MB PSRAM priorisiert.


# 15. Änderung 2026-08-20 18:00 – Bluetooth aus eigenem Target entfernen

## Ausgangslage

Der native Build des Targets `ESP32_S3_N16_NOPSRAM` erreicht den eigentlichen nanoFramework-C++-Build und läuft bis ungefähr Schritt `1033/1287`.

Der Build stoppt in:

```text
targets/ESP32/_nanoCLR/nanoFramework.Device.Bluetooth/
sys_dev_ble_native_nanoFramework_Device_Bluetooth_Security.cpp
```

Der verwendete GCC 14.2.0 meldet dort zwei nicht verwendete Variablen:

```text
error: variable 'pkey' set but not used [-Werror=unused-but-set-variable]
```

Da nanoFramework mit `-Werror` kompiliert, wird diese Warnung als Fehler behandelt und Ninja bricht den Build ab.

## Entscheidung

Bluetooth wird für den ESP32-S3 im OpenSpoolMan-NFC-Projekt nicht benötigt.

Der Bluetooth-/NimBLE-Code wird deshalb **nicht im nanoFramework-C++-Quellcode gepatcht**. Stattdessen wird Bluetooth im projektspezifischen Target `ESP32_S3_N16_NOPSRAM` vollständig deaktiviert.

Damit bleibt der nanoFramework-Upstream-Code unangetastet und der eigene Target enthält nur die für das Projekt tatsächlich benötigten Funktionen.

## Änderung am Defconfig

Datei:

```text
targets/ESP32/defconfig/ESP32_S3_N16_NOPSRAM_defconfig
```

Folgende Zeile entfernen:

```text
CONFIG_API_NANOFRAMEWORK_DEVICE_BLUETOOTH=y
```

Die SDK-Konfiguration bleibt:

```text
CONFIG_SDK_CONFIG_FILE="sdkconfig.default.esp32s3"
```

Es wird ausdrücklich **keine BLE-spezifische SDK-Konfiguration** verwendet.

## Build-Cache nach Änderung löschen

Nach der Änderung des Defconfig muss der bisherige Build-Cache vollständig entfernt werden:

```powershell
cd C:\nanoFramework\nf-interpreter

Remove-Item -Recurse -Force .\build
```

Damit wird verhindert, dass Komponenten aus der vorherigen Bluetooth-Konfiguration weiterverwendet werden.

## Neu konfigurieren

Vorher gegebenenfalls die ESP-IDF-Umgebung aktivieren:

```powershell
cd C:\nanoFramework\esp-idf
.\export.ps1

cd C:\nanoFramework\nf-interpreter
```

Danach:

```powershell
cmake --preset ESP32_S3_N16_NOPSRAM `
  -DTOOL_SRECORD_PREFIX="C:/nanoFramework/srecord/bin" `
  -DESP32_IDF_PATH="C:/nanoFramework/esp-idf"
```

Im Configure-Output muss anschließend Bluetooth als deaktiviert erscheinen, sinngemäß:

```text
Support for Bluetooth disabled
```

## Neu bauen

```powershell
cmake --build --preset ESP32_S3_N16_NOPSRAM
```

## Erwarteter Effekt

Durch die Änderung werden die für dieses Projekt nicht benötigten Bluetooth-/NimBLE-Native-Assemblies nicht mehr gebaut. Dadurch entfällt der aktuelle GCC-Fehler in `nanoFramework.Device.Bluetooth`.

Zusätzliche Vorteile:

- weniger unnötige Firmware-Komponenten,
- geringerer Flash-Bedarf,
- geringerer RAM-Bedarf,
- kein unnötiger NimBLE-Stack,
- weniger Abhängigkeiten,
- keine projektspezifische Änderung am nanoFramework-Bluetooth-C++-Code.

## Status

Die Änderung ist als nächster Build-Schritt festgelegt. Ob der vollständige Build danach fehlerfrei durchläuft, muss mit dem anschließenden Neuaufbau verifiziert werden. Sie darf bis dahin nicht als vollständig erfolgreicher Firmware-Build dokumentiert werden.


---

## Verifizierter Endstand – Visual Studio erkennt den eigenen Target

Der selbst gebaute Target `ESP32_S3_N16_NOPSRAM` wird über `COM8` sowohl von `nanoff` als auch vom Visual Studio Device Explorer erkannt.

![Visual Studio Device Explorer – ESP32_S3_N16_NOPSRAM auf COM8](img/amshelper/nanoframework-device-explorer-com8.png)

Auch das neu aus der nanoFramework-Projektvorlage erzeugte Projekt `AMSHelper` ist der gültige Ausgangspunkt für die weitere Entwicklung:

![AMSHelper-Projekt in Visual Studio](img/amshelper/amshelper-project.png)
