# Steckbrief topic-tree (Vorlage nach Leitfaden, Kap. 6)

Status je Zeile: ✅ belegt · ⏳ zu messen/klären · ➖ entfällt

| Zeile | Inhalt | Status |
|---|---|---|
| Dienst-ID | `topic-tree` (b-api-Proxy-Eintrag, Logs, Metriken, Chart) | ✅ |
| Kurzbeschreibung | Erzeugt Themenbäume aus Thema, Strukturdokument, Ordnern oder Inhalten und entwickelt sie mit Rückmeldungen weiter; ordnet Inhalte zu. | ✅ |
| Funktionen | `POST /v2/topic-tree`; alt: `/generate-topic-tree`, `/generate-collection-description` | ✅ |
| Laufzeit je Funktion (P50/P90) | Gemessen am 24.11.2026 (OpenAI nativ, `gpt-6-luna`): `topic` voll (3 Ebenen, ~150 Knoten) 42 s einzeln, bei Last (`n=6, c=3`) **P50 63,5 s / P90 112,1 s** (0 % Fehler); `document` 7,4 s; `folders` + `improve` 5,6 s; `contents` (12 Items) 19,7 s; `refine` 4,2 s (Details unten) | ✅ (OpenAI nativ; b-api-Route optional gegenzuprüfen) |
| Kosten je Aufruf | Tokens gemessen auf `gpt-6-luna` (s. Tabelle unten, 75 % Prompt-Cache-Quote bei Last); reale EUR-Buchung nach Testlauf aus den b-api-Nutzungsdaten ablesen | ⏳ b-api-Abrechnung |
| b-api | Proxy-Eintrag `topic-tree`, `forwardDelegation: true`, Scopes `llm`; Route `topic-tree-generator`; `responseTimeout` ≥ 310 000 ms | ⏳ mit b-api-Admin |
| Ruft selbst die b-api? | ja, nur `/api/v1/llm/router/chat/completions`; keine verifizierte Person nötig | ✅ |
| Abhängigkeiten | LLM-Route (oder OpenAI-kompatibel eigenständig); keine Datenbank, kein Repository-Zugriff | ✅ |
| Clusterfähigkeit | zustandslos, beliebig viele Pods; gunicorn-Worker je Pod (`WEB_CONCURRENCY`) | ✅ |
| Updates und CronJobs | keine; Vokabular-Snapshot mit Release aktualisieren (`scripts/build_vocab_snapshot.py`) | ✅ |
| Ressourcen | RAM weitgehend fest (keine lokalen Modelle): 1 Worker Leerlauf **72 MiB**, warm **95 MiB**, Spitze unter Last (`c=3`) **97 MiB**. Bei `WEB_CONCURRENCY=2` + Master ≈ 235 MiB Spitze → Empfehlung: Request `100m CPU / 256Mi RAM`, Limit `512Mi RAM` (Reserve für große `items_ref`-Payloads) | ✅ (Windows-Prozess; Container-cgroup im ersten CI-Image gegenzuprüfen) |
| Image-Größe | nach CI-Build eintragen; keine Modelle oder Daten im Image | ⏳ |
| Ansprechperson | Jan Schachtschabel, Vertretung: … | ⏳ |

## Abweichungen vom Leitfaden (mit Begründung)

- **Synchron über 30 s**: Ein 3-Ebenen-Baum braucht typisch 35–112 s (`gpt-6-luna`). Das Delegations-Token endet mit dem Aufruf, Hintergrundjobs
  im Dienst könnten die b-api nicht mehr rufen. Frist `REQUEST_TIMEOUT_SECONDS=280`; Proxy-Timeout mindestens 310 s.
- **OpenTelemetry-Export**: B3 und `x-client-trace-id` werden gelesen und weitergegeben, Spans aber nicht exportiert.

## Messergebnisse (24.11.2026, OpenAI nativ, `gpt-6-luna`)

