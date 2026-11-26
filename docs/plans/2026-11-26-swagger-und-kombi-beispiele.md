# Swagger-Doku und Kombinationsbeispiele: Umsetzungsplan

> Für ausführende Agents: Aufgaben der Reihe nach mit superpowers:executing-plans abarbeiten, Checkboxen abhaken.

**Ziel:** `/docs` (OpenAPI) erklärt den Endpunkt und seine Optionen so, dass man ohne README aufrufen kann, und das
Beispiel-Dropdown enthält alle wichtigen Kombinationen. Die Test-UI zeigt Kombinationen als eigene Gruppe.

**Auftrag:** Jan, 26.11.2026 („Endpunkte in docs besser beschreiben … gemischte Use Cases wie Thema und Inhalte“).
Ziel-Version 2.2.0 (Changelog „Unreleased“).

**Architektur:** Nur Dokumentation und Beispiele; kein Verhalten ändert sich. Beschreibung als Markdown in
`app/api/v2_description.py`, Beispiele aufgeteilt in `app/api/examples.py` (Einzelfälle) und
`app/api/examples_combos.py` (Kombinationen). UI-Presets bekommen `combo: true`; das Dropdown gruppiert danach.

## Aufgaben

- [x] Endpunktbeschreibung: Use Cases mit Pflichtfeldern, Modi (create, refine, assign_only, describe), Rollen
      (`use`, `folders_use`), Kombinationstabelle mit Beispielnamen, wichtigste Optionen mit Standard, Antwort, Fehler.
      App-Beschreibung (Kopf von /docs) mit Kurzüberblick und Verweis auf die Legacy-Endpunkte.
- [x] Feldbeschreibungen von `Options` präzisieren (Standard, Wirkung, wann sinnvoll; `Item.use`, `Shape`, `Hints`
      waren schon ausreichend und sind über die /docs-Beschreibung erklärt);
      Schemas und `docs/datenformat.md` neu erzeugen.
- [x] Beispiele: Thema + Inhalte (nur einsortieren), Thema + Inhalte (Anregung + einsortieren), Thema + Lehrplan,
      Thema + Ordner, Dokument + Thema + Inhalte, Inhalte + Lehrplan, Inhalte + Ordner als Hinweis, Ordner verbessern
      + Lehrplan + lose Dateien, Ordner nur als Gliederung, refine mit Änderungen + Inhalten, Einsortieren, describe.
      Test: jedes Beispiel ist gültig; zusammen decken sie jeden use_case, jede Rolle, jeden folders_use-Wert,
      assign_only und describe ab; jedes Beispiel hat `description`.
- [x] Test-UI: Presets mit `combo: true`, Dropdown mit Gruppen „Grundbeispiele“/„Kombinationen“, Aufgabenkarten
      zeigen die Zahl der Kombinationen; neues Preset „Thema + Materialien nur einsortieren“. Test: jede Aufgabe außer
      assign/refine hat mindestens eine Kombination.
- [ ] Tests, Lint, Review, PR, CI, mergen.
