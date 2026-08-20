# OpenSpoolMan – Arbeitsanweisungen für Agenten

## Zweck

Dieses Repository ist ein privat gepflegter OpenSpoolMan-Fork mit eigener Bambu-Lab-Integration. Diese Datei ist der zentrale Einstiegspunkt für ChatGPT Work, Codex und andere Coding-Agenten.

Vor jeder Änderung muss diese Datei gelesen werden. Zusätzlich sind die für die jeweilige Aufgabe relevanten Dokumente unter `docs/agent-kontext/` zu lesen.

## Grundregeln

1. Die Upstream-Struktur von OpenSpoolMan soweit wie sinnvoll erhalten.
2. Eigene Bambu-Funktionalität modular und updatefreundlich halten.
3. Die originale `app.py` möglichst unangetastet lassen. Eigene Erweiterungen bevorzugt über den eigenen Einstiegspunkt und separate Module integrieren.
4. Keine aufgabenfremden Refactorings durchführen.
5. Vor Änderungen immer den aktuellen Repository-Stand prüfen. Das Repository ist die Quelle der Wahrheit für den aktuellen Implementierungsstand; diese Dokumente beschreiben Architekturentscheidungen und Vorgaben.
6. Bestehende funktionierende Abläufe erhalten, sofern die konkrete Aufgabe sie nicht ausdrücklich ersetzt.
7. Niemals Passwörter, Access Tokens, API-Schlüssel, Drucker-Zugangscodes, private Schlüssel oder andere Geheimnisse in Git aufnehmen.
8. Entwicklung und Tests erfolgen derzeit primär über **Visual Studio Debug**, nicht über das reale Docker-Image. Testanweisungen deshalb vorrangig für Visual Studio formulieren.
9. Bei Änderungen an Konfiguration, Authentifizierung, MQTT, Zertifikaten/Signierung oder Bambu-Routen immer alle Aufrufer und UI-Abhängigkeiten prüfen.
10. Bei Änderungen über mehrere Dateien hinweg auf einen konsistenten Gesamtstand achten.

## Bekannte eigene Projektdateien

- `app_custom.py` – eigener Anwendungseinstieg.
- `bambu_auth.py` – Bambu-Authentifizierungslogik.
- `bambu_auth_routes.py` – Bambu-Routen und UI-Abläufe.
- `bambu_certificate.py` – Zertifikats-/Signierungsfunktionalität.
- `templates/bambu_auth.html` – Bambu-Konfigurations- und Authentifizierungsoberfläche.
- `templates/base.html` – Navigationseinbindung.

Diese Liste ist nicht zwingend vollständig. Vor Änderungen das Repository nach weiteren Bambu-, NFC- und MQTT-Modulen durchsuchen.

## Bambu-Verbindungsmodi

Die Bambu-Lab-Seite bietet zwei per Radio-Button wählbare Modi.

### Lokaler LAN-Modus

- Bezeichnung: **„Lokaler LAN-Modus“**
- Standardmodus.
- Direkter Zugriff auf den lokalen Drucker.
- Eigener UI-/Fachbegriff: **`Printer Access LAN`**; technischer Konfigurationsschlüssel: **`PRINTER_ACCESS_LAN`**.
- Der lokale Drucker-Access-Key ist getrennt von Zugangsdaten der Online-Authentifizierung zu behandeln.
- Die bereits konfigurierte Drucker-IP wird als Vorgabewert auf der Bambu-Seite verwendet.
- MQTT-Status wird binär angezeigt: **verbunden** oder **nicht verbunden**.
- Keine gelbe/intermediäre MQTT-Statusanzeige wieder einführen, sofern dies nicht ausdrücklich neu beschlossen wird.

### Online-Authentifizierung

- Bezeichnung: **„Online-Authentifizierung“**
- Die bestehende Online-Authentifizierung bleibt als Alternative vollständig erhalten.
- Änderungen am LAN-Modus dürfen den Online-Ablauf nicht beeinträchtigen.
- Abhängig vom ausgewählten Modus müssen der passende Access-Key und der passende Authentifizierungsweg verwendet werden.

Details: `docs/agent-kontext/bambu-authentifizierung.md`.

## Bambu Cloud

Die Bambu-Cloud-Anmeldung ist fester Bestandteil der OpenSpoolMan-Weboberfläche und erscheint direkt im Hauptmenü als **„Bambu Cloud“**.

Festgelegtes Verhalten:

