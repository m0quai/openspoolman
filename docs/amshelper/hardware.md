# AMSHelper – Hardware

> Einstieg: [START.md](../START.md) · Entscheidungen: [Design-Entscheidungen](../design-entscheidungen.md)

## ESP32-S3

- Revision v0.2
- 16 MB Flash
- 8 MB physisch erkanntes PSRAM
- nanoFramework-Target `ESP32_S3_N16_NOPSRAM`

![ESP32-S3 Pinout](../img/amshelper/esp32-s3-pinout.png)

## PN532

GERUI/Elechouse-kompatibles PN532 NFC Module V3.

![PN532 Originalansicht](../img/amshelper/pn532-v3-original.png)

![PN532 Anschlussübersicht](../img/amshelper/pn532-v3-anschluss-antenne-guide.png)

### Aktueller Einzelreader

I²C1: VCC 3.3 V, GND, SDA GPIO8, SCL GPIO9; IRQ/RSTO nicht verwendet.

### Vier-Reader-Ziel

Vier PN532 über SPI. Clock/MOSI/MISO werden gemeinsam genutzt; jeder Reader erhält eine eigene Chip-Select-Leitung. TCA9548A ist keine Zielarchitektur mehr.
