{{context}}

## Baum
{{tree}}

## Aufgabe: Inhalte zuordnen
Ordne jeden unten genannten Inhalt nach den Regeln im Systemprompt den passenden Knoten zu (Schlüssel aus „Baum“).
Passt ein Inhalt fachlich zu einem Oberknoten, aber zu keinem seiner Unterknoten genau, ordne ihn dem passenden
Oberknoten zu. Gib je Inhalt seine `id`, die Knoten mit Konfidenz (`nodes`), `off_topic: true` für fachfremde Inhalte
und `excluded: true` für Inhalte, die unter „Ausschließen“ im Anfragekontext fallen. Gibt es keinen passenden Knoten,
bleibt `nodes` leer.

{{items}}
