# Messbericht: Laufzeit, Tokens, Cache & Ressourcen (`gpt-6-luna`, OpenAI nativ)

Stand: 24.11.2026 · Branch: `feature/topic-tree-v2` (Basis-Commit `ae6eb62`) · Zweck: Datengrundlage für Kostenbewertungen, Tarifvergleiche (OpenAI, Azure EU, GWDG/b-api) und Kapazitätsplanung.

## 1. Messaufbau

| Parameter | Wert |
|---|---|
| Betriebsmodus | `SERVICE_MODE=standalone` (natives OpenAI-Backend, `OPENAI_BASE_URL` leer) |
| Modell | `OPENAI_MODEL=gpt-6-luna` |
| Parameterfamilie / Ausgabe | `LLM_PARAM_FAMILY=common` (`max_completion_tokens` + `reasoning_effort: "none"`), `LLM_OUTPUT_MODE=json_schema` (`strict: true`) |
| Prompt-Cache-Key | `LLM_SEND_PROMPT_CACHE_KEY=auto` (aktiv bei OpenAI nativ: `topic-tree:<step>`) |
| Parallelität / Worker | `LLM_MAX_CONCURRENCY=8`, 1 Prozess (`python -m app`, uvicorn, Windows 11) |
| Eingaben | `docs/examples/*.json`; bei `document` mit `tests/fixtures/lehrplan_physik_auszug.md`; bei `contents` mit 11 Optik-Materialien + 1 fachfremdem Item (`c12`, „Rezept für Apfelkuchen“) |

Alle Aufrufe liefen über echte HTTP-Verbindungen gegen den laufenden Dienst (`POST /v2/topic-tree`) inklusive JSON-Logging und Prometheus-Metriken am internen Port. Kein API-Schlüssel erschien im Log (`secret_leaked=False`).

---

## 2. Feature-Probe (`scripts/probe_llm.py --model gpt-6-luna`)

| Probe | Ergebnis | Hinweis |
|---|---|---|
| `plain` (`max_tokens`) | ❌ HTTP 400 | Erwartet für GPT-5/GPT-6-Familie (`max_completion_tokens` Pflicht) |
| `common_body` (`max_completion_tokens` + `reasoning_effort: "none"`) | ✅ OK, gültiges JSON | Standard-Parameterfamilie `common` kompatibel |
| `json_object` | ✅ OK, gültiges JSON | Fallback-Modus funktionsfähig |
| `json_schema` (`strict: true`) | ✅ OK, gültiges JSON | Alle 9 Schritt-Schemata strikt nutzbar |
| `prompt_cache_key` | ✅ OK, gültiges JSON | Wird von OpenAI nativ akzeptiert |

---

## 3. Token-Verbrauch & Laufzeit je Use Case (Einzelaufrufe)

Für die Kostenbewertung sind die Prompt-Tokens nach **ungecachtem Input** (`prompt_tokens - cached_tokens`), **gecachtem Input** (`cached_tokens`) und **Output** (`completion_tokens`) getrennt ausgewiesen.

| Szenario | Dauer | Aufrufe | Fehler | Knoten (Tiefe) | Input ungecacht | Input gecacht (Anteil) | Output-Tokens | Output / Knoten | Warnungen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `topic_minimal` (kalt) | 45,6 s | 9 | 0 | 207 (3) | 8.564 | 11.753 (57,8 %) | 27.131 | ~131 | 8× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| `topic_minimal` (warm) | 55,8 s | 9 | 0 | 199 (3) | 4.781 | 15.432 (76,3 %) | 28.424 | ~143 | 9× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| `topic_full` (Sek I, 3 Ebenen) | 42,0 s | 9 | 0 | 148 (3) | 5.359 | 15.143 (73,9 %) | 18.629 | ~126 | 7× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| `document` (Lehrplan Physik Auszug) | 7,4 s | 3 | 0 | 2 (1) | 5.923 | 0 (0,0 %) | 458 | ~229 | `SHAPE_WIDTH` (Auszug hat nur 2 TF) |
| `folders` (`options.improve=true`) | 5,6 s | 2 | 0 | 2 (1) | 2.251 | 1.630 (42,0 %) | 297 | ~149 | `SHAPE_WIDTH` (Beispiel hat 2 Ordner) |
| `contents` (12 Items, 1 off-topic) | 19,7 s | 2 | 0 | 15 (2) | 2.985 | 1.666 (35,8 %) | 2.466 | ~164 | keine (`c12` → `unassigned: off_topic`) |
| `refine` (Feedback + `locked`) | 4,2 s | 2 | 0 | 2 (1) | 2.185 | 1.630 (42,7 %) | 159 | ~80 | `SHAPE_WIDTH`, `DESCRIPTION_MISSING` |

