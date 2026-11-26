# Inhalte einsortieren und Knoten beschreiben: Umsetzungsplan

> **Für ausführende Agents:** Aufgaben der Reihe nach mit superpowers:executing-plans abarbeiten, Checkboxen abhaken.

**Ziel:** Ein bestehender (auch fremder) Themenbaum lässt sich als eigener Use Case nur mit Inhalten befüllen,
ohne dass sich Struktur oder Properties ändern. Zusätzlich beschreibt die neue Änderung `describe` ausgewählte
Knoten mit Baum-Kontext neu und ersetzt damit fachlich den alten Endpunkt `/generate-collection-description`.

**Architektur:** Keine neuen Endpunkte und kein neuer `mode`. Einsortieren bleibt `mode: refine` +
`options.assign_only: true`; `describe` ist ein neuer `ChangeOp` in `feedback.changes`, der die vorhandene
Stufe `describe_nodes` mit einem Knotenhinweis (`extra`) nutzt. Der Legacy-Endpunkt bleibt eingefroren.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, pytest; Test-UI in reinem JS (`node --test`).

**Entscheidung:** Jan, 26.11.2026, Entscheidungskarte „Beides (Einsortieren + describe)“. Version 2.2.0.

## Globale Vorgaben

- v1-Endpunkte bleiben format- und verhaltensgleich.
- `nodeId` wird unverändert durchgereicht, nie erzeugt oder umformatiert.
- Keine stillen Lücken: Ignorierte Eingaben ergeben `INPUT_IGNORED`/`FEEDBACK_IGNORED`.
- Prompts und API-Texte deutsch, Code/Kommentare englisch. Keine neue Abhängigkeit.

## Review-Fokus

1. Fremder Baum ohne `key`, ohne `generation`, mit `nodeId` je Knoten: Antwort hat dieselbe Struktur, dieselben
   `nodeId` und identische `properties` je Knoten; nur `contents` kommen hinzu.
2. `assign_only` mit geändertem `frame` gegenüber `generation.frame`: Properties bleiben trotzdem unverändert.
3. `assign_only` + `auto_metadata: true` gesendet: wird nicht ausgeführt, `INPUT_IGNORED`-Warnung.
4. `describe` auf gesperrten Knoten: `CHANGE_REJECTED`, Beschreibung bleibt.
5. `describe` auf Knoten, der schon eine Beschreibung hat: wird trotzdem neu beschrieben, Hinweis landet im Prompt.

---

### Aufgabe 1: `nodeId` an Sammlungsknoten durchreichen

**Dateien:** `app/schemas/request_v2.py` (`TreeNodeIn`), `app/domain/tree.py` (`Node`, `from_tree_in`),
`app/schemas/response_v2.py` (`NodeOut`), `app/pipeline/finalize.py` (`to_node_out`);
Test: `tests/pipeline/strategies/test_refine.py`, `tests/schemas/test_request_v2.py`.

**Schnittstelle:** `TreeNodeIn.node_id: str | None` (Alias `nodeId`, max 200), `Node.node_id: str | None = None`,
`NodeOut.node_id: str | None` (Alias `nodeId`, nur ausgegeben, wenn gesetzt).

- [ ] Test `test_node_ids_of_collection_nodes_pass_through_unchanged`: refine mit `changes` (rename) auf Baum
      mit `nodeId` je Knoten → jede Antwort-Node hat dieselbe `nodeId`; neu hinzugefügter Knoten hat keine.
- [ ] Test fehlschlagen sehen, Felder ergänzen, Test grün.
- [ ] Commit `feat: pass nodeId of collection nodes through refine`.

### Aufgabe 2: `assign_only` lässt Knoten unverändert

**Dateien:** `app/pipeline/finalize.py` (`node_properties`, `to_node_out` bekommen `keep_properties: bool`),
`app/pipeline/strategies/refine.py` (`apply_changed_frame` nicht unter `assign_only`),
`app/pipeline/orchestrator.py` (`infer_metadata` nicht unter `assign_only`),
`app/pipeline/input_checks.py` bzw. `warn_unused_inputs` (`INPUT_IGNORED` für `auto_metadata`);
Test: `tests/pipeline/strategies/test_refine.py`.

