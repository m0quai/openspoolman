# AMSHelper / ESP32-S3 / NFC – aktueller Stand

> Einstieg: [START.md](../START.md) · Entscheidungen: [Design-Entscheidungen](../design-entscheidungen.md)

## Hardware/Firmware

- ESP32-S3 Revision v0.2
- Flash: 16 MB Macronix
- physisch erkanntes PSRAM: 8 MB
- eigenes nanoFramework-Target: `ESP32_S3_N16_NOPSRAM`
- Visual Studio Device Explorer: COM8
- Deployment und Debugging aus Visual Studio funktionieren

## WLAN

WLAN, DHCP/IP-Konfiguration, DNS und Namensauflösung wurden erfolgreich getestet. WLAN bleibt in einer eigenen Netzwerkklasse und ist nicht Bestandteil des ESP-/Hardwareobjekts.

## PN532 – aktueller Teststand

Ein einzelner PN532 V3 ist über I²C1 verifiziert: 3.3 V, GND, SDA GPIO8, SCL GPIO9; IRQ/RSTO unbenutzt. PN532 Chip-ID `0x32`, Firmware `1.6`; NTAG215 per `GET_VERSION (0x60)` erkannt und Pages per `READ (0x30)` gelesen.

Der I²C-Einzelreader ist der aktuelle funktionierende Entwicklungs- und Testpfad.

## Vier-Reader-Ziel

Die Zielarchitektur ist **SPI**: gemeinsamer SPI-Bus, vier PN532, eigener Chip-Select je AMS-Slot. Die frühere TCA9548A-/Vierfach-I²C-Planung ist verworfen.

## To-do

Die übergreifende Aufgabenliste steht in [docs/TODO.md](../TODO.md), Kapitel „AMSHelper“.
