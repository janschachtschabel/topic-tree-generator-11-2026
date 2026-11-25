# Test-UI: Aufgaben-Navigation, Kombinationen, gezielte Änderungen

Stand: 2026-11-25 · Status: Ansatz 1 von Jan gewählt (mit Prüfauftrag „kann das alles abbilden?“, siehe
Abdeckung unten)

## Anlass und Ziel

Jan will inhaltlich mit dem Dienst arbeiten. Dafür muss die Test-UI unter `/ui/`

1. gezielte Änderungen an einem bestehenden Baum (`mode: refine`, `feedback.changes`) ohne JSON-Handarbeit
   eingeben und testen lassen,
2. Kombinationen von Use Cases (z. B. Thema + Materialien) einfach eingeben lassen,
3. optisch dem UI des Kompendiale-Texte-Dienstes folgen,
4. mit Beispielen kommen, die jede Aufgabe und jede sinnvolle Kombination abdecken.

Erfolg: Jede Option des Requests ist im UI erreichbar, die häufigen ohne JSON; jede Aufgabe hat mindestens ein
lauffähiges Beispiel; ein erzeugter Baum lässt sich mit zwei, drei Klicks gezielt ändern.

Nicht-Ziele: keine Änderung am API-Vertrag (v1 und v2 bleiben wie sie sind), keine Persistenz, kein Build-Schritt,
keine externen Bibliotheken oder CDNs.

Anti-Ziele: Ein UI, das Kombinationen erlaubt, die der Dienst nicht versteht; ein Formular, das stillschweigend
Felder verwirft.

## Bestandsaufnahme

- Der Endpunkt kann gezielte Änderungen: `refine` mit `current_tree` und `feedback.changes`
  (`add`, `remove`, `rename`, `edit`, `move` inkl. Hauptebene, `merge`, `split`), `feedback.text`, `feedback.locked`.
  Im UI nur als JSON-Textfeld; kein Beispiel nutzt Operationen.
- Kombinationen laufen über `items[].use` (`structure`/`content`). Im UI nur als JSON-Array.
- UI: ein langes Formular mit allen Feldern gleichzeitig (Modus- und Use-Case-Auswahl oben, sieben Akkordeons).
  `app.js` hat 762 Zeilen (Regel: ≤ ~300).
- Beispiele (`app/ui/presets.py`): 9; es fehlen gezielte Änderungen, Dokument + Thema, Ordner + lose Dateien,
  Änderung + neue Materialien, geänderter Rahmen beim Weiterentwickeln, Elementar- und Hochschulbeispiel.

## Ansätze

1. **Ausgangslage + Zusätze (empfohlen):** Navigation nach Ausgangslage (Thema, Dokument, Ordner, Inhalte gruppieren,
   Baum ändern). Darunter eine Gruppe „Zusätzlich einbeziehen“ mit Häkchen, die Felder einblenden. Bildet die API
   1:1 ab (ein `use_case` plus optionale Materialien mit `use`).
2. **Freier Baukasten:** beliebige Eingaben anhaken, `use_case` wird abgeleitet. Flexibel, aber unklar, welche
   Strategie läuft.
3. **Feste Kombi-Einträge:** eigene Navigationspunkte je Kombination. Einfach, aber viele Einträge, nicht vollständig.

Entscheidung: Ansatz 1 (Jan, 2026-11-25). Der Rest dieses Dokuments beschreibt Ansatz 1.

## Abdeckung: kann „Ausgangslage + Zusätze“ alles abbilden?

Geprüft gegen `TopicTreeRequestV2`, `input_checks.py`, `inputs_block.py` und die Strategien. Ergebnis: ja, wenn es
zwei Materiallisten gibt (prägen die Struktur / nur einsortieren) und ein Strukturdokument auch als Zusatz geht.

| Ausgangslage | `use_case`/`mode` | Zusätze im Formular | Ergebnis im Request |
|---|---|---|---|
| Thema | topic/create | Materialien als Anregung · Materialien einsortieren · Dokument als Anregung | Liste A `use: [structure, content]`, Liste B `use: [content]`, Dokument `use: [structure]` mit Volltext |
| Dokument | document/create | Thema als Rahmen · Materialien einsortieren | Dokument `structure` (Text oder `fulltext.ref`), Liste B |
| Ordner | folders/create | Ordner verbessern · Dokument als Leitlinie (nur mit Verbessern) · lose Materialien einsortieren | `folders` + daraus erzeugte Datei-Items, `improve`, Dokument `structure`, Liste B |
| Inhalte gruppieren | contents/create | Thema als Rahmen · Materialien nur einsortieren | Liste A (Pflicht) `[structure, content]`, Liste B `[content]` |
| Baum ändern | refine, `use_case` aus der Basis | Änderungen · Freitext · Sperren · nur einsortieren · neue Materialien | `current_tree`, `feedback.*`, `assign_only`, Liste B; geänderter Rahmen wirkt über `frame` |