### Bewertung der Einzelläufe

- **Prompt-Caching greift bereits beim ersten Lauf**: In `topic_minimal` (kalt) profitieren bereits die parallelen Ast-Aufrufe vom gemeinsamen Präfix (statischer Systemprompt + Anfragekontext + Skelett) → **57,8 % Cache-Treffer** im Kaltlauf, **73,9–76,3 %** im Warmlauf.
- **Kleine Use Cases sind sehr günstig und schnell**: `document`, `folders` und `refine` benötigen nur 2–3 Aufrufe, ~4–7 s Laufzeit und wenige hundert Output-Tokens.
- **Qualität der Ausgaben**:
  - `topic_full`: `Allgemeines` vorn, `Farben` aufgenommen, `Wellenoptik` ausgeschlossen, Ordnungsprinzip automatisch erkannt („Themenfeld → Thema → Fachbegriff“), keine Facetten als Knoten.
  - `folders`: „Neuer Ordner (2)“ anhand der Inhalte in „Spiegelbilder“ umbenannt (`from: "service"`).
  - `contents`: 11 Physik-Materialien sauber in 5 Themenfelder / 15 Knoten gruppiert, „Rezept für Apfelkuchen“ (`c12`) als `off_topic` aussortiert.
  - `refine`: `k-optik` (`locked`) unangetastet; bei mehrdeutigem Wunsch wurde eine Rückfrage (`questions: 1`) gestellt statt zu raten.
- **Offene Optimierungsmöglichkeit**: Bei großen 3-Ebenen-`topic`-Bäumen (150–200 Knoten) schlagen parallele Äste auf Ebene 3 vereinzelt identische Fachbegriffe vor (4–9× `DUPLICATE_TITLE`). Der Strukturprüfer meldet dies transparent.

---

## 4. Paralleler Lastlauf (`topic_full.json`, `n=6`, `c=3`)

Sechs Anfragen mit 3 gleichzeitigen Clients gegen einen einzelnen Worker (`LLM_MAX_CONCURRENCY=8`):

| Lauf | Status | Dauer | Aufrufe | Input ungecacht | Input gecacht (Anteil) | Output-Tokens | Warnungen |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 200 | 112,1 s | 10 | 6.036 | 17.203 (74,0 %) | 24.341 | `SHAPE_DEPTH`, 8× `DUPLICATE_TITLE`, `SHAPE_SINGLE_CHILD`, `DESCRIPTION_LENGTH` |
| 2 | 200 | 34,5 s | 9 | 4.770 | 15.524 (76,5 %) | 16.809 | 6× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| 3 | 200 | 61,1 s | 10 | 5.799 | 17.203 (74,8 %) | 22.261 | 8× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| 4 | 200 | 95,7 s | 10 | 5.965 | 17.203 (74,3 %) | 21.306 | 5× `DUPLICATE_TITLE`, 5× `SHAPE_SINGLE_CHILD`, `DESCRIPTION_LENGTH` |
| 5 | 200 | 88,5 s | 9 | 4.789 | 15.524 (76,4 %) | 17.912 | 4× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| 6 | 200 | 63,5 s | 9 | 5.021 | 15.524 (75,6 %) | 20.132 | 9× `DUPLICATE_TITLE`, `DESCRIPTION_LENGTH` |
| **Gesamt / Ø** | **0 Fehler** | **P50 63,5 s · P90 112,1 s** | **Ø 9,5** | **Ø 5.397** | **Ø 16.364 (75,2 %)** | **Ø 20.460** | — |

---

## 5. Ressourcenverbrauch (RAM)

| Zustand (1 Worker-Prozess) | Working Set (MiB) |
|---|---:|
| Leerlauf nach Start (`import app.main`) | 71,5 MiB |
| Warm nach Einzelaufrufen aller Use Cases | 95,0 MiB |
| Spitze unter paralleler Last (`n=6, c=3`) | 97,0 MiB |

