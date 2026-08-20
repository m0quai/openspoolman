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
