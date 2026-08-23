# START – AMSHelper / ESP32-S3 / NFC

**Stand: 2026-08-21 15:12 (Europe/Berlin)**

Diese Datei ist der Einstiegspunkt in die Projektdokumentation. Sie beschreibt, **was aktuell funktioniert, was entschieden wurde, welche Dokumente wofür zuständig sind und in welcher Reihenfolge sie gelesen werden sollten**.

---

## 1. Projekt in einem Satz

`AMSHelper` ist der ESP32-S3-Teil des OpenSpoolMan-Projekts. Ziel ist, die vier AMS-Slots jeweils über einen eigenen PN532-NFC/RFID-Reader zu erfassen und später UID + AMS-Slot an OpenSpoolMan zu übertragen.

---

## 2. Aktueller verifizierter Stand

Folgende Punkte sind bereits praktisch getestet und funktionieren:

- eigenes nanoFramework-Target `ESP32_S3_N16_NOPSRAM`
- ESP32-S3 wird über `COM8` von `nanoff` erkannt
- ESP32-S3 wird im Visual Studio Device Explorer erkannt
- C#-Deployment und Debugging aus Visual Studio funktionieren
- das aktuelle Projekt `AMSHelper` wurde neu aus einer funktionierenden nanoFramework-Projektvorlage erzeugt
- WLAN funktioniert
- DHCP/IP-Konfiguration funktioniert
- DNS-Auflösung funktioniert
- der Rechnername `NBK-01-548` kann vom ESP32-S3 aufgelöst werden

![Visual Studio erkennt den eigenen nanoFramework-Target](img/amshelper/nanoframework-device-explorer-com8.png)

![Aktuelles AMSHelper-Projekt](img/amshelper/amshelper-project.png)

Der einzelne PN532 über I2C ist inzwischen **erfolgreich verifiziert**. Ein echter NTAG215 wurde per GET_VERSION erkannt und dessen Pages 0–3 wurden erfolgreich gelesen. Aktueller Schritt ist das Lesen und Dekodieren von NDEF ab Page 4.

---

## 3. Empfohlene Lesereihenfolge

### 3.1 Aktueller Projektstand

➡️ **[agent-kontext/amshelper-aktueller-stand.md](agent-kontext/amshelper-aktueller-stand.md)**

Hier steht der aktuelle Gesamtzustand:
- Hardware
- eigenes nanoFramework-Target
- WLAN
- PN532
- 4-Slot-Zielarchitektur
- nächster technischer Schritt

Diese Datei ist die wichtigste laufende Kontextdatei.

### 3.2 Hardware, Pinout und Bilder

➡️ **[agent-kontext/hardware-und-bilder.md](agent-kontext/hardware-und-bilder.md)**

Hier stehen:
- konkretes ESP32-S3-Pinout
- PN532 V3
- Antennenposition
- aktueller Einzelreader-Anschluss
- Entscheidung für vier Reader
- Warnung vor dem verworfenen Parallelanschluss

Die zugehörigen Original- und Hilfsbilder liegen unter:

➡️ **[img/amshelper/README.md](img/amshelper/README.md)**

### 3.3 WLAN-Test

➡️ **[agent-kontext/wlan-test.md](agent-kontext/wlan-test.md)**

Enthält den bestätigten WLAN-Stand:
- benötigtes NuGet-Paket
- DHCP/IP
- DNS
- erneute Namensauflösung von `NBK-01-548`

WLAN gilt aktuell als **funktionierend und abgeschlossenes Basisthema**.

### 3.4 PN532 / NTAG215

➡️ **[agent-kontext/pn532-ntag215.md](agent-kontext/pn532-ntag215.md)**

Enthält den aktuellen, praktisch verifizierten PN532-/NTAG215-Stand einschließlich Scan-Retries, GET_VERSION, READ und NDEF-Fortsetzung.

### 3.5 nanoFramework-Build und Toolchain

➡️ **[esp32-nanoframework-build.md](esp32-nanoframework-build.md)**

Diese Datei ist die technische Wiederherstellungs- und Build-Dokumentation. Sie beschreibt:
- alle benötigten Tools
- ESP-IDF 5.5.4
- CMake/Ninja/SRecord
- eigenes Target `ESP32_S3_N16_NOPSRAM`
- Bluetooth-Deaktivierung
- erfolgreichen nativen Build
- Flash-Vorgang
- Verifikation über `nanoff` und Visual Studio

Diese Datei wird vor allem benötigt, wenn der Entwicklungsrechner neu aufgebaut oder die Firmware erneut gebaut werden muss.

---

## 4. Hardware-Zielbild

### ESP32-S3

Verwendet wird das konkrete ESP32-S3-Board aus:

![ESP32-S3 Pinout](img/amshelper/esp32-s3-pinout.png)

Für den ersten Einzelreader-Test:

| Funktion | ESP32-S3 |
|---|---|
| I2C SDA | GPIO8 |
| I2C SCL | GPIO9 |
| Versorgung PN532 | 3.3 V |
| Masse | GND |

