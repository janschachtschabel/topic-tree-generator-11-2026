# Abschlussaudit: Themenbaum-Dienst (`main` nach PR #21 und #22, Stand `c1d0949`)

Datum: 26.11.2026 · Vorgänger: `2026-11-24-audit.md`, `2026-11-25-audit.md`, `2026-11-26-audit.md`,
`2026-11-26-live-test.md`, `2026-11-26-gesamtaudit.md` (deren Befunde sind behoben und wurden nicht erneut gezählt).
Ergebnis: Release `2.2.0` vorbereitet, Doku vollständig auf Deutsch und Englisch.

## Vorgehen

- Vier Prüfbereiche parallel und unabhängig: (1) Pipeline, Domain, Schemas mit Schwerpunkt auf `assign_only`,
  `nodeId` und `describe` (PR #21), (2) API, Sicherheit, LLM-Client, v1, Verweise, Swagger-Beispiele (PR #22),
  (3) Test-UI mit Playwright gegen den OpenAI-Stub (alle 28 Beispiele: laden, senden, als Basis übernehmen, erneut
  senden), (4) Deploy, CI, Release, Doku, Steckbrief und Abgleich mit dem Diensteleitfaden.
- Vorher: `uv run pytest -q` 675 grün, 5 übersprungen (Helm ohne `helm`); 35 Node-Tests der UI; ruff sauber.
- Jeder Befund wurde mit einer Probe bestätigt; jeder Fix hat einen Regressionstest, der vorher fehlschlug. Wo sich
  DOM-Verhalten nicht als Unit-Test prüfen ließ, belegt ein Playwright-Lauf den Fix (im Commit vermerkt).
- Nachher: 712 grün, 6 übersprungen (Helm-Tests laufen in der CI); 44 Node-Tests; 8 `promtool`-Tests der Alarme
  (laufen in der CI, lokal war `promtool` nicht ausführbar); ruff sauber.
- Nicht als Befund gewertet (Vorgabe Jan): Binärdateien in `fulltext.ref`; die Umwandlung passiert vorher.

## Gesamturteil

Token-Weitergabe, Fehlerformat, Host-Allowlist, Fristen und die deterministischen Teile halten. Die neuen Funktionen
aus PR #21 waren im Kern richtig; die Befunde lagen an ihren Rändern (Zusammenspiel von `describe` mit `edit` und
Umbenennen, ein geänderter `frame` bei `assign_only`). Für den Betrieb fehlten Labels für den Prometheus Operator,
ein PodDisruptionBudget, Alarme für Ausfall und Serverfehler sowie ein Runbook; für die Übergabe fehlten ein
Betriebshandbuch und die englische Fassung der Doku.

## Behobene Befunde

