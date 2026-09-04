# Bambu MQTT, Zertifikate und Signierung

> Einstieg: [START.md](../START.md) · Entscheidungen: [Design-Entscheidungen](../design-entscheidungen.md)

Dieser Bereich ist sicherheitskritisch. Protokolldetails werden aus aktuellem Quellcode und bestätigten Tests abgeleitet, nicht aus Vermutungen.

## LAN

Lokales MQTT verwendet `PRINTER_ACCESS_LAN`. Bestätigte LAN-Kommandos wie `pushall` und `ams_filament_setting` werden nicht durch die bestehende RSA-SHA256/X.509-Schicht geleitet.

## Online

Online verwendet `PRINTER_ACCESS_ONLINE`; vorhandene Signierungslogik bleibt aktiv, sofern ein gültiges Zertifikat vorhanden ist. RSA-SHA256/X.509 bleibt damit für den Online-/Cloud-Kontext relevant.

## Sicherheit/UI

Keine privaten Schlüssel, Tokens oder Zugangsdaten committen oder loggen. MQTT-Status in der UI ausschließlich verbunden/nicht verbunden; interne Logs dürfen detaillierter sein, solange sie keine Secrets enthalten.
