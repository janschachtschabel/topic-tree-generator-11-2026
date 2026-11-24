# Steckbrief topic-tree (Vorlage nach Leitfaden, Kap. 6)

Status je Zeile: ✅ belegt · ⏳ zu messen/klären · ➖ entfällt

| Zeile | Inhalt | Status |
|---|---|---|
| Dienst-ID | `topic-tree` (b-api-Proxy-Eintrag, Logs, Metriken, Chart) | ✅ |
| Kurzbeschreibung | Erzeugt Themenbäume aus Thema, Strukturdokument, Ordnern oder Inhalten und entwickelt sie mit Rückmeldungen weiter; ordnet Inhalte zu. | ✅ |
| Funktionen | `POST /v2/topic-tree`; alt: `/generate-topic-tree`, `/generate-collection-description` | ✅ |
| Laufzeit je Funktion (P50/P90) | mit `scripts/loadtest.py` messen, je Use Case | ⏳ |
| Kosten je Aufruf | b-api-Nutzungsdaten nach Testlauf; Aufrufzahl: topic 8×5×3 = 9 Aufrufe | ⏳ |
| b-api | Proxy-Eintrag `topic-tree`, `forwardDelegation: true`, Scopes `llm`; Route `topic-tree-generator`; `responseTimeout` ≥ 310 000 ms | ⏳ mit b-api-Admin |
| Ruft selbst die b-api? | ja, nur `/api/v1/llm/router/chat/completions`; keine verifizierte Person nötig | ✅ |
| Abhängigkeiten | LLM-Route; keine Datenbank, kein Repository-Zugriff | ✅ |
| Clusterfähigkeit | zustandslos, beliebig viele Pods; gunicorn-Worker je Pod (`WEB_CONCURRENCY`) | ✅ |
| Updates und CronJobs | keine; Vokabular-Snapshot mit Release aktualisieren (`scripts/build_vocab_snapshot.py`) | ✅ |
| Ressourcen | messen: Leerlauf, warm, Spitze (siehe unten) | ⏳ |
| Image-Größe | nach CI-Build eintragen; keine Modelle oder Daten im Image | ⏳ |
| Ansprechperson | Jan Schachtschabel, Vertretung: … | ⏳ |

## Abweichungen vom Leitfaden (mit Begründung)

- **Synchron über 30 s**: Ein Baum braucht 10–120 s. Das Delegations-Token endet mit dem Aufruf, Hintergrundjobs
  im Dienst könnten die b-api nicht mehr rufen. Frist `REQUEST_TIMEOUT_SECONDS=280`; Proxy-Timeout mindestens 310 s.
- **OpenTelemetry-Export**: B3 und `x-client-trace-id` werden gelesen und weitergegeben, Spans aber nicht exportiert.

## Messanleitung

1. LLM-Route proben: `B_API_KEY=… uv run python -m scripts.probe_llm --base-url <router> --model topic-tree-generator`.
   Lehnt die Route `json_schema` oder `prompt_cache_key` ab: `LLM_OUTPUT_MODE=json_object` bzw. `LLM_SEND_PROMPT_CACHE_KEY=false`.
2. Container starten (`docker compose up`), Leerlauf-RAM mit `docker stats` notieren.
3. Last: `uv run python -m scripts.loadtest --url … --payload docs/examples/topic_full.json -n 20 -c 5`, dabei RAM/CPU
   beobachten (Spitze). Für jeden Use Case wiederholen.
4. Kosten aus den b-api-Nutzungsdaten des Testschlüssels ablesen; `metadata.generation.usage` zeigt Tokens und Cache-Anteil.
5. Limit ≈ gemessene Spitze + 20–30 %, Worker × RAM je Worker + Grundbedarf ≤ Limit.