- Anmeldung mit Bambu-E-Mail und Passwort.
- Falls erforderlich zusätzlich E-Mail-Verifizierungscode.
- Das Passwort wird nicht gespeichert.
- Lokal gespeichert werden dürfen Access Token, numerische User-ID und erforderliche Token-Metadaten.
- Die numerische Bambu-User-ID wird automatisch über `/v1/design-user-service/my/preference` ermittelt.
- Der Token wird live gegen diesen Endpoint geprüft.
- Die UI zeigt Verbindungs- und Tokenstatus.
- Bei ungültigem oder abgelaufenem Token wird eine erneute Anmeldung verlangt.
- Token-, Credential- und Secret-Dateien dürfen nicht in Git gelangen.

## Bambu MQTT und Signierung

Auf der Cloud-Authentifizierung baut die Authentifizierung/Signierung von Bambu-MQTT-Kommandos auf. Vorgesehene Richtung: **RSA-SHA256 / X.509**.

Vor Änderungen:

- aktuellen Implementierungsstand prüfen;
- `bambu_certificate.py` und alle Aufrufer untersuchen;
- Secrets strikt vom Quellcode trennen;
- keine Zertifikate, Tokens oder Zugangsdaten erfinden oder hart codieren;
- LAN- und Online-Authentifizierungswege sauber getrennt halten.

Details: `docs/agent-kontext/bambu-mqtt-signierung.md`.

## NFC-/OpenSpoolMan-/Spoolman-Architektur

Festgelegte Architektur:

- Controller: ESP32-S3.
- Umsetzung: C# mit .NET nanoFramework.
- NFC-Tag: NTAG215.
- Der Controller liest die Hardware-UID des Tags.
- Bei einem neuen/leeren Tag wird der NDEF-Inhalt geprüft und einmalig eine URL mit unveränderlicher UID geschrieben, z. B. `/nfc/<UID>`.
- Diese URL bleibt bei Wiederverwendung des Tags unverändert.
- Der Controller meldet UID und AMS-Slot an OpenSpoolMan.
- Das iPhone kann die URL direkt vom Tag öffnen.
- Über die Weboberfläche kann die UID einer Spoolman-Spule zugeordnet, freigegeben oder neu zugeordnet werden.
- Die Zuordnung UID → Spule liegt ausschließlich in OpenSpoolMan/Spoolman und wird nicht als wechselnde Spulenidentität auf den NFC-Tag geschrieben.

Details: `docs/agent-kontext/nfc-architektur.md`.

## Patch- und ZIP-Regeln

Wenn ein Patch als ZIP verlangt wird:

- Patch sofort erstellen und bereitstellen, nicht nur ankündigen.
- Pfade innerhalb der ZIP relativ zum Repository-Root.
- Kein zusätzliches oberstes `OpenSpoolMan/`-Verzeichnis.
- Nur tatsächlich benötigte/geänderte Projektdateien aufnehmen.
- Keine `README-PATCH.txt` und keine zusätzliche Änderungsbeschreibung in die ZIP aufnehmen.
- Aktuell primär Visual-Studio-Debug-Testschritte nennen, nicht standardmäßig Docker-Rebuild/Compose.

## Nutzung

Die Bambu-MQTT-Zertifikats-/Signing-Integration ist für den privaten Gebrauch vorgesehen. Keine Veröffentlichungs- oder kommerziellen Anforderungen unterstellen.

## Ablauf vor jeder Coding-Aufgabe

1. Diese `AGENTS.md` lesen.
2. `docs/agent-kontext/projektarchitektur.md` lesen.
3. Relevante aufgabenspezifische Kontextdateien lesen.
4. `git status` und betroffene Dateien prüfen.
5. Unabhängige lokale Änderungen des Nutzers niemals überschreiben.
6. Betroffene Konfigurationswerte, Routen, Templates und Aufrufer ermitteln.
7. Kleinste konsistente Änderung durchführen.
8. Sinnvolle Tests/Prüfungen mit den vorhandenen Werkzeugen durchführen.
9. Diff auf Secrets, unbeabsichtigte Änderungen und unnötige Upstream-Eingriffe prüfen.
10. Änderungen, tatsächlich durchgeführte Tests und offene Punkte klar zusammenfassen.

## Übergang Work → Codex

Diese Markdown-Dateien liegen bewusst im Repository. Work kann sie jetzt als Projektkontext verwenden; später kann Codex denselben Repository-Stand einschließlich dieser Dateien übernehmen.

Bei neuen dauerhaften Architekturentscheidungen müssen die entsprechenden Kontextdateien aktualisiert werden.
