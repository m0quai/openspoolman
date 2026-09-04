# Übergabe zwischen ChatGPT Work, Codex und anderen Agenten

> Einstieg: [START.md](../START.md)

Der übertragbare Projektkontext liegt vollständig unter `docs/`. Jede neue Aufgabe beginnt mit `docs/START.md`; anschließend werden `docs/design-entscheidungen.md` und die relevanten Fachdokumente gelesen.

Der Agent kombiniert drei Quellen: dauerhafte Entscheidungen aus der Dokumentation, aktuellen Implementierungsstand aus `feature/NewFiles` und die konkrete aktuelle Aufgabe.

Entsteht eine neue dauerhafte Architektur-, Hardware-, Software-, UI-, Formatierungs- oder Workflowentscheidung, wird `docs/design-entscheidungen.md` aktualisiert. Fachdetails werden zusätzlich im passenden Dokument gepflegt.

Die frühere Root-`AGENTS.md` und das Verzeichnis `docs/agent-kontext/` sind keine Einstiegspunkte mehr.
