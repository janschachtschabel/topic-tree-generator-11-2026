{{context}}
{{inputs}}
## Ordnerbaum
{{folders}}

## Aufgabe: Ordnerstruktur verbessern
Die Ordner stammen aus einem Upload. Schlage nur Änderungen vor, die den Baum nach den Regeln im Systemprompt
klar verbessern: nichtssagende Namen ersetzen (z. B. „Neuer Ordner (2)“ anhand der enthaltenen Inhalte),
Ordner unter den fachlich passenden Elternordner verschieben, Doppelungen zusammenlegen, organisatorische
Ebenen (Jahr, „alt“, „neu“) durch fachliche ersetzen und Einzelkind-Ordner auflösen (Unterordner hochziehen oder
passende Geschwister darunter verschieben, sodass kein Ordner genau ein Kind hat).
Fachlich treffende Namen (z. B. „Optik“, „Linsen“) bleiben unverändert, auch wenn ein Inhalt nur einen Teilaspekt
behandelt; schlage keine Umbenennung auf den bisherigen Namen vor.
Erlaubte Operationen: `rename` (key, title), `move` (key, to oder null für die oberste Ebene), `merge` (keys, title), `add` (parent oder null, title)
für einen neuen gruppierenden Ordner. Verwende nur Schlüssel aus dem Ordnerbaum oder Schlüssel, die du mit `add`
angelegt hast, sobald sie zurückgemeldet sind; für neue Ordner nutze nur `add`. Ist nichts zu verbessern, gib
eine leere Liste zurück.
