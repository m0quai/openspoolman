# Bambu MQTT, Zertifikate und Signierung

## Kontext

Die Bambu-Cloud-Authentifizierung bildet die Grundlage für authentifizierte Bambu-MQTT-Kommandos. Die festgelegte technische Richtung umfasst **RSA-SHA256 / X.509-Signierung**.

Dieser Bereich ist sicherheitskritisch. Protokolldetails nicht aus Vermutungen rekonstruieren, wenn der aktuelle Quellcode untersucht werden kann.

## Relevanter Code

Bekannte Datei:

- `bambu_certificate.py`

Zusätzlich suchen nach:

- Zertifikatsimports;
- Signierungsfunktionen;
- MQTT-Kommandoaufbau;
- MQTT-Verbindungs-/Authentifizierungslogik;
- Verwendung von Token und User-ID;
- Verzweigung LAN/Online;
- Speicherpfaden für Zertifikate und Schlüssel.

## Anforderungen

- Private Schlüssel, Tokens und Zugangsdaten niemals committen.
- Kein hart codiertes Schlüssel-/Zertifikatsmaterial.
- Secrets nicht in Logs ausgeben.
- LAN- und Online-Authentifizierung sauber unterscheiden.
- Bambu-User-ID und Token-Metadaten nur dort verwenden, wo die tatsächliche Implementierung sie benötigt.
- Fehler differenziert behandeln, statt jeden Fehler lediglich als MQTT-Trennung darzustellen.

## MQTT-Status in der UI

Nur:

- verbunden;
- nicht verbunden.

Die frühere gelbe/intermediäre Statusanzeige bleibt entfernt.

Interne Logs dürfen detailliertere Zustände enthalten, solange keine Geheimnisse offengelegt werden.

## Vorgehen bei Änderungen

1. `bambu_certificate.py` prüfen.
2. Alle Aufrufer ermitteln.
3. MQTT-Verbindungs- und Kommando-Code untersuchen.
4. Aktiven Authentifizierungsmodus berücksichtigen.
5. Passenden Access-Key-/Token-/Zertifikatsweg prüfen.
6. Änderung eng begrenzen.
7. Logs auf Secret-Leaks prüfen.
8. Soweit möglich über Visual Studio Debug testen.