| # | Schwere | Bereich | Befund | Fix |
|---|---|---|---|---|
| 1 | Mittel | assign_only | Ein geänderter `frame` wurde still ignoriert; `vocab_labels` und Zielgruppe zeigten den neuen, `generation.frame` den alten Rahmen. | `INPUT_IGNORED`; Labels und Zielgruppe aus dem Rahmen des Baums. |
| 2 | Mittel | refine | Umbenannte oder zusammengeführte Knoten, deren Beschreibung das LLM nicht neu schrieb, behielten still die alte. | `DESCRIBE_FAILED` für jeden aufzufrischenden Knoten. |
| 3 | Mittel | refine | Eine mit `edit` gesetzte Beschreibung (oder Schlagworte) wurde von `describe` oder vom Auffrischen nach `rename` still überschrieben. | `edit` gewinnt; `describe` desselben Knotens wird mit `CHANGE_REJECTED` abgelehnt. |
| 4 | Niedrig | refine | Zwei `describe` auf denselben Knoten: der erste Hinweis ging verloren. | Beide Hinweise gehen in den Prompt. |
| 5 | Niedrig | refine | Ein fehlgeschlagener Beschreibungs-Batch ergab zwei `DESCRIBE_FAILED`, eine ohne `step`. | Eine Warnung mit `step`. |
| 6 | Niedrig | Prompts | Abschnittsauszüge eines Dokuments (`describe_nodes`) und Knotenbeschreibungen (`infer_metadata`) konnten Zeilen im Prompt vortäuschen. | Auf eine Zeile gebracht (wie schon die Titel). |
| 7 | Niedrig | Tracing | Alle LLM-Aufrufe einer Anfrage hatten dieselbe `X-B3-SpanId`. | Trace-Header je Aufruf; jeder Aufruf ist ein eigener Span. |
| 8 | Niedrig | Verweise | Die Host-Allowlist ignorierte den Port (`https://erlaubt:8443/` wurde geladen). | Nur Port 443. |
| 9 | Niedrig | Swagger | Das Beispiel `describe` (ein Knoten) meldete immer `SHAPE_WIDTH`. | Refine ohne Strukturänderung und ohne gesendetes `shape` prüft die Form nicht erneut. |
| 10 | Niedrig | Intern | Port 9000 beantwortete andere Methoden mit einer HTML-Fehlerseite (501). | JSON-405 mit `Allow: GET`, Fehlerseiten als JSON. |
| 11 | Mittel | Release | `latest` und `main` enthielten #21/#22, meldeten sich aber als `2.1.0`. | Version `2.2.0` vorbereitet (Entscheidung Jan); Tag nach dem Merge. |
| 12 | Mittel | Helm | `ServiceMonitor`/`PrometheusRule` ohne frei wählbare Labels: der Prometheus Operator (z. B. kube-prometheus-stack) hätte sie nicht gefunden. | `serviceMonitor.labels`, `prometheusRule.labels`. |
| 13 | Mittel | Helm | Kein PodDisruptionBudget: ein Drain konnte beide Pods mitten in 280-s-Anfragen beenden. | PDB, Standard an, `maxUnavailable: 1`. |
| 14 | Niedrig | Alarme | Kein Alarm für Ausfall oder 5xx; der LLM-Alarm zählte 401/403 der Aufrufer und schlug schon bei einem einzelnen Fehler an; keine Beschreibung, kein Runbook. | `TopicTreeDown`, `TopicTreeServerErrors`, Mindestmenge, 401/403 ausgenommen, `description` und `runbook_url`; `promtool test rules` in der CI (offenes Soll der Vorgänger). |
| 15 | Niedrig | Helm | Service-Account-Token im Pod eingehängt; Proben ohne `timeoutSeconds`. | `automountServiceAccountToken: false`, `timeoutSeconds: 3`. |
| 16 | Niedrig | Doku | Steckbrief: Testzahlen veraltet; Use Cases und Endpunkte ohne `assign_only`, `describe`, `nodeId`. README: Helm-Tests „inklusive“, obwohl sie lokal übersprungen werden. `api.md`: `500 INTERNAL` fehlte (die Prüfung erfasste es nicht). | Korrigiert; die Prüfung erfasst jetzt auch `error_response`. |
| 17 | Mittel | Doku | Kein Runbook, keine Schritte für Upgrade, Rollback, Release, Kapazität, Egress der NetworkPolicy, Prüfung nach der Installation, Logfelder. | Betriebshandbuch `docs/de/betrieb.md` / `docs/en/operations.md`; jeder Alarm hat einen Abschnitt (mit Test). |
| 18 | Mittel | Doku | Doku nur teilweise zweisprachig (README englisch, `docs/` deutsch). | `README.md`/`README.de.md`, `docs/de/`, `docs/en/`, Index `docs/README.md`; Feldreferenz in beiden Sprachen erzeugt; Tests prüfen Paare, gegenseitige Links, gleiche Abschnitte und alle relativen Links. |
| 19 | Mittel | Test-UI | Der Sprachwechsel löschte die Anzeige der Basis („Noch keine Basis“), Überschrift und Knöpfe blieben deutsch. | Basis wird aus dem Zustand neu gezeichnet. |
| 20 | Mittel | Test-UI | Ein Baum ohne Schlüssel (z. B. aus dem Repository) bot in „Baum ändern“ keine Knoten zur Auswahl, ohne Hinweis. | Hinweis, wie die Knoten Schlüssel bekommen. |
| 21 | Mittel | Test-UI | Im Änderungseditor sprang der Tastaturfokus nach jeder Änderung der Operation oder dem Entfernen einer Zeile ins Leere. | Fokus bleibt in der Zeile bzw. geht zur nächsten. |
| 22 | Niedrig | Test-UI | Ein Beispiel, das in der JSON-Ansicht öffnet, zeigte seine Basis nicht (oder die vorige). | Basis wird gesetzt. |
| 23 | Niedrig | Test-UI | Fokus ging nach „Sperren“, „Ändern …“ und nach dem Senden verloren. | Fokus auf Knopf, neue Zeile bzw. Ergebnis- oder Fehlerüberschrift. |
| 24 | Niedrig | Test-UI | Baum-Knöpfe ohne knotenbezogenen Namen; Basisbaum ohne zugänglichen Namen. | `aria-label` je Knoten, `aria-labelledby`. |
| 25 | Niedrig | Test-UI | Ansichtsschalter (Beschreibungen, Schlüssel) fehlten für eine frisch geladene Basis. | Sichtbar, sobald eine Basis da ist. |
| 26 | Niedrig | Test-UI | „Letztes Ergebnis übernehmen“ in „Inhalte einsortieren“ wechselte nach „Baum ändern“. | Bleibt im Einsortieren. |
| 27 | Niedrig | Test-UI | „Inhalte“/„Materialien“ gemischt im Einsortieren; „Kombination:“ doppelt in der Gruppe „Kombinationen“. | Einheitlich „Inhalte“; Präfix in der Gruppe entfällt. |