Überall: Rahmen, Form, Hinweise, Zuordnungsoptionen, `auto_metadata`, `extra_topics`, Token.
Materialien können statt Zeilen auch per Link (`items_ref`) kommen.

Nur über die JSON-Ansicht erreichbar (bewusst, weil selten): `nodeId` je Material, Volltexte je Material, mehrere
Strukturdokumente, eigene Properties, Items mit nur `use: [structure]` außer dem Dokument. Die JSON-Ansicht zeigt
stets die vollständige Anfrage und kann frei bearbeitet abgeschickt werden; damit bleibt jede Option erreichbar.

## Aufbau

### Linke Seitenleiste

- Kopf: „Themenbaum testen“, darunter Dienstversion und Server-Grenzen; DE/EN-Umschalter.
- **WAS ERZEUGEN?** Navigation: Thema · Dokument · Ordner · Inhalte gruppieren · Baum ändern.
  Ein Navigationspunkt setzt `mode` und `use_case` (Baum ändern: `refine`, `use_case` aus `current_tree.generation`,
  sonst `topic`).
- **Beispiel laden** (Dropdown, nur Beispiele dieser Aufgabe) mit Hilfetext „Füllt die Felder; erzeugt wird erst mit
  dem Knopf unten.“
- Felder der Aufgabe, je mit kurzem Hilfetext:
  - Thema: Thema (Pflicht).
  - Dokument: Markdown-Text oder HTTPS-Link (`fulltext.ref`), optional Thema, Ordnungsprinzip.
  - Ordner: Ordnerbaum als eingerückter Text (eine Zeile je Ordner, zwei Leerzeichen je Ebene, `- Titel` ist eine
    Datei im Ordner darüber). Häkchen „Ordnerstruktur verbessern“ (`improve`).
  - Inhalte gruppieren: optional Thema (Rahmen), Materialien (Pflicht).
  - Baum ändern: Basis (letztes Ergebnis übernehmen, Beispiel oder JSON einfügen), Änderungsliste, Freitext-Feedback,
    gesperrte Äste, „Nur einsortieren“ (`assign_only`).
- **Rahmen**: Fächer (Chips), Bildungsstufe, Zielgruppe – für alle Aufgaben.
- **ZUSÄTZLICH EINBEZIEHEN** (Häkchen, je nach Aufgabe):
  - „Materialien einsortieren“ (alle Aufgaben außer Inhalte gruppieren, dort immer an) → Materialeditor.
  - „Materialien als Anregung für die Struktur“ (nur Thema) → setzt `use: ["structure","content"]`.
  - „Zusatzthema Allgemeines vorn“ / „Methodik & Didaktik hinten“ (`extra_topics`).
  - „Metadaten je Knoten automatisch“ (`auto_metadata`).
- Aufklappbar: **Form** (Ebenen, Breiten, Wörter je Beschreibung), **Hinweise** (Kontext, Einschließen,
  Ausschließen, Ordnung, Sprache), **Zuordnung** (Mehrfachzuordnung, Mindestkonfidenz), **Anmeldung** (Token),
  **Anfrage als JSON** (zeigt die erzeugte Anfrage; „JSON bearbeiten“ schaltet auf freie Eingabe um, damit jede
  Option und `items_ref` pflegbar bleibt).
- Großer Primärknopf unten, fest am Rand: „Themenbaum erzeugen“ bzw. „Änderungen anwenden“.

### Materialeditor

Zwei Listen mit gleichem Format: **A „prägen die Struktur“** (`use: [structure, content]`) und **B „nur
einsortieren“** (`use: [content]`). Eine Zeile je Material: `Titel | Schlagwort, Schlagwort | Kurzbeschreibung`
(Teile nach dem Titel optional). Daraus werden `items` mit fortlaufender `id` (`a1`, `a2`, … bzw. `b1`, …),
`cm:title`, `cclom:general_keyword`, `cm:description`.
Daneben „Als JSON bearbeiten“ für Volltexte, `nodeId` und eigene `use`-Werte. Zeilen, die nicht passen, ergeben
eine Fehlermeldung mit Zeilennummer, nie ein stilles Weglassen.

