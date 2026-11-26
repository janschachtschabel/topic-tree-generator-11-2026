{{context}}
{{inputs}}

## Inhalte
{{items}}

## Aufgabe: Themenbaum aus den Inhalten bilden
Bilde aus den Inhalten oben einen Themenbaum nach den Regeln im Systemprompt. Er soll den tatsächlichen Bestand
ordnen: keine leeren Knoten und keine eigenen Knoten für einzelne Ausreißer oder Kleinstgruppen (Richtwert bei großen
Beständen: Blattknoten tragen ab etwa 5 Inhalte; bei kleinen Beständen unter ~30 Inhalten wähle kompakte, abdeckende
Gruppen, sodass jeder thematisch passende Inhalt klar unterkommt). Sehr große Gruppen (ab etwa 40 bis 60 Inhalten) in
trennscharfe Unterthemen teilen. Ein Thema im Anfragekontext grenzt ein; fachfremde Inhalte bekommen keine eigene
Gruppe.
Schreibe für jede Gruppe Titel, Kurztitel, Beschreibung (innerhalb der Wortspanne aus dem Anfragekontext) und
Schlagworte; halte die Form aus dem Anfragekontext ein (ohne explizite Breitenvorgabe richtet sich die Zahl der
Haupt- und Untergruppen nach den inhaltlichen Clustern im Bestand bis zur genannten Obergrenze, unter Einhaltung der
maximalen Ebenentiefe).
`order` und `levels`: das gewählte Ordnungsprinzip, `description`: Beschreibung des ganzen Baums.
