# ESP32-S3 / .NET nanoFramework – Build und Toolchain

> Einstieg: [START.md](../START.md)

## Verifizierter Projektstand

Zielhardware: ESP32-S3, 16 MB Flash, physisch 8 MB PSRAM, COM8, C#/.NET nanoFramework. Verwendetes eigenes Target: `ESP32_S3_N16_NOPSRAM`.

Der konservative Build ohne PSRAM-Nutzung wurde gewählt, nachdem offizielle `ESP32_S3_OCTAL`-Images auf dem konkreten Board reproduzierbar mit `IllegalInstruction` abstürzten.

## Toolchain

Verwendet werden Visual Studio 2022 mit nanoFramework Extension/Device Explorer, Git, Python, `nanoff`, CMake, Ninja, SRecord und ESP-IDF 5.5.4.

Arbeitsverzeichnisse liegen unter `C:\nanoFramework\`, insbesondere `nf-interpreter` und `esp-idf`.

## Eigenes Target

Defconfig: `targets\ESP32\defconfig\ESP32_S3_N16_NOPSRAM_defconfig`.

SDK-Konfiguration: `sdkconfig.default.esp32s3` statt der Octal-PSRAM-Konfiguration. Configure-/Build-Preset: `ESP32_S3_N16_NOPSRAM`.

## Configure/Build

```powershell
cd C:\nanoFramework\esp-idf
.\export.ps1
cd C:\nanoFramework\nf-interpreter
cmake --preset ESP32_S3_N16_NOPSRAM -DTOOL_SRECORD_PREFIX="C:/nanoFramework/srecord/bin" -DESP32_IDF_PATH="C:/nanoFramework/esp-idf"
cmake --build --preset ESP32_S3_N16_NOPSRAM
```

COM8 und der Flashweg sind bestätigt. Visual-Studio-Deployment und Debugging des AMSHelper-Projekts funktionieren inzwischen; deshalb ist diese Datei Referenz für die reproduzierbare Toolchain, nicht mehr eine Liste der nächsten Projektaufgaben.