### Änderungseditor (Baum ändern)

Liste von Operationen; je Zeile: Operation (Dropdown, deutsch beschriftet), Knoten (Dropdown aus der Basis, Titel mit
Einrückung), dann nur die Felder, die die Operation braucht (neuer Titel, Ziel, zweiter Knoten, Hinweis, Beschreibung).
Pflichtfelder wie in `_REQUIRED_BY_OP`; fehlende werden vor dem Absenden gemeldet. Im Ergebnisbaum hat jeder Knoten
kleine Aktionen „Sperren“ und „Ändern …“; „Ändern …“ fügt eine Operationszeile mit diesem Knoten hinzu.

### Rechte Seite

- Statuszeile oben („Bereit“, „Wird erzeugt … 11,3 s“, „Fertig: topic · create · 28,1 s“).
- Ladekarte mit Spinner, Laufzeit, Hinweis zur Dauer und Abbrechen-Knopf.
- Ergebniskopf: Titel, Knöpfe „JSON kopieren“, „JSON speichern“, „Als Basis für Änderungen“.
- Kennzahlenkarte in Gruppen: QUALITÄT (Knoten je Ebene, beschrieben %, Warnungen, Duplikate, zugeordnet,
  nicht zugeordnet), KOSTEN (Tokens gesamt, davon Cache), ZEIT (Dauer, LLM-Aufrufe, Fehlversuche), Modell.
- Aufklappbare Karten: Hinweise & Rückfragen, Änderungen, Nicht zugeordnet, Themenbaum (offen), Anfrage/Antwort-JSON.
- Optik: heller grauer Hintergrund, weiße Karten mit feinem Rand, Petrol als Akzentfarbe, Kapitälchen-Labels für
  Gruppen, Systemschrift.

## Beispiele (Soll)

Je Aufgabe ein Feld `task` im Preset, das Dropdown filtert danach.

| Aufgabe | Beispiele |
|---|---|
| Thema | Optik Sek I (Zusatzthemen, Include/Exclude); Berufsbildung Kfz (Lernfelder); BNE fächerübergreifend (auto_metadata); **Kita: Jahreszeiten** (Elementar, 2 Ebenen); **Hochschule: Einführung Statistik**; Thema + Materialien als Anregung und zum Einsortieren |
| Dokument | Lehrplan Physik mit Seitenmarken + Material; **Dokument + Thema als Rahmen** |
| Ordner | Upload verbessern; **Ordner + lose Dateien einsortieren** |
| Inhalte gruppieren | 12 Materialien inkl. Off-Topic; **Materialien teils nur einsortieren** (`use: content`) |
| Baum ändern | Freitext + gesperrter Ast; **Gezielte Änderungen (umbenennen, verschieben auf Hauptebene, zusammenführen, aufteilen, löschen, Beschreibung ändern)**; **Änderung + neue Materialien**; Nur einsortieren; **Rahmen ändern** (andere Bildungsstufe) |

Alle Beispiele werden wie bisher gegen das v2-Schema und `check_request` getestet; neu wird geprüft, dass jede
Aufgabe Beispiele hat und jede Operation in mindestens einem Beispiel vorkommt.

## Technik

- Weiter ohne Build und ohne Abhängigkeiten. `app.js` wird nach Verantwortung geteilt (je ≤ ~300 Zeilen):
  `payload.js` (Formular → Anfrage, rein), `parsers.js` (Material- und Ordnerzeilen, rein),
  `changes.js` (Operationseditor), `result.js` (Ergebnis, Kennzahlen), `app.js` (Steuerung).
- Reine Funktionen (Parser, Anfrageaufbau) bekommen Tests mit dem eingebauten Node-Testläufer (`node --test`),
  aufgerufen aus pytest; ohne `node` wird der Test übersprungen. Keine neue Abhängigkeit.
- Bestehende UI-Tests bleiben sinngemäß (keine CDNs, `hidden`-Regel, DE/EN, Duplikat-Markierung, Grenzen).
- Prüfung im Browser mit Playwright gegen den Stub (`tests/stub_openai.py`), Screenshots für Jan.

## Dem Umsetzer überlassen

Genaue Farben und Abstände, Texte der Hilfezeilen, Reihenfolge der aufklappbaren Bereiche, EN-Übersetzungen.
