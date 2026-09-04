# OpenSpoolMan – zentrale To-do-Liste

## AMSHelper

- I²C-Einzelreader stabil halten.
- NDEF-URL-Lesen/-Schreiben für NTAG215 abschließen.
- SPI-Pinbelegung festlegen.
- PN532-SPI-Pfad zunächst mit einem Reader testen.
- Auf vier Reader mit gemeinsamem SPI-Bus und vier CS-Leitungen erweitern.
- UID + AMS-Slot bzw. „Tray leer“ an OpenSpoolMan übertragen.
- Live-Video-Funktion prüfen und umsetzen.
- Hotspot-Modus zum Öffnen/Anbieten eines WLAN-Hotspots implementieren.

## OpenSpoolMan / AMS-Kommunikation

- Zentrale AMS-Operations-Serialisierung für Fill, Clear, Profil- und Statusabfragen fertigstellen.
- Profil-/PA-Index zuverlässig aus AMS-Antworten übernehmen und dauerhaft in Bambu verifizieren.
- Unterschiede zwischen AMS-Status und SpoolMan-Zuordnung behandeln.
- Verhalten bei External-Spool-Reset durch Bambu abschließend korrigieren.
- External-Spool-Druckstatus und Zuordnung verifizieren.

## Weboberfläche / Verlauf

- Print-History vollständig gegen alle gewünschten Zustände und UI-Aktionen testen.
- Automatische Aktualisierung nur während laufender Druckjobs sicherstellen.

## Wartung / Betrieb

- Docker-Log-Leerung beim Recreate dokumentieren und prüfen.
- Versionierung bei Releases konsistent aktualisieren.
