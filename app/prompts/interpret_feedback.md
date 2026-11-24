{{context}}

## Aktueller Baum
{{tree}}

## Aufgabe: Rückmeldung umsetzen
Übersetze die Rückmeldung unten in geordnete Einzeländerungen (`changes`):
- `add`: neuen Knoten anlegen (`title` = Name des neuen Knotens, `parent` = `key` des Elternknotens oder `null` für die Hauptebene, `key: null` – der Dienst vergibt neue Schlüssel automatisch!). Soll ein neuer Knoten direkt Unterknoten erhalten, lege zuerst den Elternknoten per `add` an und setze bei den nachfolgenden Kinder-`add`s `parent` auf den exakten `title` dieses neuen Elternknotens.
- `remove`: bestehenden Knoten entfernen (`key` aus „Aktueller Baum“).
- `rename`: bestehenden Knoten umbenennen (`key` aus „Aktueller Baum“, `title` = neuer Name).
- `move`: bestehenden Knoten verschieben (`key` = zu verschiebender Knoten, `to` = Ziel-Elternknoten).
- `merge`: mindestens zwei bestehende Knoten zusammenlegen (`keys`, `title`).
- `split`: bestehenden Knoten aufteilen (`key`, `hint`).

Regeln:
- Setze alle für eine Operation nicht benötigten Felder auf `null`.
- Für bestehende Knoten nur Schlüssel (`k-...`) aus „Aktueller Baum“ verwenden; Knoten mit `[gesperrt]` und deren Unterknoten niemals ändern.
- Stelle niemals technische Rückfragen nach Knotenschlüsseln (`key`). Nutze `questions` nur, wenn der fachliche Wunsch selbst mehrdeutig oder widersprüchlich ist.
{{already}}
## Rückmeldung
{{text}}
