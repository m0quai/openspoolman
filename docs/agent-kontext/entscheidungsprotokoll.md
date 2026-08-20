# Festgelegte Projektentscheidungen

Dieses Dokument hält dauerhafte Entscheidungen fest, damit sie unabhängig von Chat, Work oder Codex erhalten bleiben.

## Anwendungsstruktur

- OpenSpoolMan wird als eigener Fork gepflegt.
- Originale `app.py` möglichst unangetastet lassen.
- Eigener Einstieg bevorzugt über `app_custom.py`.
- Bambu-Routen: `bambu_auth_routes.py`.
- Bambu-Authentifizierungslogik: `bambu_auth.py`.
- Bambu-UI: `templates/bambu_auth.html`.
- Navigation: `templates/base.html`.
- Zertifikats-/Signing-Funktionalität: `bambu_certificate.py`.

## Bambu Cloud

- Direkt im Hauptmenü als **„Bambu Cloud“**.
- Login mit Bambu-E-Mail/Passwort und ggf. E-Mail-Verifizierungscode.
- Passwort wird nicht gespeichert.
- Access Token, User-ID und Token-Metadaten dürfen lokal gespeichert werden.
- Numerische User-ID automatisch über `/v1/design-user-service/my/preference`.
- Token live gegen diesen Endpoint prüfen.
- UI zeigt Verbindungs-/Tokenstatus und fordert bei Bedarf zur Neuanmeldung auf.
- Token-/Credential-Dateien nicht in Git.

## Authentifizierungsmodi

Radio-Buttons:

- **„Lokaler LAN-Modus“**
- **„Online-Authentifizierung“**

Festgelegt:

- Standard ist lokaler LAN-Modus.
- Online-Authentifizierung bleibt vollständig erhalten.
- Lokaler Modus hat eigenen Access-Key **`Printer Access LAN`**.
- Vorhandene Drucker-IP wird als Vorgabewert verwendet.
- Modus bestimmt passenden Access-Key und Authentifizierungsweg.
- MQTT-Status nur verbunden/nicht verbunden.
- Keine gelbe Zwischenstatusanzeige.

## MQTT/Signierung

- Cloud-Authentifizierung bildet Grundlage für weitere MQTT-Authentifizierungs-/Signing-Arbeit.
- Technische Richtung: RSA-SHA256 / X.509.
- Secrets, private Schlüssel und Credential-Dateien nicht in Git.

## NFC

- ESP32-S3.
- C#/.NET nanoFramework.
- NTAG215.
- Hardware-UID ist stabile Identität.
- Bei leerem/neuem Tag NDEF prüfen und einmalig URL mit UID schreiben.
- Beispiel `/nfc/<UID>`.
- URL bleibt bei Wiederverwendung unverändert.
- Controller meldet UID + AMS-Slot an OpenSpoolMan.
- iPhone öffnet NFC-URL.
- UID kann einer Spoolman-Spule zugeordnet, freigegeben und neu zugeordnet werden.
- UID-zu-Spule-Zuordnung ausschließlich serverseitig in OpenSpoolMan/Spoolman.

## Entwicklung

- Aktuell primär Visual Studio Debug.
- Docker-Rebuild/Compose nicht als Standard-Testanweisung.

## Patch-Auslieferung

- Angeforderte Patches direkt erstellen und liefern.
- ZIP relativ zum Repository-Root.
- Kein zusätzliches `OpenSpoolMan/`-Verzeichnis.
- Nur tatsächlich notwendige/geänderte Projektdateien.
- Keine `README-PATCH.txt`.
- Signing-Integration ist für privaten Gebrauch vorgesehen.


## Bestätigt: P1S LAN-/Developer-Mode und AMS-Materialstatus (20.08.2026)

- Direkte lokale MQTT-Verbindung mit dem separaten `Printer Access LAN` funktioniert.
- `pushall`, Statusabonnement und `ams_filament_setting` funktionieren lokal.
- `ams_filament_setting` wird vom P1S ohne RSA-SHA256-/X.509-Signierung mit `result='success'` und `reason='success'` bestätigt.
- Signing bleibt damit für den Online-Modus relevant, nicht für den bestätigten lokalen LAN-Pfad.
- Bei Fremdspulen mit Null-RFID-UUID kann der P1S nach einem erfolgreichen `ams_filament_setting` unvollständige/sparse AMS-Statusdaten liefern, insbesondere leere Materialfelder.
- OpenSpoolMan hält deshalb die zuletzt vom Drucker erfolgreich bestätigten AMS-Materialwerte im Laufzeit-Cache und ergänzt damit fehlende Materialfelder in nachfolgenden Statuspaketen.
- Ein erfolgreiches explizites `Clear` schreibt leere Werte in denselben Cache und hebt die lokale Materialzuordnung wieder auf.