### PN532

Verwendet wird das GERUI / Elechouse-kompatible `NFC MODULE V3` auf Basis PN532.

![PN532 Originalansicht](img/amshelper/pn532-v3-original.png)

![PN532 Anschluss- und Antennenübersicht](img/amshelper/pn532-v3-anschluss-antenne-guide.png)

Für den ersten Test ist **ein** PN532 im I2C-Modus vorgesehen:

| PN532 | ESP32-S3 |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| SDA | GPIO8 |
| SCL | GPIO9 |
| IRQ | zunächst frei |
| RSTO | zunächst frei |

---

## 5. Vier AMS-Slots / vier PN532

Das AMS besitzt vier Slots. Daher sind vier PN532-Reader vorgesehen.

### Wichtig

**Vier PN532 werden nicht direkt parallel an denselben SDA/SCL-Leitungen betrieben.**

Grund:
- alle PN532 verwenden im I2C-Modus die feste Adresse `0x24`
- vier Geräte mit derselben Adresse können auf demselben ungetrennten I2C-Bus nicht eindeutig angesprochen werden

Der zuvor erstellte Parallel-Schaltplan wurde deshalb verworfen und ist **nicht Bestandteil der gültigen Dokumentation**.

Aktuell bevorzugte Zielarchitektur:

```text
ESP32-S3
   |
   | GPIO8 = SDA
   | GPIO9 = SCL
   v
TCA9548A I2C-Multiplexer
   |
   +-- Kanal 0 -> PN532 -> AMS Slot 1
   +-- Kanal 1 -> PN532 -> AMS Slot 2
   +-- Kanal 2 -> PN532 -> AMS Slot 3
   +-- Kanal 3 -> PN532 -> AMS Slot 4
```

Diese Vier-Reader-Architektur ist **noch geplant und noch nicht praktisch getestet**.

---

## 6. Software-/NuGet-Stand

Für die bisherige Entwicklung relevant:

- `nanoFramework.System.Device.Wifi` – installiert und WLAN getestet
- `nanoFramework.System.Device.I2c` – installiert
- `nanoFramework.Hardware.Esp32` – für ESP32-spezifische Pin-Funktionen vorgesehen
- `nanoFramework.Iot.Device.Pn532` – für den PN532-Treiber vorgesehen

Das aktuelle C#-Projekt heißt:

```text
AMSHelper
```

Frühere manuell gepatchte `.nfproj`-Varianten werden **nicht mehr verwendet**.

---

## 7. Nächste Schritte

Der nächste sinnvolle Ablauf ist:

1. einen einzelnen PN532 an 3.3 V / GND / GPIO8 / GPIO9 anschließen
2. PN532 per I2C erkennen
3. PN532-Firmwarekennung auslesen
4. NTAG215 erkennen
5. UID auslesen
6. NDEF-URL lesen/schreiben
7. anschließend TCA9548A und vier PN532 aufbauen
8. jeden Reader eindeutig AMS Slot 1–4 zuordnen
9. UID + AMS-Slot an OpenSpoolMan übertragen

---

## 8. Dokumentationsregel

Bei Änderungen am Projekt sollen die Kontextdateien weiterhin mit **Datum und Uhrzeit** aktualisiert werden.

Neue Entscheidungen gehören primär in:

➡️ **[agent-kontext/amshelper-aktueller-stand.md](agent-kontext/amshelper-aktueller-stand.md)**

Technische Build-/Toolchain-Änderungen zusätzlich in:

➡️ **[esp32-nanoframework-build.md](esp32-nanoframework-build.md)**

Hardware-/Verdrahtungsänderungen zusätzlich in:

➡️ **[agent-kontext/hardware-und-bilder.md](agent-kontext/hardware-und-bilder.md)**

WLAN-/Netzwerkänderungen zusätzlich in:

➡️ **[agent-kontext/wlan-test.md](agent-kontext/wlan-test.md)**

---

## 9. Kurzstatus

| Bereich | Status |
|---|---|
| ESP32-S3 Hardware erkannt | ✅ bestätigt |
| eigener nanoFramework-Build | ✅ bestätigt |
| Flash über COM8 | ✅ bestätigt |
| Visual Studio Device Explorer | ✅ bestätigt |
| C# Deployment/Debugging | ✅ bestätigt |
| WLAN | ✅ bestätigt |
| DHCP/IP | ✅ bestätigt |
| DNS | ✅ bestätigt |
| PN532 einzeln per I2C | ✅ bestätigt |
| NTAG215 UID lesen | ✅ bestätigt |
| NTAG215 GET_VERSION / Typ | ✅ bestätigt |
| NTAG215 Pages 0–3 lesen | ✅ bestätigt |
| NDEF lesen/dekodieren | 🔄 aktuell |
| NDEF schreiben | ⏳ geplant |
| TCA9548A | ⏳ geplant |
| 4× PN532 | ⏳ geplant |
| OpenSpoolMan-Übertragung vom ESP32 | ⏳ geplant |
