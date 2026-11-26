# Betrieb und Übergabe: `topic-tree` (Themenbaum-Dienst)

> 🇬🇧 English version: [`../en/operations.md`](../en/operations.md) · Übersicht aller Dokumente: [`../README.md`](../README.md)

Dieses Handbuch richtet sich an den Betrieb (Team 6) und den b-api-Admin. Es beschreibt, was zum Installieren,
Einrichten, Überwachen, Aktualisieren und Zurückrollen des Dienstes nötig ist, und enthält das Runbook zu jedem Alarm.
Die Leitfaden-Angaben (Stammdaten, Abweichungen, Messwerte) stehen im [Steckbrief](steckbrief.md), die Aufrufe der
API in [`api.md`](api.md), alle Umgebungsvariablen in der [README](../../README.de.md#konfiguration-umgebungsvariablen).

## Überblick und Zuständigkeiten

- **Was der Dienst tut:** Er nimmt eine JSON-Anfrage an `POST /v2/topic-tree` an, ruft dafür ein Sprachmodell über die
  b-api auf und gibt einen Themenbaum als JSON zurück. Er speichert nichts, hat keine Datenbank, kein Volume und keine
  CronJobs und ruft das edu-sharing-Repository nie auf.
- **Ports:** `8000` öffentlich (API, `/docs`, optional `/ui/`), `9000` intern (`/health`, `/ready`, `/metrics`).
  Port `9000` darf nur im Cluster erreichbar sein.
- **Abhängigkeit zur Laufzeit:** nur die b-api (LLM-Router). Optional HTTPS-Downloads von Hosts in
  `REF_ALLOWED_HOSTS` (Standard leer, also keine).
- **Anmeldung:** Hinter der b-api reicht der Proxy ein Delegations-Token (`Authorization: Bearer bdt_…`) durch; der
  Dienst gibt es unverändert an die b-api weiter und speichert oder protokolliert es nie. Im Chart ist dafür kein
  Secret nötig.

| Aufgabe | Zuständig |
|---|---|
| Image und Chart bauen und veröffentlichen | CI des Repositorys (GitHub Actions; ob T6 aus GitLab baut, ist offen, siehe Steckbrief) |
| Installation, Werte, NetworkPolicy, Monitoring | Team 6 |
| Proxy-Eintrag `topic-tree` und LLM-Route `topic-tree-generator` | b-api-Admin |
| Fachliche Fragen, Prompts, Releases | Technischer Owner (Steckbrief, Abschnitt 1) |

## Voraussetzungen

- Kubernetes ab 1.25 (`policy/v1` PodDisruptionBudget, `autoscaling/v2`), Helm 3.
- Optional Prometheus Operator (für `ServiceMonitor` und `PrometheusRule`).
- Zugriff auf das Image `ghcr.io/janschachtschabel/topic-tree-generator-11-2026:<version>` (öffentlich, ohne Login)
  oder ein Spiegel in der Plattform-Registry.
- Eine b-api mit dem Proxy-Eintrag und der LLM-Route aus [Einrichtung in der b-api](#einrichtung-in-der-b-api).

## Installation

Produktion und Staging laufen mit einer festen Version, nie mit `latest`:

```shell
helm upgrade --install topic-tree \
  oci://ghcr.io/janschachtschabel/topic-tree-generator-11-2026/charts/topic-tree \
  --version 2.2.0 \
  --namespace topic-tree --create-namespace \
  -f values-staging.yaml
```

Ein Beispiel für `values-staging.yaml`:

```yaml
image:
  repository: registry.example.org/projects/wlo/topic-tree   # Spiegel der Plattform oder das GHCR-Image
  tag: "2.2.0"
config:
  serviceMode: bapi
  bApiBaseUrl: https://b-api.staging.openeduhub.net
  bApiRoute: topic-tree-generator
  uiEnabled: false
networkPolicy:
  enabled: true
  publicFrom:
    - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: b-api } }
  internalFrom:
    - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: monitoring } }
  egress:
    - ports: [{ port: 443, protocol: TCP }]   # b-api (und Hosts aus refAllowedHosts); möglichst mit ipBlock/namespaceSelector eingrenzen
serviceMonitor:
  enabled: true
  labels: { release: kube-prometheus-stack }   # Label, nach dem der Prometheus Operator auswählt
prometheusRule:
  enabled: true
  labels: { release: kube-prometheus-stack }
```

Die Namespaces und Labels oben sind Platzhalter, bis T6 sie benennt. Jeder Wert ist in
[`values.yaml`](../../deploy/helm/topic-tree/values.yaml) mit `## @param` erklärt. Für Tests ohne Cluster gibt es
zwei Compose-Dateien (README, Abschnitt *Installation & Docker-Setup*).

## Konfiguration für die Produktion

- **Betriebsart:** `config.serviceMode: bapi` (Standard im Chart). Dann nimmt der Dienst nur Aufrufe mit
  Delegations-Token an und antwortet sonst `401`.
- **LLM-Ziel:** `config.bApiRoute: topic-tree-generator` (Route am b-api-Router). Ohne Route und ohne `bApiModel`
  antwortet jeder Aufruf `503 LLM_NOT_CONFIGURED`, und `:9000/ready` meldet `not_ready`.
- **Test-Oberfläche:** `config.uiEnabled: false` (Standard im Chart); `/ui/*` antwortet dann `404`.
- **Secrets:** hinter der b-api keine. Nur im Betrieb ohne b-api (`standalone`) gehören `OPENAI_API_KEY` und
  `SERVICE_API_KEYS` in ein Secret, das `secrets.existingSecret` nennt.
- **Verweise (`items_ref`, `fulltext.ref`):** aus, solange `config.refAllowedHosts` leer ist. Erlaubte Hosts werden
  nur über HTTPS auf Port 443 geladen, mit `refMaxBytes` (10 MiB) und `refTimeoutSeconds` (20 s) je Verweis.
- **Kostengrenzen:** `maxTreeDepth` (3) und `maxNodesPerLevel` (20) können Aufrufer nicht überschreiten.
- **Fristen:** `requestTimeoutSeconds: 280`; Gunicorn beendet einen Worker nach 310 s, `terminationGracePeriodSeconds`
  ist 300. Der Proxy davor braucht ein Timeout von mindestens 310 s.
- **Sicherheit des Pods:** Pod Security `restricted`, kein Root, nur `/tmp` beschreibbar, kein Service-Account-Token.
- **Verfügbarkeit:** zwei Pods (`replicaCount: 2`) und ein PodDisruptionBudget mit `maxUnavailable: 1`, damit ein
  Drain nicht beide Pods mitten in einer Anfrage beendet.

## Einrichtung in der b-api

Durch den b-api-Admin (Werte aus dem Steckbrief, Abschnitt 2):

1. **Proxy-Eintrag `topic-tree`** auf den Service `:8000`: `forwardDelegation: true`, `delegationScopes: ["llm"]`,
   kein `forwardApiKey`, `responseTimeout` ≥ `310000` ms, `delegationLifetimeSeconds` ≥ 310,
   `openApiPath: /openapi.json`, `pathToIgnore`: `/`, `/_ping`, `/health`, `/ui/**`, `/docs`, `/redoc`.
   Header-Freigaben: Antwort `Retry-After`, `WWW-Authenticate`; Anfrage `b3`, `X-B3-*`, `x-client-trace-id`.
2. **LLM-Route `topic-tree-generator`** nach [`route-topic-tree-generator.json`](../../deploy/b-api/route-topic-tree-generator.json):
   `gpt-6-luna` (Stufe 0), `gpt-5.6-luna` (Stufe 1), `maxAttempts: 3`, `clearCache: true`. Keine GWDG-Reserve
   (zu niedriges Kontingent für 8 bis 14 parallele Aufrufe je Baum).
3. **Rechte der Aufrufer:** Dienst-Recht `topic-tree` und LLM-Recht am Schlüssel. Fehlt das LLM-Recht, antwortet der
   Dienst `403 FORBIDDEN`.

## Prüfung nach der Installation

```shell
kubectl -n topic-tree rollout status deploy/topic-tree
kubectl -n topic-tree port-forward deploy/topic-tree 9000:9000 8000:8000
curl -s localhost:9000/health    # {"status":"ok","service":"topic-tree","version":"2.2.0","vocab_snapshot":"…"}
curl -s localhost:9000/ready     # {"status":"ready","reason":null}; sonst reason LLM_NOT_CONFIGURED
curl -s localhost:9000/metrics | grep topic_tree_
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/v2/topic-tree \
  -H 'Content-Type: application/json' -d @docs/examples/topic_minimal.json   # 401: ohne Token abgewiesen
```

Danach ein echter Aufruf über die b-api (`/api/v1/proxy/topic-tree/v2/topic-tree`) mit einem Schlüssel, der beide
Rechte hat, zum Beispiel mit [`docs/examples/topic_minimal.json`](../examples/topic_minimal.json). Erwartet: `200`,
ein Baum in `collection`, `warnings` leer oder nur mit Hinweisen, `metadata.generation.usage.llm_calls` > 0. Ein
Aufruf mit [`refine_changes.json`](../examples/refine_changes.json) braucht kein LLM und antwortet in unter einer
Sekunde. Für Last- und Kostenmessungen über Staging: `scripts/loadtest.py` und `scripts/probe_llm.py`.

## Kapazität und Skalierung

- Der Dienst wartet fast nur auf das LLM; CPU und Speicher bleiben niedrig (gemessen ~235 MiB Spitze je Pod mit zwei
  Workern, Limit 512 Mi).
- Parallele LLM-Aufrufe = Pods × `webConcurrency` × `llmMaxConcurrency`, im Standard 2 × 2 × 20 = 80. Diese Zahl muss
  zum Kontingent der Route passen; bei 429-Antworten der b-api zuerst `llmMaxConcurrency` senken.
- Ein 3-Ebenen-Baum braucht 8 bis 14 LLM-Aufrufe und 20 bis 45 s, unter Last bis ~110 s (P90). Gezielte Änderungen
  ohne Text kommen ohne LLM aus.
- Der HPA (`autoscaling.enabled`) skaliert nach CPU und greift deshalb spät. Für planbare Last besser feste
  `replicaCount` setzen; mehr Pods helfen nur, solange die Route nicht drosselt.

## Logs, Metriken und Tracing

- **Logs:** JSON je Zeile nach stdout mit `timestamp`, `level`, `service`, `trace_id`, `span_id`, `message`, dazu
  `client_trace_id`, wenn der Aufrufer `x-client-trace-id` sendet. Je Anfrage eine Zeile mit `event=request`,
  `route` (Routenklasse), `status`, `duration_ms`. Einzelne LLM-Aufrufe (`event=llm_call`, `step`, `outcome`) stehen
  nur bei `LOG_LEVEL=DEBUG`. Tokens, Header, Pfade und Eingabetexte stehen nie im Log.
- **Fehler finden:** Jede Fehlerantwort enthält `error.trace_id`; dieselbe `trace_id` steht in allen Logzeilen der
  Anfrage. Ein `500 INTERNAL` hat dort den Stacktrace.
- **Metriken** an `:9000/metrics` (Multiprozess, ein Endpunkt je Pod):
  `topic_tree_requests_total{route,status}`, `topic_tree_request_seconds{route}`,
  `topic_tree_llm_calls_total{step,outcome}`, `topic_tree_llm_seconds{step}`,
  `topic_tree_llm_tokens_total{kind}` (`prompt`, `cached`, `completion`), `topic_tree_warnings_total{code}`.
  `outcome` ist `ok`, `timeout`, `connection`, `deadline` oder `http_<Status>`.
- **Tracing:** eingehende B3-Header (`b3`, `X-B3-*`) werden geprüft und an die b-api weitergegeben; jeder LLM-Aufruf
  ist ein eigener Span. Ohne B3 legt der Dienst eine neue Trace-ID an.

## Runbook

Jeder Alarm verlinkt hierher (`runbook_url`, Basis per `prometheusRule.runbookUrl`).

### `TopicTreeDown`

Prometheus erreicht seit 5 Minuten keinen Pod (`up == 0` oder kein Ziel). Prüfen: `kubectl get pods`, Events und
`kubectl logs --previous` (Absturz beim Start, z. B. ungültige Umgebungsvariable), ob der `ServiceMonitor` die
Labels hat, nach denen Prometheus auswählt (`serviceMonitor.labels`), und ob die NetworkPolicy das Monitoring auf
Port `internal` zulässt (`networkPolicy.internalFrom`).

### `TopicTreeServerErrors`

Mehr als 5 % der Anfragen enden mit 5xx. Nach `status` aufschlüsseln: `503` mit `LLM_UNAVAILABLE` heißt, die b-api oder
das Modell antwortet nicht (siehe `TopicTreeLLMErrors`); `503 LLM_NOT_CONFIGURED` heißt, Route oder Modell fehlen in
den Werten; `502 LLM_UNAVAILABLE` heißt, die b-api meldete einen dauerhaften Fehler oder das Modell lieferte keine verwertbare Antwort; `500 INTERNAL` ist ein Fehler im
Dienst: `trace_id` aus der Antwort im Log suchen und mit Stacktrace an den Owner melden.

### `TopicTreeLLMErrors`

Mehr als 20 % der LLM-Aufrufe schlagen fehl (ohne 401/403 einzelner Aufrufer). `topic_tree_llm_calls_total` nach
`outcome` aufschlüsseln: `http_429` = Kontingent der Route erschöpft (`llmMaxConcurrency` senken, Kontingent erhöhen),
`http_5xx` oder `connection` = Störung der b-api oder des Anbieters (Status der b-api prüfen, Reserve-Stufe der Route),
`timeout` = Modell zu langsam (`llmTimeoutSeconds`, Modellwahl), `http_402` = Kostenlimit. Der Dienst liefert in
dieser Zeit Bäume mit Warnungen (`LLM_DEGRADED`, `DESCRIBE_FAILED`) oder `503`.

### `TopicTreeSlowRequests`

Das 90. Perzentil von `/v2/topic-tree` liegt über 240 s und damit nahe der Frist von 280 s. Folge: Antworten mit
`DEADLINE_EXCEEDED` oder Abbrüche am Proxy. Prüfen: `topic_tree_llm_seconds` je `step` (langsames Modell?),
Drosselung der Route, Anzahl paralleler Anfragen. Abhilfe: mehr Pods nur bei freiem Kontingent, sonst schnelleres
Modell in der Route oder kleinere Bäume bei den Aufrufern.

### `TopicTreeDescribeFailures`

Mehr als 20 Beschreibungs-Batches je Stunde sind fehlgeschlagen; die Bäume kamen mit `DESCRIBE_FAILED` und teils ohne
Beschreibungen zurück. Meist dieselbe Ursache wie `TopicTreeLLMErrors` in kleinerem Umfang, sonst ungültige Antworten
des Modells (`outcome=ok`, aber Warnungen): Modell der Route prüfen. Schwere `info`, kein Bereitschaftsfall.

### Häufige Fehlerbilder ohne Alarm

| Bild | Ursache und Abhilfe |
|---|---|
| `401 UNAUTHORIZED` für alle Aufrufe | Aufruf ohne Delegations-Token, also nicht über die b-api, oder `forwardDelegation` fehlt im Proxy-Eintrag |
| `403 FORBIDDEN` | Der Schlüssel des Aufrufers hat kein LLM-Recht an der b-api |
| `413 REQUEST_TOO_LARGE` | Anfrage größer als `maxRequestBytes` (32 MiB); große Mengen über `items_ref` |
| `422 REF_NOT_ALLOWED` | Host fehlt in `refAllowedHosts` oder Verweis nicht `https://` auf Port 443 |
| `504` am Proxy nach 60 s oder 120 s | `responseTimeout` des Proxy-Eintrags oder Ingress-Timeout unter 310 s |
| Warnung `DEADLINE_EXCEEDED` | Frist von 280 s erreicht; der Baum ist unvollständig (siehe `TopicTreeSlowRequests`) |
| Gleicher Baum bei wortgleicher Anfrage | Cache der b-api (der Dienst sendet kein `temperature`); gewollt, keine Kosten |

## Updates, Rollback und Releases

- **Update:** `helm upgrade` mit neuer `--version` und `image.tag`. Der Dienst ist zustandslos; ein Rolling Update
  braucht keine Migration. Laufende Anfragen dürfen bis zu 290 s fertig laufen.
- **Rollback:** `helm rollback topic-tree <Revision>` (Revisionen: `helm history topic-tree`). Es gibt keine Daten,
  die zurückgerollt werden müssten.
- **Kompatibilität:** `/generate-topic-tree` und `/generate-collection-description` (v1) bleiben formatgleich;
  Änderungen an `/v2/topic-tree` stehen im [CHANGELOG](../../CHANGELOG.md). Vom Altstand `0.4.0` auf 2.x ändern sich
  Proxy-Eintrag und Route (siehe [Änderungsüberblick](aenderungen-v0.4-zu-v2.0.md)).
- **Release erstellen** (Owner):
  1. Version in `pyproject.toml` und `deploy/helm/topic-tree/Chart.yaml` (`version` und `appVersion`) erhöhen,
     `uv lock` ausführen, CHANGELOG-Abschnitt `## X.Y.Z (Datum)` schreiben, Versionen in README und Doku anpassen.
  2. Pull Request mit grüner CI nach `main` mergen.
  3. Tag `vX.Y.Z` auf den Merge-Commit in `main` setzen und pushen. Die CI prüft Tag = Version und dass der Tag auf
     `main` liegt, und veröffentlicht Image `X.Y.Z`/`X.Y` und Chart `X.Y.Z`. Eine Version wird nie zweimal
     veröffentlicht; `latest` kommt nur von `main`.
  4. Löst der Tag keinen Lauf aus, den Workflow `ci` per *Run workflow* auf dem Tag starten (veröffentlicht nur, was
     fehlt).
- **Abhängigkeiten:** Der CI-Job `audit` meldet bekannte Lücken (`pip-audit`); Dependabot-PRs sind pausiert, die
  Basis-Images im `Dockerfile` sind per Digest festgelegt und werden von Hand aktualisiert.

## Übergabe-Checkliste an T6

- [ ] Build-Quelle festgelegt (GitLab `scm.edu-sharing.com` oder GitHub) und Stand mit `main` abgeglichen
- [ ] Image in die Plattform-Registry gespiegelt oder GHCR freigegeben; `image.repository` gesetzt
- [ ] Release-Tag der zu installierenden Version vorhanden (Image und Chart auf der Registry)
- [ ] Proxy-Eintrag `topic-tree` und Route `topic-tree-generator` in der b-api (Staging, dann Produktion)
- [ ] Namespaces für `networkPolicy.publicFrom`/`internalFrom` und Egress-Ziele benannt, `networkPolicy.enabled: true`
- [ ] `serviceMonitor` und `prometheusRule` mit den passenden Labels an; Alarme landen im richtigen Kanal
- [ ] Prüfung nach der Installation bestanden (Abschnitt oben), ein echter Aufruf über die b-api erfolgreich
- [ ] Kosten je Use Case aus den b-api-Buchungen des Staging-Laufs im Steckbrief eingetragen
- [ ] Vertretung des technischen Owners im Steckbrief benannt