## 2026-08-20 – AMS Clear und app.py-Regel

- `app.py` darf fuer projektspezifische Anpassungen niemals geaendert werden.
- Flask-Routen und bestehende View-Funktionen werden ausschliesslich ueber `app_custom.py` bzw. die Custom-/Blueprint-Struktur erweitert oder ersetzt.
- `Clear` eines AMS-Slots loescht zuerst die Materialbelegung am Bambu-Drucker per lokalem MQTT und erst danach die OpenSpoolMan-/Spoolman-Zuordnung.
- Der lokale Cache der zuletzt bestaetigten AMS-Materialdaten wird beim erfolgreichen Clear sofort invalidiert, damit Material und Farbe nicht in der Tray-Kopfzeile stehen bleiben.

## 2026-08-20 15:40 – AMS-Clear-Payload für P1S korrigiert

- `app.py` bleibt unverändert; die Clear-Route wird ausschließlich über `app_custom.py` überschrieben.
- Der P1S erhält beim Clear keine `null`-Temperaturwerte mehr.
- Der lokale Clear setzt den Fremdspulen-Slot mit leerem Material/Profil, Temperaturwerten `0` und neutraler Farbe auf einen unkonfigurierten Zustand.
- Das tatsächlich gesendete Clear-Payload wird mit `[AMS-CLEAR]` protokolliert.

## 2026-08-20 16:01 – Temporäre AMS-Debug-Ausgaben entfernt

- Die während der LAN-/Developer-Mode- und AMS-Clear-Analyse ergänzten Erfolgs-/Payload-Debugmeldungen wurden entfernt.
- Entfernt wurden insbesondere `[AMS-CLEAR]`, `[AMS-FILAMENT-SETTING-RESPONSE]` sowie die temporäre Meldung zum ausgelassenen leeren `setting_id`.
- Die funktionale Verarbeitung erfolgreicher `ams_filament_setting`-Antworten und der AMS-Material-Cache bleiben unverändert aktiv.
- Fehlerprotokollierung bleibt erhalten; nur nicht mehr notwendige Diagnose-/Erfolgsausgaben wurden entfernt.
- `app.py` bleibt unverändert.

## 2026-08-20 16:10 – Position von AMS und External Spool getauscht

- In der Hauptansicht wird die AMS-Karte links und `External Spool` rechts dargestellt.
- Dieselbe Reihenfolge wird in der Spulen-/Tray-Zuordnungsansicht verwendet.
- Es wurde ausschließlich die Darstellungsreihenfolge geändert; Verbindungs-, MQTT- und Zuordnungslogik bleiben unverändert.

## 2026-08-20 16:04 – Layoutkorrektur AMS / External Spool

- `AMS` und `External Spool` bleiben zwei getrennte Karten auf derselben äußeren Bootstrap-Zeile.
- Reihenfolge: `AMS` links, `External Spool` rechts.
- `External Spool` darf nicht innerhalb des `AMS`-Card-Bodys bzw. innerhalb der Tray-Zeile gerendert werden.
- Die Korrektur betrifft `templates/index.html` und `templates/spool_info.html`.
- `app.py` bleibt unverändert.

## 2026-08-20 16:14 – AMS/External-Spool-Layout 8/4 korrigiert

- Grundlage ist der bereits reparierte Stand mit zwei getrennten Geschwister-Karten.
- AMS bleibt eine eigene Karte links und erhält auf großen Bildschirmen `col-lg-8`.
- `External Spool` bleibt eine eigene Karte rechts und erhält `col-lg-4`.
- `External Spool` ist ausdrücklich nicht Bestandteil des AMS-Card-Bodys.

## 2026-08-20 16:20 – Erfolgsmeldungen automatisch ausblenden

- Globale grüne Erfolgsmeldungen werden nach 10 Sekunden automatisch geschlossen.
- Manuelles Schließen über das X bleibt weiterhin möglich.
- Die Änderung erfolgt ausschließlich im gemeinsamen Template `templates/base.html`; `app.py` bleibt unverändert.
