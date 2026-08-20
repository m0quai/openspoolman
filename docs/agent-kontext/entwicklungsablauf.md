# Entwicklungs- und Testablauf

## Aktuelle Umgebung

Das Projekt wird derzeit primär über **Visual Studio Debug** getestet.

Nicht standardmäßig folgende Schritte verlangen:

- Docker-Image neu bauen;
- Docker Compose neu starten;
- Produktionscontainer neu deployen.

Docker-Schritte nur verwenden, wenn die Aufgabe tatsächlich Docker/Produktion betrifft oder ausdrücklich verlangt wird.

## Ablauf vor Änderungen

1. `AGENTS.md` lesen.
2. `git status` prüfen.
3. Unabhängige lokale Änderungen erhalten.
4. Betroffene Dateien tatsächlich untersuchen.
5. Alle Referenzen auf zu ändernde Konfigurationswerte, Routen, Funktionen und Templates suchen.

## Während der Implementierung

1. Änderungen auf die Aufgabe beschränken.
2. Upstream-Kompatibilität soweit sinnvoll erhalten.
3. Keine unnötigen Formatierungsänderungen.
4. Keine Secrets in Code oder Beispiele einführen.
5. LAN- und Online-Modus erhalten, sofern die Aufgabe keinen Modus ausdrücklich entfernt.

## Nach Änderungen

1. Gesamten Diff prüfen.
2. Auf Tokens, Zugangscodes, Passwörter und private Schlüssel prüfen.
3. Verfügbare Syntax-, Unit- oder statische Prüfungen ausführen.
4. Bei manuellen Tests Visual-Studio-Debug-Schritte angeben.
5. Klar unterscheiden zwischen tatsächlich getesteten Punkten und noch erforderlichen Laufzeittests.

## Patch-ZIP

Bei angefordertem Patch:

- sofort erzeugen;
- Pfade ab Repository-Root;
- kein zusätzliches `OpenSpoolMan/`-Verzeichnis;
- nur notwendige/geänderte Dateien;
- keine `README-PATCH.txt`;
- keine zusätzliche Änderungsdatei, sofern nicht ausdrücklich verlangt.

## Dokumentationspflege

Ändert eine Aufgabe eine dauerhafte Architekturentscheidung, soll die passende Kontextdatei ebenfalls aktualisiert werden. Dadurch bleiben Work und später Codex auf demselben Wissensstand.
