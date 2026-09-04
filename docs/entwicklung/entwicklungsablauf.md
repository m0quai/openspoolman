# Entwicklungs- und Testablauf

> Einstieg: [START.md](../START.md)

Das Projekt wird derzeit primär über **Visual Studio Debug** getestet. Docker-Rebuild/Compose nur verwenden, wenn die Aufgabe Docker/Produktion betrifft oder ausdrücklich verlangt wird.

## Vor Änderungen

1. `docs/START.md` und `docs/design-entscheidungen.md` lesen.
2. Aktuellen `feature/NewFiles`-Stand prüfen.
3. Unabhängige Nutzeränderungen erhalten.
4. Betroffene Dateien und Referenzen untersuchen.

## Implementierung

Änderungen auf die Aufgabe beschränken, Upstream-Kompatibilität erhalten, keine unnötigen Formatierungsänderungen, keine Secrets einführen und LAN-/Online-Modus erhalten, sofern nicht ausdrücklich anders entschieden.

## Danach

Diff und Secrets prüfen, verfügbare Tests ausführen, zwischen tatsächlich getesteten Punkten und offenen Laufzeittests unterscheiden und die Änderungen direkt auf `feature/NewFiles` committen.

Dauerhafte Architekturentscheidungen werden zusätzlich in `docs/design-entscheidungen.md` aktualisiert. Patch-ZIPs sind nicht mehr der reguläre Übergabeweg.
