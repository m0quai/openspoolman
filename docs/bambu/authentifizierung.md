# Bambu-Authentifizierung

> Einstieg: [START.md](../START.md) · Entscheidungen: [Design-Entscheidungen](../design-entscheidungen.md)

## Lokaler LAN-Modus

Standardmodus. Direkte Verbindung zum Drucker im LAN. Vorhandene Drucker-IP wird vorbelegt. Eigener Access-Key: `Printer Access LAN`, Konfigurationsschlüssel `PRINTER_ACCESS_LAN`. MQTT-Status nur verbunden/nicht verbunden.

## Online-Authentifizierung

Bambu-E-Mail/Passwort und ggf. E-Mail-Verifizierungscode. Passwort wird nicht gespeichert. Lokal dürfen Access Token, numerische User-ID und erforderliche Token-Metadaten gespeichert werden.

User-ID und Tokenprüfung erfolgen über `/v1/design-user-service/my/preference`. Ungültige/abgelaufene Tokens führen zur erneuten Anmeldung.

Bambu Cloud ist direkt über das Hauptmenü erreichbar.

## Konfiguration

- `PRINTER_CONNECTION_MODE=LAN|ONLINE`, Default `LAN`
- `PRINTER_ACCESS_LAN`: lokaler Drucker-Access-Code
- `PRINTER_ACCESS_ONLINE`: bestehender Online-/Cloud-Weg
- `PRINTER_CODE`: rückwärtskompatibler aktiver Wert

Beim Moduswechsel verwenden MQTT und lokaler FTPS-Zugriff denselben aktiven Access-Code.

Keine Passwörter, Tokens, Zugangscodes, Session-Credentials oder private Schlüssel in Git.