Der Speicherbedarf ist weitgehend **elastisch flach** (keine lokalen ML-Modelle im Prozess). Hochrechnung für den Kubernetes-Pod mit `WEB_CONCURRENCY=2` und Gunicorn-Master (~40 MiB): ca. **235 MiB Spitze** → Helm-Vorgaben `requests.memory: 256Mi`, `limits.memory: 512Mi` bieten ausreichenden Puffer auch bei großen `items_ref`-Dateien.

---

## 6. Rechenmodell für spätere Kostenbewertungen

Da sich Modell- und b-api-Preise (OpenAI direkt, Azure EU +20 %, GWDG/AcademicCloud) unabhängig vom Code ändern, lassen sich die Stückkosten je Aufruf direkt aus den gemessenen Token-Buckets berechnen:

$$\text{Kosten je Aufruf} = \frac{T_{\text{in,uncached}} \cdot P_{\text{in}} + T_{\text{in,cached}} \cdot P_{\text{cached}} + T_{\text{out}} \cdot P_{\text{out}}}{1\,000\,000}$$

Dabei sind $P_{\text{in}}$, $P_{\text{cached}}$ und $P_{\text{out}}$ die aktuellen Preise pro 1 Mio. Tokens aus der b-api-Preisliste bzw. dem Anbieter-Tarif.

### Typische Token-Profile je 1.000 Aufrufe (Planungswerte aus dieser Messung)

| Profil | Aufrufe/Req | Input ungecacht / 1k Req | Input gecacht / 1k Req | Output / 1k Req | Hauptkostentreiber |
|---|---:|---:|---:|---:|---|
| Großer 3-Ebenen-Themenbaum (`topic_full`, ~150 Knoten) | ~9,5 | ~5,40 Mio. | ~16,36 Mio. | ~20,46 Mio. | **Output-Tokens** (Beschreibungen aller ~150 Knoten) |
| Mittelgroßes Clustering (`contents`, 12 Items, 2 Ebenen) | 2 | ~2,99 Mio. | ~1,67 Mio. | ~2,47 Mio. | Output + Input ausgewogen |
| Lehrplan-Mapping (`document`, kleiner Auszug) | 3 | ~5,92 Mio. | ~0 | ~0,46 Mio. | Input-Tokens (Gliederung + Auszüge) |
| Ordner-Verbesserung / Feedback (`folders` / `refine`) | 2 | ~2,22 Mio. | ~1,63 Mio. | ~0,23 Mio. | Sehr gering (~1 % eines 3-Ebenen-Baums) |

### Wichtigste Stellhebel für die Kosten

1. **Output-Tokens dominieren bei 3-Ebenen-`topic`-Bäumen**: Bei ~150 Knoten und `description_length: 60` Wörtern entfallen ~20.500 Output-Tokens (~125–140 Output-Tokens je Knoten inkl. JSON-Struktur und Schlagworte) auf einen Lauf. Reduktion auf `shape.depth: 2` oder kürzere `hints.description_length` (z. B. 40 Wörter) senkt die Stückkosten nahezu linear.
2. **Prompt-Caching spart ~75 % der Input-Tokens** bei großen Bäumen (statischer Systemprompt + geteilter Anfragekontext/Skelett). Bei Anbietern mit Cache-Write-Aufschlag (z. B. Anthropic) bzw. über GWDG ohne Provider-Cache muss mit der vollen `prompt_tokens`-Summe (Ø 21.760) gerechnet werden.
3. **Einsparung gegenüber v1**: v1 benötigte für einen 8×5×3-Baum bis zu **49 LLM-Aufrufe** (ohne Cache-Präfix), v2 erzeugt einen vergleichbaren Baum in **9–10 Aufrufen** — entscheidend insbesondere hinter dem geteilten GWDG-Kontingent (~10 Req/min).

---

## 7. Abgleich bei b-api-Übergabe

Vor Produktivbetrieb auf der b-api-Route (`topic-tree-generator`) einmalig wiederholen:

1. `B_API_KEY=… uv run python -m scripts.probe_llm --base-url <b-api-router> --model topic-tree-generator`
2. `uv run python -m scripts.loadtest --url <service>/v2/topic-tree --payload docs/examples/topic_full.json -n 10 -c 3`
3. Reale EUR-Buchung aus den b-api-Nutzungsdaten des Testschlüssels in [docs/steckbrief.md](../steckbrief.md) ergänzen.
