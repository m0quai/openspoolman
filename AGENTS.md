# OpenSpoolMan / AMSHelper - Codex Instructions

Diese Datei enthaelt verbindliche Arbeitsregeln fuer Codex und andere Coding-Agenten in diesem Repository.

## Repository und Arbeitsbranch

- Repository: `m0quai/openspoolman`
- Aktiver Entwicklungsbranch: `feature/NewFiles`
- Vor jeder Aenderung zuerst den aktuellen Stand des Branches einlesen.
- Keine Aenderung auf Basis eines vermuteten oder veralteten Dateistands vornehmen.
- Bestehende lokale Aenderungen des Benutzers nicht ungefragt verwerfen, ueberschreiben oder resetten.

## Allgemeiner Arbeitsablauf

1. `git status` pruefen.
2. Aktuellen Branch pruefen: `git branch --show-current`.
3. Falls der Working Tree sauber ist, aktuellen Remote-Stand holen: `git pull --ff-only origin feature/NewFiles`.
4. Vor Implementierung die betroffenen Dateien und vorhandene Architektur lesen.
5. Kleine, nachvollziehbare Aenderungen bevorzugen.
6. Nach Aenderungen Diff pruefen und passende Builds/Tests ausfuehren.
7. Projektdateien (`.sln`, `.nfproj`, `.pyproj`, `packages.config` usw.) mit aktualisieren, wenn Dateien/Abhaengigkeiten hinzugefuegt oder entfernt werden.
8. Keine Build-Artefakte, lokalen IDE-Dateien, Tokens, Passwoerter oder sonstige Secrets committen.

## OpenSpoolMan - verbindliche Regeln

- OpenSpoolMan wird als eigener Fork gepflegt; Upstream ist `drndos/openspoolman`.
- Anpassungen muessen moeglichst updatefreundlich bleiben.
- `app.py` moeglichst nicht veraendern.
- Eigene Erweiterungen bevorzugt ueber `app_custom.py` und getrennte Module/Blueprints implementieren.
- Fuer Bambu-Authentifizierung existieren getrennte Module wie `bambu_auth.py`; bestehende Trennung respektieren.
- Token-, Credential- und Secret-Dateien duerfen nicht in Git gelangen.
- Die Weboberflaeche und bestehende API-Vertraege nicht ohne ausdruecklichen Auftrag inkompatibel aendern.
- Die Spool-/UID-Zuordnungslogik bleibt auf OpenSpoolMan-Seite; der AMSHelper loest keine UID selbst zu einer Spool-ID auf.

## AMSHelper - Architektur

Das Projekt `AMSHelper` ist eine nanoFramework-Anwendung fuer ESP32-S3 und Bambu Lab P1S/AMS.

### Komponenten und Verantwortlichkeiten

- `BambuMqtt`: nur lokaler Bambu-MQTT-Transport, TLS-Verbindung, Subscribe, Empfang und Reconnect.
- `BambuStatusParser`: JSON-Auswertung. Nur vorhandene Felder auswerten; fehlende Felder nicht als neue Werte interpretieren.
- WLAN/Netzwerk ist eine separate Komponente und gehoert nicht in ein gemeinsames `Esp`-Objekt.
- `OpenSpoolManClient` kapselt die Kommunikation mit OpenSpoolMan.
- Vier `AmsTray`-Objekte repraesentieren Tray 0 bis 3.
- Traybezogene PN532-/NFC-Logik gehoert in bzw. hinter die Tray-Abstraktion.
- Ein gemeinsamer Scheduler darf die vier Trays bedienen; Aktionen sollen nach Moeglichkeit ereignis-/statusgetrieben erfolgen und nicht durch unnoetiges Dauerpolling.
- Event-Handler nach Moeglichkeit gekapselt und asynchron gestalten, soweit nanoFramework/API dies sinnvoll erlaubt.

### MQTT

- Lokaler Bambu-MQTT-Zugang: TLS Port `8883`.
- Benutzer: `bblp`.
- Passwort: Printer LAN Access Code. Niemals hardcoden oder committen.
- Report-Topic: `device/<SERIAL>/report`.
- Requests werden ueber das passende `device/<SERIAL>/request`-Topic gesendet.
- Standard-Telemetrieausgaben gering halten. Debug-Ausgaben nur zielgerichtet bzw. konfigurierbar aktivieren.

### NFC / Hardware

- Zielhardware: ESP32-S3 mit vier PN532-Lesern und NTAG215-Tags.
- Zielanbindung fuer vier PN532: gemeinsamer SPI-Bus mit getrenntem SS/CS je Reader.
- Kein I2C-Multiplexer.
- Eventuell vorhandener Code fuer einen einzelnen PN532 per I2C ist Test-/Uebergangsstand und darf nicht als Zielarchitektur fuer vier Leser interpretiert werden.
- Kein MIFARE-Classic-spezifisches Design fuer dieses Projekt einfuehren; Ziel-Tags sind NTAG215.

## Diagnose / Logging

- Zentrale Trace-/Debug-Ausgabe bevorzugen (`TraceWriter` bzw. vorhandene zentrale Implementierung).
- Debug-Queue begrenzen; keine unbeschraenkt wachsenden Queues.
- Heartbeat soll bei entsprechender Implementierung freien Speicher sowie Queue-/Drop-Informationen kompakt anzeigen.
- Keine hochfrequente Standard-Telemetrie ohne konkreten Diagnosezweck einfuehren.

## C# / nanoFramework Coding-Regeln

- `if`-Anweisungen immer mit `{ }` schreiben, auch bei nur einer Anweisung.
- Bestehende Namespace- und Ordnerstruktur respektieren (`Ams`, `Config`, `Diagnostics`, `Hardware`, `Mqtt`, `Network`, `Nfc`, `OpenSpoolMan`).
- Vor neuen NuGet-Paketen pruefen, ob sie mit der verwendeten nanoFramework-Version kompatibel sind.
- Keine Desktop-.NET-APIs verwenden, die nanoFramework nicht unterstuetzt.

## Test- und Entwicklungsumgebung

- Primaerer Testweg des Benutzers ist Visual Studio Debug.
- Nicht standardmaessig Docker-Rebuild/Compose als ersten Testschritt verlangen, wenn die Aenderung im lokalen Visual-Studio-Debug pruefbar ist.
- Bei AMSHelper-Aenderungen Projekt/NuGet-Referenzen und nanoFramework-Kompatibilitaet mitpruefen.

## Git-Regeln fuer Codex

- Keine Force-Pushes.
- Keine History-Rewrites ohne ausdruecklichen Auftrag.
- Keine fremden oder lokalen Aenderungen entfernen, nur um einen sauberen Diff zu erhalten.
- Vor einem Commit `git diff` und `git status` pruefen.
- Commit-Nachrichten kurz und beschreibend halten.
- Im Zweifel Aenderungen auf `feature/NewFiles` belassen; nicht ungefragt nach `main` mergen.

## Prioritaet bei Widerspruechen

1. Aktuelle ausdrueckliche Benutzeranweisung.
2. Diese `AGENTS.md`.
3. Aktueller Code und vorhandene Projektdokumentation.
4. Aeltere Annahmen oder fruehere Chat-Kontexte.

Wenn Architektur und aktueller Code voneinander abweichen, die Abweichung zuerst benennen und nicht stillschweigend eine neue Architektur einfuehren.
