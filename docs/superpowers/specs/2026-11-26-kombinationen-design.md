# Design: Kombinationen ohne stille Lücken (26.11.2026)

## Ziel und Warum
Ein späterer Chatbot sammelt Thema, Gliederungsdokumente, Inhalte und eine Ordnerstruktur getrennt ein und lässt
Nutzer je Element markieren (Gliederung, Inhalt, beides, keins). Jede Kombination soll möglich sein; nichts, was
gesendet wird, darf still wegfallen (Kombinationsgebot, Jan 26.11.2026).

## Grundregel
`use_case` bestimmt die Quelle, die das Gerüst bildet. Die Rollen (`use` je Item, `folders_use` für die ganze
Ordnerstruktur) bestimmen, wie alle übrigen Quellen einfließen.

## Ansätze
- **A (gewählt):** `folders_use` – ein Feld für die ganze Ordnerstruktur, gleiche vier Werte wie `use`, Standard
  `["structure", "content"]`. Fügt sich ins Rollenmodell; der Chatbot überträgt seine Markierung direkt.
- B: globaler Schalter `options.combine: primary | all` – grob, doppelt sich mit den Item-Rollen.
- C: immer alles kombinieren – Ordner ließen sich nicht mehr als reine Ablage mitschicken.

## Verhalten
| Fall | Vorher | Neu |
|---|---|---|
| Ordner bei `topic`/`document`/`contents`, Rolle Gliederung | still verworfen | Ordnerbaum als ergänzende Eingabe der Strukturplanung |
| Ordner, Rolle Inhalt | still verworfen | Ordnerpfad der Datei als Hinweis bei der Zuordnung |
| Ordner, `folders_use: []` | – | angenommen, nicht genutzt, `INPUT_IGNORED` |
| `use_case: folders` ohne Rolle Inhalt | – | Ordnerzuordnung nicht übernommen, Dateien werden neu einsortiert |
| `use_case: folders` ohne Rolle Gliederung | – | `422 INVALID_INPUT` (Ordner sind dort das Gerüst) |
| `Item.path` | ungenutzt | Hinweis bei der Zuordnung |
| Lehrplan mit Text bei `contents` | nur Titel | Auszug fließt in die Gruppenbildung |
| Gliederungsdokument ohne Text bei `document` | still verworfen | ergänzende Eingabe der Gliederung |
| `refine` mit neuen Gliederungsdokumenten oder Ordnern | still ignoriert | `INPUT_IGNORED` mit Hinweis auf Rückmeldung |
| `assign_contents: false` mit Inhalten | still weder platziert noch gelistet | `INPUT_IGNORED` |
| Thema + Lehrplan bei `topic` | nur Anregung (5 Auszüge) | bleibt; dokumentiert in der Chatbot-Tabelle |

Zusätzlich: Einzel-Unterpunkte bei `contents` werden aufgelöst, „Allgemeines“/„Methodik und Didaktik“ bekommen eine
Inhaltsdefinition, die Test-UI erlaubt mehrere Dokumente und Ordner bei allen Aufgaben, neue Musterszenarien für
Kombinationen, und ein Test lädt jedes Beispiel ins Formular (alle Daten links sichtbar).

## Nicht-Ziele
Den Baum bei `refine` automatisch an einen neuen Lehrplan angleichen (eigenes Feature). Ein `use_case: auto`.

## Dem Umsetzer überlassen
Wortlaut der Prompt-Blöcke, Grenzen für Auszüge (an `inputs_block.py` angelehnt).