- [ ] Test `test_assign_only_into_foreign_tree_changes_nothing_but_contents`: Baum ohne Schlüssel/`generation`,
      `nodeId`, Properties ohne `cm:title`, langer Titel, `frame` mit Fach → `properties` je Knoten identisch zur
      Eingabe, Struktur gleich, `status` überall `unchanged`, Inhalt am Zielknoten.
- [ ] Test `test_assign_only_ignores_changed_frame` (Review-Fokus 2) und
      `test_assign_only_skips_auto_metadata_with_warning` (Review-Fokus 3).
- [ ] Umsetzen; Felder `shorttitle` der Antwort bleiben vertragsgemäß (≤ 20 Zeichen), nur `properties` bleiben roh.
- [ ] Commit `fix: assign_only leaves node properties untouched`.

### Aufgabe 3: Änderung `describe`

**Dateien:** `app/schemas/common.py` (`ChangeOp.describe`), `app/schemas/request_v2.py`
(`_REQUIRED_BY_OP[describe] = ("key",)`, `hint` als Grundlage), `app/domain/ops.py` (`_Applier.describe`:
gesperrt → abgelehnt, sonst `record`), `app/pipeline/strategies/refine.py` (`describe`-Schlüssel in `refresh`,
Hinweise als `extra` an `describe_nodes`); Test: `tests/domain/test_ops.py`, `tests/pipeline/strategies/test_refine.py`.

- [ ] Test `test_describe_rewrites_description_with_hint`: Knoten mit Beschreibung, `describe` mit `hint` →
      ein `describe_nodes`-Aufruf, Prompt enthält den Hinweis, neue Beschreibung, `changes[0].op == "describe"`,
      Status `changed`, andere Knoten unverändert.
- [ ] Test `test_describe_on_locked_node_is_rejected` (Review-Fokus 4), `describe` ohne `key` → 422.
- [ ] Umsetzen; `interpret_feedback` (Freitext) bleibt ohne `describe`.
- [ ] Commit `feat: describe change regenerates node descriptions with tree context`.

### Aufgabe 4: Sichtbarer Use Case in UI, README und Doku

**Dateien:** `app/ui/static/{index.html,app.js,form.js,payload.js,changes.js,i18n.js}`,
`app/ui/presets_refine.py` (neue Aufgabe `assign`), `README.md`, `docs/api.md`, `docs/examples/`, `CHANGELOG.md`,
`pyproject.toml` (2.2.0); Tests: `tests/ui_js/payload.test.cjs`, `tests/api/test_ui_presets_form.py`.

- [ ] UI-Aufgabe „Inhalte einsortieren“ (`task: "assign"`): Basis-Baum (JSON/übernommen) + Materialien zum
      Einsortieren; Anfrage = `refine` + `assign_only: true`, ohne `feedback`.
- [ ] JS-Test: `build({task: "assign", ...})` ergibt `mode: "refine"`, `options.assign_only: true`, keine `feedback`;
      ohne Basis → `err.currentTreeRequired`; ohne Materialien → Fehler.
- [ ] Vorlagen: bisherige `assign_only` nach `assign` verschieben, neue „Fremden Baum befüllen (edu-sharing)“ mit
      `nodeId` und ohne Schlüssel; `describe` im Änderungs-Editor und als Vorlage unter „Baum ändern“.
- [ ] README: Use Case „Sort items into an existing tree“ und „Describe nodes“; docs/api.md: Entscheidungstabelle,
      `describe`, `nodeId` an Knoten; Changelog 2.2.0.
- [ ] Commit(s) `feat: assign task in the test UI`, `docs: assign into an existing tree and describe`.

### Aufgabe 5: Abschluss

- [ ] `uv run pytest -q`, `uv run ruff check`, `uv run ruff format --check` grün.
- [ ] Review, PR, grüne CI, mergen (Freigabe laut Projektregel).