Vollständiger Messbericht inkl. Token-Aufschlüsselung (ungecacht/gecacht/Output) und Rechenmodell für Tarif- und Kostenbewertungen: [`docs/measurements/2026-11-24-openai-gpt-6-luna.md`](measurements/2026-11-24-openai-gpt-6-luna.md).

### Feature-Probe (`scripts/probe_llm.py --model gpt-6-luna`)

- `common_body` (`max_completion_tokens` + `reasoning_effort: "none"`): ✅ OK, gültiges JSON
- `json_object`, `json_schema` (`strict: true`), `prompt_cache_key`: ✅ alle OK, gültiges JSON
- `plain` (`max_tokens`): HTTP 400 (erwartet für GPT-5/GPT-6-Familie; daher Standard `LLM_PARAM_FAMILY=common`)

### Einzelaufrufe je Use Case (`SERVICE_MODE=standalone`, `LLM_OUTPUT_MODE=json_schema`)

| Szenario | Dauer | LLM-Aufrufe | Knoten (Tiefe) | Prompt-Tokens (davon Cache) | Completion-Tokens | Fehler |
|---|---:|---:|---:|---:|---:|---:|
| `topic_minimal` (kalt) | 45,6 s | 9 | 207 (3) | 20.317 (11.753 / 58 %) | 27.131 | 0 |
| `topic_minimal` (warm) | 55,8 s | 9 | 199 (3) | 20.213 (15.432 / 76 %) | 28.424 | 0 |
| `topic_full` (Sek I, 3 Ebenen) | 42,0 s | 9 | 148 (3) | 20.502 (15.143 / 74 %) | 18.629 | 0 |
| `document` (Lehrplan Physik Auszug) | 7,4 s | 3 | 2 (1) | 5.923 (0 / 0 %) | 458 | 0 |
| `folders` (`options.improve=true`) | 5,6 s | 2 | 2 (1) | 3.881 (1.630 / 42 %) | 297 | 0 |
| `contents` (12 Items, 1 off-topic) | 19,7 s | 2 | 15 (2) | 4.651 (1.666 / 36 %) | 2.466 | 0 |
| `refine` (Text-Feedback + `locked`) | 4,2 s | 2 | 2 (1) | 3.815 (1.630 / 43 %) | 159 | 0 |

### Paralleler Lastlauf (`topic_full.json`, `n=6`, `c=3`, 1 Worker, `LLM_MAX_CONCURRENCY=8`)

- **Fehlerquote**: `0 / 6` (0,0 %)
- **Antwortzeiten**: min 34,5 s · **P50 63,5 s** · **P90 112,1 s** · max 112,1 s
- **Durchschnittliche Tokens je Baum**: 21.760 Prompt-Tokens (davon **16.364 aus dem Prompt-Cache = 75,2 %**), 20.460 Completion-Tokens, 9–10 LLM-Aufrufe
- **Speicher**: Leerlauf 71,5 MiB → warm 95,0 MiB → Spitze 97,0 MiB; keine Schlüssel/Tokens im JSON-Log

## Messanleitung (Wiederholung gegen b-api-Staging)

1. LLM-Route proben: `B_API_KEY=… uv run python -m scripts.probe_llm --base-url <router> --model topic-tree-generator`.
   Lehnt die Route `json_schema` oder `prompt_cache_key` ab: `LLM_OUTPUT_MODE=json_object` bzw. `LLM_SEND_PROMPT_CACHE_KEY=false`.
2. Container starten (`docker compose up`), Leerlauf-RAM mit `docker stats` notieren.
3. Last: `uv run python -m scripts.loadtest --url … --payload docs/examples/topic_full.json -n 20 -c 5`, dabei RAM/CPU
   beobachten (Spitze). Für jeden Use Case wiederholen.
4. Kosten aus den b-api-Nutzungsdaten des Testschlüssels ablesen; `metadata.generation.usage` zeigt Tokens und Cache-Anteil.
5. Limit ≈ gemessene Spitze + 20–30 %, Worker × RAM je Worker + Grundbedarf ≤ Limit.
