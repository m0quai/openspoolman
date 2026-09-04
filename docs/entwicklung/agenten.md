# Agenten- und Arbeitsregeln

> Einstieg immer über [START.md](../START.md). Verbindliche Architekturentscheidungen stehen in [Design-Entscheidungen](../design-entscheidungen.md).

Diese Regeln gelten für ChatGPT Work, Codex und andere Coding-Agenten.

## Vor jeder Änderung

1. `docs/START.md` lesen.
2. `docs/design-entscheidungen.md` lesen.
3. Relevante Fachdokumente lesen.
4. Aktuellen Stand von `feature/NewFiles` und betroffene Dateien prüfen.
5. Unabhängige Änderungen des Nutzers nicht überschreiben.
6. Aufrufer, Konfiguration, Templates und Abhängigkeiten ermitteln.
7. Kleinste konsistente Änderung durchführen.
8. Sinnvolle Tests mit vorhandenen Werkzeugen durchführen.
9. Diff auf Secrets und unbeabsichtigte Änderungen prüfen.
10. Änderungen direkt auf `feature/NewFiles` committen, sofern der Nutzer nichts anderes verlangt.

## Harte Projektregeln

- `app.py` nicht für projektspezifische Anpassungen ändern.
- Eigene Flask-/Bambu-Funktionalität über `app_custom.py`, Blueprints und separate Module.
- Keine aufgabenfremden Refactorings.
- Keine Secrets in Git.
- Visual Studio Debug ist derzeit der primäre Testweg.
- C#-`if` immer mit geschweiften Klammern.
- Markdown-Dokumentation mit Windows-CRLF.
- Neue dauerhafte Designentscheidungen zusätzlich in `docs/design-entscheidungen.md` eintragen.
- Keine Patch-ZIPs als regulären Übergabeweg; GitHub `feature/NewFiles` ist der gemeinsame aktuelle Stand.

## Prioritäten bei Widersprüchen

1. Explizite aktuelle Nutzeranweisung.
2. `docs/design-entscheidungen.md`.
3. Aktueller Repository-Code für den tatsächlichen Implementierungsstand.
4. Fachdokumente.
5. Historische Beschreibungen.
