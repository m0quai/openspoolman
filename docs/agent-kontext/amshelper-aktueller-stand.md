# AMSHelper / ESP32-S3 / NFC – aktueller Projektkontext

> Zur Gesamtübersicht: [START.md](../START.md)

Stand: 2026-08-21 08:49 (Europe/Berlin)

## Ziel

AMSHelper ist der ESP32-S3-Teil des OpenSpoolMan-Projekts. Pro AMS-Slot soll später ein eigener NFC/RFID-Reader eine Filamentspule erkennen. Das AMS hat vier Slots, daher sind vier PN532-Reader vorgesehen.

## Aktuell bestätigter Hardware-/Firmwarestand

- Controller: ESP32-S3, Revision v0.2
- Flash: 16 MB Macronix
- Physisch vorhandenes PSRAM laut Chip-Erkennung: 8 MB
- Verwendetes eigenes nanoFramework-Target: `ESP32_S3_N16_NOPSRAM`
- nanoFramework-Gerät wird in Visual Studio am Device Explorer auf `COM8` erkannt.
- Deployment und Debugging aus Visual Studio funktionieren.
- Das endgültige C#-Projekt wurde neu aus der offiziellen nanoFramework-Projektvorlage erzeugt. Die zuvor manuell gepatchten `.nfproj`-Varianten werden nicht weiterverwendet.

### Entwicklungsstand in Visual Studio

![Eigenes nanoFramework-Target im Device Explorer](../img/amshelper/nanoframework-device-explorer-com8.png)

![Funktionierendes AMSHelper-nanoFramework-Projekt](../img/amshelper/amshelper-project.png)


## Eigene nanoFramework-Firmware

Das Standardtarget `ESP32_S3_OCTAL` ließ sich flashen, wurde vom nanoFramework Wire Protocol auf diesem Board jedoch nicht zuverlässig als Gerät erkannt.

Daraufhin wurde ein eigenes Target `ESP32_S3_N16_NOPSRAM` gebaut. Nach Flashen dieses Builds wurde das Gerät erfolgreich erkannt:

`ESP32_S3_N16_NOPSRAM @ COM8`

Die vollständige Toolchain und der Buildablauf stehen in `docs/esp32-nanoframework-build.md`.

## WLAN – bestätigt funktionierend

WLAN wurde im neuen AMSHelper-Projekt erfolgreich getestet.

Bestätigt:
- WLAN-Verbindung funktioniert.
- DHCP/IP-Konfiguration funktioniert.
- Netzwerkdaten können über nanoFramework ausgelesen werden.
- DNS-Auflösung funktioniert.
- Der Hostname `NBK-01-548` wird vom ESP32-S3 erfolgreich aufgelöst.
- Für wiederholte Tests wird `Dns.GetHostEntry(...)` bei jedem Durchlauf erneut aufgerufen.

NuGet:
- `nanoFramework.System.Device.Wifi`

## PN532

Reader: GERUI / Elechouse-kompatibles `NFC MODULE V3` auf Basis PN532.

![PN532 NFC Module V3 – Originalansicht](../img/amshelper/pn532-v3-original.png)

![PN532 – Antennen- und Anschlussübersicht](../img/amshelper/pn532-v3-anschluss-antenne-guide.png)


Das konkrete Modul besitzt einen kleinen 2-poligen DIP-Schalter zur Wahl der Schnittstelle. Die Module wurden für den geplanten Test auf I2C gestellt.

Das verwendete ESP32-S3-Pinout:

![ESP32-S3 Pinout](../img/amshelper/esp32-s3-pinout.png)

Für den ersten Einzelreader-Test ist vorgesehen:
- PN532 VCC -> 3.3 V
- PN532 GND -> GND
- PN532 SDA -> ESP32-S3 GPIO8
- PN532 SCL -> ESP32-S3 GPIO9
- IRQ zunächst frei
- RSTO zunächst frei

NuGet für I2C:
- `nanoFramework.System.Device.I2c`

Geplanter PN532-Treiber:
- `nanoFramework.Iot.Device.Pn532`

## Wichtige Korrektur: vier PN532 nicht direkt parallel

Alle vier PN532 dürfen NICHT einfach gemeinsam direkt an GPIO8/GPIO9 betrieben werden, weil die PN532 im I2C-Modus dieselbe feste I2C-Adresse `0x24` verwenden.

Der zuvor erzeugte Vier-Reader-Schaltplan mit vier direkt parallel geschalteten PN532 ist verworfen und gehört ausdrücklich NICHT zur gültigen Projektdokumentation.

Für vier Reader ist als bevorzugte Architektur vorgesehen:

ESP32-S3 GPIO8/GPIO9
-> I2C
-> TCA9548A I2C-Multiplexer
-> Kanal 0: PN532 AMS Slot 1
-> Kanal 1: PN532 AMS Slot 2
-> Kanal 2: PN532 AMS Slot 3
-> Kanal 3: PN532 AMS Slot 4

Diese Vier-Reader-Schaltung ist noch nicht praktisch getestet.

## Nächster technischer Schritt

1. Einen einzelnen PN532 an GPIO8/GPIO9 anschließen.
2. PN532 über I2C erkennen und Firmwarekennung auslesen.
3. NTAG215 erkennen.
4. Hardware-UID auslesen.
5. NDEF-URL mit UID schreiben/lesen.
6. Danach auf vier Reader über einen I2C-Multiplexer erweitern.
7. Anschließend UID + AMS-Slot an OpenSpoolMan übertragen.
