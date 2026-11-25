# Direktvergleich Alt (`POST /generate-topic-tree`) vs. Neu (`POST /v2/topic-tree`) über 3 Themen

Stand: **25.11.2026** · Commit: `8291a06` (`v2.0.0`) · Modell: **`gpt-6-luna`** (OpenAI nativ, `SERVICE_MODE=standalone`)

## 1. Versuchsaufbau

Drei fachlich und didaktisch unterschiedliche Themen aus **MINT (Sek I)**, **Gesellschaftswissenschaften (Sek II)** und **Beruflicher Bildung (Kfz-Mechatronik)** wurden jeweils unmittelbar nacheinander über den alten v1-Endpunkt (`POST /generate-topic-tree`) und den neuen v2-Endpunkt (`POST /v2/topic-tree`, `LLM_PARAM_FAMILY=common`, `LLM_REASONING_EFFORT=none`, `LLM_OUTPUT_MODE=json_schema`) mit äquivalenten Strukturvorgaben (3 Ebenen, Zielwortlänge `60` Wörter) ausgeführt:

1. **Physik (Sek I):** *„Optik für die Sekundarstufe I, alltagsnah, mit Experimenten“* — `6 × 3 × 3` (**78 Knoten**, inkl. `Allgemeines` vorn)
2. **Politik (Sek II):** *„Demokratie, Grundrechte und politisches System der Bundesrepublik Deutschland“* — `5 × 3 × 3` (**65 Knoten**, ohne Zusatzthema)
3. **Berufsbildung (Kfz-Technik):** *„Elektromobilität und Hochvoltsysteme in der Kfz-Mechatronik“* — `5` Hauptthemen inkl. `Methodik und Didaktik` hinten (`5 × 3 × 2` = 50 Knoten in v1; `children: 2..3` = 35 Knoten in v2)

Für v1 wurden die exakten Token- und Cache-Werte direkt an der OpenAI-Client-Schnittstelle mitgeschnitten (da das eingefrorene v1-Antwortschema kein `usage`-Feld enthält).

---

## 2. Messergebnisse: Laufzeit, Aufrufe & Tokenverbrauch

| Thema | Endpunkt | Knoten (`E1/E2/E3`) | Dauer | LLM-Calls | Input ungecacht | Input gecacht (Quote) | Output-Tokens | Gesamt-Tokens | Tokens / Knoten (davon Output) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **1. Physik Optik (Sek I)** | **v1** alt | **78** (`6/18/54`) | 41,9 s | 25 | 25.673 | 0 (**0,0 %**) | 33.876 | 59.549 | 763 (**434**) |
| **1. Physik Optik (Sek I)** | **v2** neu | **78** (`6/18/54`) | **24,5 s** | **9** | **13.323** | **13.545 (50,4 %)** | **12.026** | **38.894** | **499 (154)** |
| **2. Politik Demokratie (Sek II)** | **v1** alt | **65** (`5/15/45`) | 40,2 s | 21 | 21.647 | 0 (**0,0 %**) | 31.943 | 53.590 | 824 (**491**) |
| **2. Politik Demokratie (Sek II)** | **v2** neu | **65** (`5/15/45`) | **25,0 s** | **8** | **6.896** | **15.582 (69,3 %)** | **10.383** | **32.861** | **506 (160)** |
| **3. Kfz Elektromobilität (Beruf)** | **v1** alt | **50** (`5/15/30`) | 34,4 s | 21 | 21.803 | 0 (**0,0 %**) | 25.939 | 47.742 | 955 (**519**) |
| **3. Kfz Elektromobilität (Beruf)** | **v2** neu | **35** (`5/10/20`) | **17,9 s** | **5** | **3.879** | **9.777 (71,6 %)** | **5.530** | **19.186** | **548 (158)** |

### Relative Einsparung von v2 gegenüber v1 (bei identischer Knotenzahl in Thema 1 & 2)

| Kennzahl | Thema 1: Physik (78 vs. 78 Knoten) | Thema 2: Politik (65 vs. 65 Knoten) | Thema 3: Berufsbildung (pro Knoten) |
|---|---:|---:|---:|
| **Antwortzeit (Wandzeit)** | **−41,5 %** (24,5 s statt 41,9 s) | **−37,9 %** (25,0 s statt 40,2 s) | **−48,0 %** gesamt (17,9 s statt 34,4 s) |
| **Anzahl LLM-Aufrufe** | **−64,0 %** (9 statt 25 Calls) | **−61,9 %** (8 statt 21 Calls) | **−76,2 %** (5 statt 21 Calls) |
| **Ungecachte Input-Tokens** | **−48,1 %** (13.323 statt 25.673) | **−68,1 %** (6.896 statt 21.647) | **−82,2 %** gesamt |
| **Output-Tokens je Knoten** | **−64,5 %** (154 statt 434 Tok./Knoten) | **−67,4 %** (160 statt 491 Tok./Knoten) | **−69,6 %** (158 statt 519 Tok./Knoten) |

