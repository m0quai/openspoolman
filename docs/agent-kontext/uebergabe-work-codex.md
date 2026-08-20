# Übergabe von Work zu Codex

## Ziel

Das Repository soll jetzt mit ChatGPT Work und später mit Codex verwendet werden können, ohne Projektentscheidungen aus alten Unterhaltungen erneut zusammensuchen zu müssen.

## Dauerhafter Projektkontext

Der übertragbare Kontext liegt in:

- `/AGENTS.md`
- `/docs/agent-kontext/projektarchitektur.md`
- `/docs/agent-kontext/bambu-authentifizierung.md`
- `/docs/agent-kontext/bambu-mqtt-signierung.md`
- `/docs/agent-kontext/nfc-architektur.md`
- `/docs/agent-kontext/entwicklungsablauf.md`
- `/docs/agent-kontext/sicherheit.md`
- `/docs/agent-kontext/entscheidungsprotokoll.md`

Diese Dateien bleiben Bestandteil des Repositorys und werden bei dauerhaften Änderungen aktualisiert.

## Empfohlener Start einer neuen Aufgabe

Zu Beginn einer neuen Work- oder Codex-Aufgabe:

> Lies zuerst `AGENTS.md` und die relevanten Dateien unter `docs/agent-kontext/`. Prüfe danach den aktuellen Repository-Stand und `git status`. Der aktuelle Code ist die Quelle der Wahrheit für Implementierungsdetails; die Markdown-Dateien enthalten die festgelegten Architektur- und Arbeitsregeln. Überschreibe keine unabhängigen lokalen Änderungen.

## Warum Code und Kontext gemeinsam?

Die Markdown-Dateien verhindern Wissensverlust, sollen den Code aber nicht einfrieren.

Ein Agent kombiniert daher:

1. dauerhafte Entscheidungen aus den Markdown-Dateien;
2. aktuellen Implementierungsstand des Repositorys;
3. konkrete aktuelle Aufgabe.

## Kontext fortschreiben

Entsteht eine neue dauerhafte Entscheidung, wird die passende Kontextdatei aktualisiert.

Beispiele:

- neuer dauerhafter Konfigurationswert → Authentifizierungs-/Architekturdokumentation;
- geänderter Testablauf → Entwicklungsablauf;
- geänderte NFC-Grundregel → NFC-Architektur;
- neue Modulgrenze → Projektarchitektur und Entscheidungsprotokoll.

Dadurch übernimmt eine spätere Codex-Sitzung automatisch den zuvor mit Work aufgebauten Projektstand.
