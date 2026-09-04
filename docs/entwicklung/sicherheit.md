# Sicherheit und Umgang mit Geheimnissen

> Einstieg: [START.md](../START.md)

Keine echten Geheimnisse im Repository. Dazu gehören Bambu-Passwörter, Access Tokens, lokale Drucker-Access-Keys, WLAN-Passwörter, API-Schlüssel, Session-Cookies und private kryptografische Schlüssel.

Bambu-Passwort nur zur Anmeldung verwenden und nicht speichern. Access Token, numerische User-ID und erforderliche Metadaten dürfen entsprechend der Implementierung lokal gespeichert werden; Credential-Dateien müssen von Git ausgeschlossen bleiben.

In Dokumentation und Beispielkonfiguration ausschließlich erkennbare Platzhalter verwenden. Vor jedem Commit geänderte Dateien und Logs auf Tokens, Access-Keys, Passwörter, private Schlüssel und versehentlich erzeugte Credential-Dateien prüfen.
