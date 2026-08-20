# Bambu-Authentifizierung

## Überblick

Die OpenSpoolMan-Bambu-Integration unterstützt zwei ausdrücklich getrennte Verbindungs-/Authentifizierungsmodi.

## Lokaler LAN-Modus

Bezeichnung: **„Lokaler LAN-Modus“**

Standardmodus.

### Anforderungen

- Direkte Verbindung zum konfigurierten Bambu-Drucker im LAN.
- Bereits konfigurierte Drucker-IP als Vorgabewert verwenden.
- Eigener lokaler Access-Key: **`Printer Access LAN`**.
- Lokalen Access-Key nicht mit Online-/Cloud-Zugangsdaten vermischen.
- Bei aktivem LAN-Modus muss die Verbindungslogik diesen lokalen Schlüssel verwenden.
- MQTT-Status in der UI ausschließlich verbunden/nicht verbunden.

## Online-Authentifizierung

Bezeichnung: **„Online-Authentifizierung“**

Die vorhandene Bambu-Cloud-Authentifizierung bleibt erhalten.

### Anmeldung

- Bambu-E-Mail und Passwort.
- Falls Bambu dies verlangt: E-Mail-Verifizierungscode.
- Passwort niemals dauerhaft speichern.
- Lokal dürfen nur für die Sitzung erforderliche Daten gespeichert werden, insbesondere Access Token, numerische Bambu-User-ID und erforderliche Token-Metadaten.

### Ermittlung der User-ID

Die numerische Bambu-User-ID wird automatisch über

`/v1/design-user-service/my/preference`

ermittelt.

Keine manuelle Eingabe verlangen, wenn der Endpoint die ID liefert.

### Tokenprüfung

Token live gegen den Preference-Endpoint prüfen.

Die UI soll:

- gültige Verbindung/gültigen Token anzeigen;
- ungültige oder abgelaufene Tokens erkennen;
- bei Bedarf eine erneute Anmeldung verlangen.

## UI-Einbindung

Bambu Cloud ist direkt über das Hauptmenü erreichbar und keine versteckte, manuell einzugebende URL.

Bekannte relevante Dateien:

- `bambu_auth.py`
- `bambu_auth_routes.py`
- `templates/bambu_auth.html`
- `templates/base.html`
- `app_custom.py`

Vor Änderungen tatsächliche Imports und Routen prüfen.

## Sicherheit

Nicht in Git aufnehmen:

- Bambu-Passwörter;
- Access Tokens;
- Drucker-Zugangscodes;
- Session-Credentials;
- private Schlüssel;
- lokale Token-/Credential-Dateien.

## Kompatibilitätsregel

LAN-Änderungen dürfen Online-Authentifizierung nicht beschädigen und umgekehrt.