## Geprüft, aber nicht geändert

- **`bdt_`-Token im Modus `auto`:** Ein beliebiges `bdt_…`-Token umgeht `SERVICE_API_KEYS`, weil es als Aufruf über
  die b-api gilt; geprüft wird es erst beim ersten LLM-Aufruf. Ohne LLM laufen nur gezielte Änderungen und Verweise von
  freigegebenen Hosts (Standard: keine). Das ist die Betriebsart `auto` wie entworfen (E3); README, `api.md` und
  `.env`-Hinweise sagen jetzt: eine öffentliche Instanz, die nur Dienst-Schlüssel annehmen soll, läuft mit
  `SERVICE_MODE=standalone`. Hinter der b-api (`bapi`, Standard im Chart) betrifft es nichts.
- **v1-Endpunkte und B3-Spans:** v1 sendet weiterhin eine Span-ID je Anfrage (eingefroren, nur Trace-Detail).
- **Node-Tests in der GitLab-CI:** Das uv-Image dort hat kein `node`, die UI-Tests überspringen sich; in der
  GitHub-CI laufen sie. Gehört zur offenen Frage der Build-Quelle.
- **Actions per Commit-SHA festlegen:** Aus der Cloud-Umgebung waren die SHAs nicht abrufbar; bleibt als Soll offen
  (Dependabot pausiert, Tags der Hersteller-Actions).

## Abgleich mit dem Diensteleitfaden (Änderungen seit 26.11. vormittags)

| Kap. | Punkt | vorher | jetzt |
|---|---|---|---|
| 3 | Alarmregeln mit `promtool test rules` | 🟡 | ✅ `tests/alerts/topic-tree.test.yml` in der CI |
| 3 | Alarme mit Beschreibung und Runbook | 🟡 | ✅ `docs/de/betrieb.md#runbook` |
| 4 | Produktion nur mit `vX.Y.Z` | 🟡 (kein Tag) | ✅ `v2.1.0` veröffentlicht, `v2.2.0` vorbereitet |
| 4 | Jede Version nur einmal veröffentlichen | ❌ | ✅ (seit 2.1.0) |
| 4 | Abhängigkeiten auf Lücken prüfen | ❌ | ✅ `pip-audit` (meldet) |
| 4 | Typprüfung | ❌ | ❌ offen |
| 6 | Steckbrief vollständig | 🟡 | 🟡 offen: Kosten je Funktion aus b-api-Buchungen, Vertretung |

## Offen

- Soll: Typprüfung in der CI; Actions per SHA.
- Organisatorisch, unverändert: Build-Quelle für T6 (GitLab oder GitHub), Vertretung, b-api-Proxy-Eintrag und Route,
  Namespaces für die NetworkPolicy, Kosten je Use Case aus der b-api-Buchung (siehe Übergabe-Checkliste in
  `docs/de/betrieb.md`).
- Release: Tag `v2.2.0` nach dem Merge (setzt Jan).
