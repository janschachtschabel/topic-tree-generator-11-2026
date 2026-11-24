{{context}}
{{inputs}}
## Aufgabe: Vollständiges Titel-Grundgerüst des Themenbaums planen

1. Ordnungsprinzip: {{order_instruction}} Nenne die Bezeichnung der Begriffsart je Ebene in `levels`
   (z. B. „Themenfeld“, „Thema“, „Fachbegriff“) und begründe die Wahl in einem Satz in `rationale`.
2. Erzeuge {{main_min}} bis {{main_max}} reguläre Hauptthemen, nur so viele, wie fachlich trennscharf sind.
   Falls im Anfragekontext Zusatzthemen genannt sind („Allgemeines“ vorn, „Methodik und Didaktik“ hinten),
   nimm sie zusätzlich mit passenden Unterthemen auf.
3. {{children_instruction}}
4. Nur Titel und Kurztitel (max. 20 Zeichen); Beschreibungen und Schlagworte entstehen danach parallel je Knoten.
5. **Keine Duplikate im gesamten Baum**: Jeder Knotentitel darf über alle Ebenen und Äste hinweg nur genau einmal
   vorkommen. Gehört ein Begriff fachlich zu zwei Ästen, ordne ihn dem Schwerpunkt-Ast zu oder benenne beide
   Knoten kontextspezifisch und trennscharf (z. B. „Einfallswinkel am Spiegel“ vs. „Brechungswinkel“).
6. **Ausgewogene Tiefe**: Alle Äste sollen die gewünschte Tiefe erreichen (Unterschied höchstens 1 Ebene).
7. `description`: Beschreibung des gesamten Themenbaums nach den Beschreibungsregeln.
8. `from_inputs`: true nur für Hauptthemen, die du ausschließlich wegen der ergänzenden Eingaben aufgenommen hast.
