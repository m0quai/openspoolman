# Projektarchitektur und Wartungsstrategie

## Ziel

OpenSpoolMan wird als eigener Fork mit Bambu-Lab-Erweiterungen gepflegt. Eigene Funktionalität soll so weit wie möglich von Upstream-Code getrennt bleiben, damit spätere OpenSpoolMan-Updates möglichst wenig Konflikte verursachen.

## Modulgrenzen

### `app_custom.py`

Bevorzugter eigener Anwendungseinstieg. Die originale `app.py` soll möglichst unverändert bleiben.

### `bambu_auth.py`

Bambu-Authentifizierungslogik. UI-/Routing-Aufgaben möglichst getrennt halten.

### `bambu_auth_routes.py`

Routen und Handler für Bambu-Authentifizierung, Konfiguration und zugehörige UI-Abläufe.

### `bambu_certificate.py`

Zertifikats- und Signierungsfunktionalität. Änderungen hier sind sicherheitskritisch.

### `templates/bambu_auth.html`

Bambu-spezifische Oberfläche einschließlich Auswahl des Authentifizierungsmodus sowie Konfigurations- und Statusdarstellung.

### `templates/base.html`

Einbindung in die Hauptnavigation, insbesondere **„Bambu Cloud“**. Änderungen möglichst klein halten, um Upstream-Konflikte zu reduzieren.

## Updatefreundliche Entwicklung

1. Neue eigene Module gegenüber großen Änderungen an Upstream-Dateien bevorzugen.
2. Registrierung/Integration möglichst über `app_custom.py`.
3. Änderungen an Upstream-Templates möglichst klein halten.
4. Upstream-Code nicht unnötig kopieren.
5. Falls Upstream-Code zwingend geändert werden muss, Änderung eng begrenzen.
6. Bestehende eigene Module nicht ohne konkreten Grund umbenennen.

## Konfiguration

Bekannte Anforderungen:

- vorhandene Drucker-IP als Vorgabewert verwenden;
- eigener lokaler Access-Key **`Printer Access LAN`**;
- Online-Authentifizierung verwendet ihre bestehenden Zugangsdaten;
- ausgewählter Modus bestimmt Authentifizierungsweg und Access-Key.

Vor neuen oder umbenannten Konfigurationswerten immer das gesamte Repository nach bestehenden Definitionen und Verwendungen durchsuchen.

## UI

Die Bambu-Seite enthält:

- Radio-Button **„Lokaler LAN-Modus“**;
- Radio-Button **„Online-Authentifizierung“**;
- Standard: lokaler LAN-Modus;
- Online-Modus bleibt funktionsfähig;
- Drucker-IP aus vorhandener Konfiguration vorbelegt;
- MQTT-Status nur verbunden/nicht verbunden;
- keine gelbe Zwischenstatusanzeige.

## Quelle der Wahrheit

Diese Dokumentation beschreibt die beabsichtigte Architektur. Der aktuelle Code muss trotzdem immer geprüft werden.

Bei Widersprüchen zwischen Dokumentation und Code nicht automatisch funktionierenden Code auf einen möglicherweise veralteten Dokumentationsstand zurücksetzen. Zuerst feststellen, ob der Code eine neuere bewusste Entscheidung enthält.
