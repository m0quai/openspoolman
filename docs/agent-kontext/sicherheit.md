# Sicherheit und Umgang mit Geheimnissen

## Grundregel

Keine echten Geheimnisse im Repository.

Dazu gehören insbesondere:

- Bambu-Passwörter;
- Bambu Access Tokens;
- lokale Drucker-Access-Keys;
- API-Schlüssel;
- Session-Cookies;
- private kryptografische Schlüssel;
- Credential-Dateien mit echten Authentifizierungsdaten.

## Bambu Cloud

- Passwort nur für die Anmeldung verwenden und nicht speichern.
- Access Token, numerische User-ID und erforderliche Token-Metadaten dürfen entsprechend der bestehenden Implementierung lokal gespeichert werden.
- Token-/Credential-Dateien müssen von Git ausgeschlossen bleiben.
- Bei ungültigen/abgelaufenen Tokens erneute Anmeldung verlangen.

## Zertifikate und Signierung

- Private Schlüssel nicht hart codieren.
- Tokens/private Schlüssel nicht in Debug-Ausgaben schreiben.
- Bei Änderungen auch Fehler- und Logging-Pfade prüfen.

## Beispiele

In Dokumentation und Beispielkonfiguration ausschließlich eindeutig erkennbare Platzhalter verwenden.

## Vor Commit oder ZIP-Erstellung

Geänderte bzw. zu verpackende Dateien auf folgende Inhalte prüfen:

- Tokens;
- Access-Keys;
- Passwörter;
- private Schlüssel;
- versehentlich erzeugte Credential-Dateien.