---

## 3. Qualitätsvergleich der Ergebnisse

| Qualitätskriterium | **v1** (`/generate-topic-tree`) | **v2** (`/v2/topic-tree`) |
|---|---|---|
| **Duplikate im Baum** | `0` in allen 3 Läufen *(aber ohne deterministischen Schutz bei größeren Bäumen)* | `0` in allen 3 Läufen *(zusätzlich deterministisch garantiert durch `eliminate_generated_duplicates`)* |
| **Wortlängen-Korridor (Ziel: 60 Wörter)** | Breitere Streuung: **38 – 80 Wörter** (Median 53 – 55,5) | Enger Korridor ohne Ausreißer: **44 – 73 Wörter** (Median 53 – 59), **`0` Warnungen** in allen 3 Läufen |
| **Schlagworte je Knoten** | Ø 4,5 – 4,7 Keywords | Ø 4,7 – 4,9 fachliche Keywords im Singular (bereinigt um Plattform-Stoppwörter) |
| **Prägnanz der Haupttitel (1–4 Wörter)** | Lange Doppeltitel mit „und“: z. B. *„Verfassungsorgane und Kontrolle staatlicher Macht“*, *„Wahlen und Parteien im demokratischen Wettbewerb“* | Klare, sammlungstaugliche Fachtitel: *„Demokratische Prinzipien“*, *„Grundrechte“*, *„Staatsorgane“*, *„Politische Willensbildung“*, *„Politische Ordnung“* |
| **Kanonische Zusatzthemen (`extra_topics`)** | Hat `Methodik und Didaktik` in Thema 3 eigenmächtig in *„Lernplanung und Werkstattdidaktik“* umbenannt | Setzt exakt **`Allgemeines`** (vorn, Thema 1) bzw. **`Methodik und Didaktik`** (hinten, Thema 3) und hält die E1-Gesamtzahl (`6` bzw. `5`) ohne `SHAPE_WIDTH`-Warnung exakt ein |
| **Didaktisches Ordnungsprinzip** | Starre Schablone Haupt-/Unter-/Lehrplanthema | Automatisch passend zur Bildungsstufe erkannt: bei Schule `Themenfeld → Thema → Fachbegriff`, bei Berufsbildung **`Handlungsfeld → Thema → Fachbegriff`** |

---

## 4. Gesamtbewertung

1. **Drastisch geringere Tokenkosten (~60–68 % Ersparnis pro Baum) aus zwei Gründen:**
   - **Kein unsichtbarer Reasoning-Overhead (`−65 % bis −70 % Output-Tokens/Knoten`):** Der alte v1-Endpunkt übergibt kein `reasoning_effort: "none"`. Dadurch verbraucht `gpt-6-luna` bei jedem der 21–25 Einzelaufrufe rund 300 unsichtbare Reasoning-Tokens je Knoten, die voll als teure Output-Tokens abgerechnet werden (`434–519` statt `154–160` Output-Tokens/Knoten bei gleich langen Beschreibungstexten).
   - **Hohe Prompt-Cache-Quote (`50–72 %` statt `0 %`):** In v1 liegt der kurze Systemprompt unterhalb der 1.024-Token-Schwelle des Provider-Caches (`0 %` Cache-Treffer). In v2 teilen sich alle parallelen 10er-Beschreibungs-Batches denselben statischen Systemprompt (`system.md`), den Anfragekontext und das vollständige Titel-Grundgerüst im Präfix.
2. **Rund 38–48 % kürzere Antwortzeiten & 62–76 % weniger API-Calls:**
   - Statt einer 3-stufigen Kaskade aus 21–25 Einzelaufrufen benötigt v2 nur 1 Skeleton-Call + 4–8 parallele 10er-Batches. Das schont Rate-Limits hinter der b-api massiv und senkt das Risiko partieller Timeouts.
3. **Höhere redaktionelle Qualität bei voller Transparenz:**
   - v2 liefert prägnantere Knotentitel, erkennt für die berufliche Bildung selbstständig *berufliche Handlungsfelder* statt schulischer Lehrplanthemen, hält kanonische Zusatzthemen exakt ein und garantiert deterministisch Duplikatfreiheit sowie explizite `warnings` statt stiller Leer-Listen bei Teilfehlern.
