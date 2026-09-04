# OpenSpoolMan – Dokumentation

Diese Datei ist der einzige Einstiegspunkt für Projektkontext, Entwicklungsregeln und Architekturentscheidungen.

**Regel für Menschen und Coding-Agenten:** Vor Änderungen zuerst diese Datei lesen und anschließend nur die für die Aufgabe verlinkten Dokumente.

## Verbindliche Reihenfolge

1. [Design-Entscheidungen](design-entscheidungen.md) – verbindliche technische, organisatorische und Formatierungsentscheidungen.
2. [Agenten- und Arbeitsregeln](entwicklung/agenten.md) – Regeln für ChatGPT Work, Codex und andere Coding-Agenten.
3. Die zur Aufgabe passende Fachdokumentation.
4. Vor Änderungen immer den aktuellen Stand von `feature/NewFiles` prüfen.

Bei Widersprüchen gilt: aktuelle Nutzeranweisung → `design-entscheidungen.md` → aktueller Repository-Code für den Implementierungsstand → Fachdokumentation → historische Beschreibung.

## Projektarchitektur

- [Gesamtarchitektur](architektur/projektarchitektur.md)
- [NFC-Architektur](architektur/nfc.md)
- [API](referenz/api.md)

## AMSHelper / ESP32-S3

- [Aktueller Stand](amshelper/aktueller-stand.md)
- [PN532 / NTAG215](amshelper/pn532-ntag215.md)
- [Hardware](amshelper/hardware.md)
- [WLAN-Test](amshelper/wlan.md)
- [nanoFramework-Build](amshelper/nanoframework-build.md)

## Bambu Lab

- [Authentifizierung](bambu/authentifizierung.md)
- [MQTT und Signierung](bambu/mqtt-signierung.md)

## Entwicklung

- [Agenten- und Arbeitsregeln](entwicklung/agenten.md)
- [Entwicklungsablauf](entwicklung/entwicklungsablauf.md)
- [Sicherheit](entwicklung/sicherheit.md)
- [Work → Codex](entwicklung/work-codex.md)

## Referenz

- [API](referenz/api.md)
- [Screenshots](referenz/screenshots.md)

## Dokumentationsregeln

- Markdown-Dateien werden mit Windows-Zeilenenden **CRLF** gespeichert.
- Es gibt keine zweite Einstiegspunkt-Datei neben `docs/START.md`.
- Keine `AGENTS.md` im Repository-Root. Agentenregeln liegen unter `docs/entwicklung/agenten.md`.
- Dauerhafte Architektur-, Hardware-, Software-, UI-, Formatierungs- und Workflowentscheidungen werden in `docs/design-entscheidungen.md` gepflegt.
- Detaildokumente beschreiben Zustand und Umsetzung und definieren keine konkurrierende Zielarchitektur.
- Veraltete Alternativen werden entfernt oder ausdrücklich als verworfen markiert.
- Änderungen werden direkt auf `feature/NewFiles` gepflegt und committed; Patch-ZIPs werden nicht mehr als regulärer Übergabeweg verwendet.
