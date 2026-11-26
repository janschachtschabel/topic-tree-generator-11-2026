# Operations and handover: `topic-tree` (Themenbaum-Dienst)

> 🇩🇪 Deutsche Fassung: [`../de/betrieb.md`](../de/betrieb.md) · Documentation index: [`../README.md`](../README.md)

This guide is for the platform team (Team 6) and the b-api admin. It covers what it takes to install, set up, monitor,
update and roll back the service, and holds the runbook for every alert. The guide-related facts (master data,
deviations, measurements) are in the [service profile](service-profile.md), the API calls in [`api.md`](api.md), and
every environment variable in the [README](../../README.md#configuration-environment-variables).

## Overview and responsibilities

- **What the service does:** it accepts a JSON request at `POST /v2/topic-tree`, calls a language model through the
  b-api and returns a topic tree as JSON. It stores nothing, has no database, no volume and no CronJobs, and never
  calls the edu-sharing repository.
- **Ports:** `8000` public (API, `/docs`, optionally `/ui/`), `9000` internal (`/health`, `/ready`, `/metrics`).
  Port `9000` must only be reachable inside the cluster.
- **Runtime dependency:** only the b-api (LLM router). Optionally HTTPS downloads from hosts in `REF_ALLOWED_HOSTS`
  (empty by default, so none).
- **Authentication:** behind the b-api the proxy forwards a delegation token (`Authorization: Bearer bdt_…`); the
  service passes it unchanged to the b-api and never stores or logs it. The chart needs no secret for this.

| Task | Owner |
|---|---|
| Build and publish image and chart | the repository's CI (GitHub Actions; whether T6 builds from GitLab is open, see service profile) |
| Installation, values, NetworkPolicy, monitoring | Team 6 |
| Proxy entry `topic-tree` and LLM route `topic-tree-generator` | b-api admin |
| Functional questions, prompts, releases | technical owner (service profile, section 1) |

## Prerequisites

- Kubernetes 1.25 or later (`policy/v1` PodDisruptionBudget, `autoscaling/v2`), Helm 3.
- Optionally the Prometheus Operator (for `ServiceMonitor` and `PrometheusRule`).
- Access to the image `ghcr.io/janschachtschabel/topic-tree-generator-11-2026:<version>` (public, no login) or a
  mirror in the platform registry.
- A b-api with the proxy entry and LLM route from [Setup in the b-api](#setup-in-the-b-api).

## Installation

Production and staging run a fixed version, never `latest`:

```shell
helm upgrade --install topic-tree \
  oci://ghcr.io/janschachtschabel/topic-tree-generator-11-2026/charts/topic-tree \
  --version 2.2.0 \
  --namespace topic-tree --create-namespace \
  -f values-staging.yaml
```

An example `values-staging.yaml`:

```yaml
image:
  repository: registry.example.org/projects/wlo/topic-tree   # platform mirror or the GHCR image
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
    - ports: [{ port: 443, protocol: TCP }]   # b-api (and hosts from refAllowedHosts); narrow with ipBlock/namespaceSelector
serviceMonitor:
  enabled: true
  labels: { release: kube-prometheus-stack }   # label the Prometheus Operator selects by
prometheusRule:
  enabled: true
  labels: { release: kube-prometheus-stack }
```

The namespaces and labels above are placeholders until T6 names them. Every value is explained with `## @param` in
[`values.yaml`](../../deploy/helm/topic-tree/values.yaml). For tests without a cluster there are two Compose files
(README, section *Installation & Docker Setup*).

## Production configuration

- **Service mode:** `config.serviceMode: bapi` (chart default). The service then accepts only calls with a
  delegation token and answers `401` otherwise.
- **LLM target:** `config.bApiRoute: topic-tree-generator` (route at the b-api router). Without route and without
  `bApiModel` every call answers `503 LLM_NOT_CONFIGURED`, and `:9000/ready` reports `not_ready`.
- **Test UI:** `config.uiEnabled: false` (chart default); `/ui/*` then answers `404`.
- **Secrets:** none behind the b-api. Only without the b-api (`standalone`) do `OPENAI_API_KEY` and
  `SERVICE_API_KEYS` belong in a secret named by `secrets.existingSecret`.
- **References (`items_ref`, `fulltext.ref`):** off while `config.refAllowedHosts` is empty. Allowed hosts are only
  loaded over HTTPS on port 443, with `refMaxBytes` (10 MiB) and `refTimeoutSeconds` (20 s) per reference.
- **Cost limits:** callers cannot exceed `maxTreeDepth` (3) and `maxNodesPerLevel` (20).
- **Deadlines:** `requestTimeoutSeconds: 280`; gunicorn stops a worker after 310 s, `terminationGracePeriodSeconds`
  is 300. The proxy in front needs a timeout of at least 310 s.
- **Pod security:** Pod Security `restricted`, no root, only `/tmp` writable, no service account token.
- **Availability:** two pods (`replicaCount: 2`) and a PodDisruptionBudget with `maxUnavailable: 1`, so a drain does
  not stop both pods in the middle of a request.

## Setup in the b-api

By the b-api admin (values from the service profile, section 2):

1. **Proxy entry `topic-tree`** to the service `:8000`: `forwardDelegation: true`, `delegationScopes: ["llm"]`, no
   `forwardApiKey`, `responseTimeout` ≥ `310000` ms, `delegationLifetimeSeconds` ≥ 310,
   `openApiPath: /openapi.json`, `pathToIgnore`: `/`, `/_ping`, `/health`, `/ui/**`, `/docs`, `/redoc`.
   Header allowances: response `Retry-After`, `WWW-Authenticate`; request `b3`, `X-B3-*`, `x-client-trace-id`.
2. **LLM route `topic-tree-generator`** after [`route-topic-tree-generator.json`](../../deploy/b-api/route-topic-tree-generator.json):
   `gpt-6-luna` (tier 0), `gpt-5.6-luna` (tier 1), `maxAttempts: 3`, `clearCache: true`. No GWDG fallback (its quota
   is too low for 8 to 14 parallel calls per tree).
3. **Caller rights:** service right `topic-tree` and LLM right on the key. Without the LLM right the service answers
   `403 FORBIDDEN`.

## Post-install check

```shell
kubectl -n topic-tree rollout status deploy/topic-tree
kubectl -n topic-tree port-forward deploy/topic-tree 9000:9000 8000:8000
curl -s localhost:9000/health    # {"status":"ok","service":"topic-tree","version":"2.2.0","vocab_snapshot":"…"}
curl -s localhost:9000/ready     # {"status":"ready","reason":null}; otherwise reason LLM_NOT_CONFIGURED
curl -s localhost:9000/metrics | grep topic_tree_
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/v2/topic-tree \
  -H 'Content-Type: application/json' -d @docs/examples/topic_minimal.json   # 401: rejected without a token
```

Then a real call through the b-api (`/api/v1/proxy/topic-tree/v2/topic-tree`) with a key that has both rights, for
example with [`docs/examples/topic_minimal.json`](../examples/topic_minimal.json). Expected: `200`, a tree in
`collection`, `warnings` empty or only notes, `metadata.generation.usage.llm_calls` > 0. A call with
[`refine_changes.json`](../examples/refine_changes.json) needs no LLM and answers in under a second. For load and cost
measurements over staging: `scripts/loadtest.py` and `scripts/probe_llm.py`.

## Capacity and scaling

- The service mostly waits on the LLM; CPU and memory stay low (measured ~235 MiB peak per pod with two workers,
  limit 512 Mi).
- Parallel LLM calls = pods × `webConcurrency` × `llmMaxConcurrency`, by default 2 × 2 × 20 = 80. This number has to fit
  the route's quota; on 429 answers from the b-api lower `llmMaxConcurrency` first.
- A 3-level tree needs 8 to 14 LLM calls and 20 to 45 s, under load up to ~110 s (P90). Targeted changes without text
  need no LLM.
- The HPA (`autoscaling.enabled`) scales on CPU and therefore reacts late. For predictable load set a fixed
  `replicaCount`; more pods only help while the route does not throttle.

## Logs, metrics and tracing

- **Logs:** one JSON object per line on stdout with `timestamp`, `level`, `service`, `trace_id`, `span_id`,
  `message`, plus `client_trace_id` when the caller sends `x-client-trace-id`. One line per request with
  `event=request`, `route` (route class), `status`, `duration_ms`. Single LLM calls (`event=llm_call`, `step`,
  `outcome`) are logged only at `LOG_LEVEL=DEBUG`. Tokens, headers, paths and input texts are never logged.
- **Finding errors:** every error answer carries `error.trace_id`; the same `trace_id` is in every log line of the
  request. A `500 INTERNAL` has its stack trace there.
- **Metrics** at `:9000/metrics` (multiprocess, one endpoint per pod):
  `topic_tree_requests_total{route,status}`, `topic_tree_request_seconds{route}`,
  `topic_tree_llm_calls_total{step,outcome}`, `topic_tree_llm_seconds{step}`,
  `topic_tree_llm_tokens_total{kind}` (`prompt`, `cached`, `completion`), `topic_tree_warnings_total{code}`.
  `outcome` is `ok`, `timeout`, `connection`, `deadline` or `http_<status>`.
- **Tracing:** incoming B3 headers (`b3`, `X-B3-*`) are validated and passed on to the b-api; every LLM call is its
  own span. Without B3 the service starts a new trace id.

## Runbook

Every alert links here (`runbook_url`, base set by `prometheusRule.runbookUrl`; the default points to the German
version, whose sections match this one).

### `TopicTreeDown`

Prometheus has reached no pod for 5 minutes (`up == 0` or no target). Check `kubectl get pods`, events and
`kubectl logs --previous` (crash at start, e.g. an invalid environment variable), whether the `ServiceMonitor` has the
labels Prometheus selects by (`serviceMonitor.labels`), and whether the NetworkPolicy lets monitoring reach port
`internal` (`networkPolicy.internalFrom`).

### `TopicTreeServerErrors`

More than 5 % of requests end with 5xx. Break down by `status`: `503` with `LLM_UNAVAILABLE` means the b-api or the
model does not answer (see `TopicTreeLLMErrors`); `503 LLM_NOT_CONFIGURED` means route or model are missing in the
values; `502 LLM_UNAVAILABLE` means the b-api reported a permanent error or the model returned no usable answer; `500 INTERNAL` is a bug in the service: look up the
`trace_id` from the answer in the logs and report it with the stack trace to the owner.

### `TopicTreeLLMErrors`

More than 20 % of LLM calls fail (not counting single callers' 401/403). Break `topic_tree_llm_calls_total` down by
`outcome`: `http_429` = route quota exhausted (lower `llmMaxConcurrency`, raise the quota), `http_5xx` or
`connection` = b-api or provider outage (check b-api status, the route's fallback tier), `timeout` = model too slow
(`llmTimeoutSeconds`, model choice), `http_402` = cost limit. Meanwhile the service returns trees with warnings
(`LLM_DEGRADED`, `DESCRIBE_FAILED`) or `503`.

### `TopicTreeSlowRequests`

The 90th percentile of `/v2/topic-tree` is above 240 s, close to the 280 s deadline. Consequences: answers with
`DEADLINE_EXCEEDED` or cuts at the proxy. Check `topic_tree_llm_seconds` per `step` (slow model?), throttling of the
route, the number of parallel requests. Remedy: more pods only with free quota, otherwise a faster model in the route
or smaller trees on the callers' side.

### `TopicTreeDescribeFailures`

More than 20 description batches per hour failed; trees came back with `DESCRIBE_FAILED` and partly without
descriptions. Usually the same cause as `TopicTreeLLMErrors` on a smaller scale, otherwise invalid model answers
(`outcome=ok`, but warnings): check the route's model. Severity `info`, not an on-call case.

### Common problems without an alert

| Symptom | Cause and remedy |
|---|---|
| `401 UNAUTHORIZED` for every call | call without a delegation token, i.e. not through the b-api, or `forwardDelegation` missing in the proxy entry |
| `403 FORBIDDEN` | the caller's key has no LLM right at the b-api |
| `413 REQUEST_TOO_LARGE` | request larger than `maxRequestBytes` (32 MiB); large sets go through `items_ref` |
| `422 REF_NOT_ALLOWED` | host missing in `refAllowedHosts`, or reference not `https://` on port 443 |
| `504` at the proxy after 60 s or 120 s | `responseTimeout` of the proxy entry or ingress timeout below 310 s |
| warning `DEADLINE_EXCEEDED` | 280 s deadline reached; the tree is incomplete (see `TopicTreeSlowRequests`) |
| same tree for a word-identical request | b-api cache (the service sends no `temperature`); intended, no cost |

## Updates, rollback and releases

- **Update:** `helm upgrade` with a new `--version` and `image.tag`. The service is stateless; a rolling update needs
  no migration. Running requests may finish for up to 290 s.
- **Rollback:** `helm rollback topic-tree <revision>` (revisions: `helm history topic-tree`). There is no data to roll
  back.
- **Compatibility:** `/generate-topic-tree` and `/generate-collection-description` (v1) keep their format; changes to
  `/v2/topic-tree` are in the [CHANGELOG](../../CHANGELOG.md). From the old `0.4.0` to 2.x the proxy entry and route
  change (see [changes overview](changes-v0.4-to-v2.0.md)).
- **Cutting a release** (owner):
  1. Raise the version in `pyproject.toml` and `deploy/helm/topic-tree/Chart.yaml` (`version` and `appVersion`), run
     `uv lock`, write the CHANGELOG section `## X.Y.Z (date)`, update versions in README and docs.
  2. Merge the pull request into `main` with green CI.
  3. Set the tag `vX.Y.Z` on the merge commit in `main` and push it. CI checks tag = version and that the tag is on
     `main`, and publishes image `X.Y.Z`/`X.Y` and chart `X.Y.Z`. A version is never published twice; `latest` only
     comes from `main`.
  4. If the tag triggers no run, start the `ci` workflow with *Run workflow* on the tag (it publishes only what is
     missing).
- **Dependencies:** the CI job `audit` reports known vulnerabilities (`pip-audit`); Dependabot PRs are paused, the base
  images in the `Dockerfile` are pinned by digest and updated by hand.

## Handover checklist for T6

- [ ] Build source decided (GitLab `scm.edu-sharing.com` or GitHub) and synced with `main`
- [ ] Image mirrored into the platform registry or GHCR approved; `image.repository` set
- [ ] Release tag of the version to install exists (image and chart in the registry)
- [ ] Proxy entry `topic-tree` and route `topic-tree-generator` in the b-api (staging, then production)
- [ ] Namespaces for `networkPolicy.publicFrom`/`internalFrom` and egress targets named, `networkPolicy.enabled: true`
- [ ] `serviceMonitor` and `prometheusRule` on with the matching labels; alerts reach the right channel
- [ ] Post-install check passed (section above), one real call through the b-api succeeded
- [ ] Cost per use case from the b-api bookings of the staging run entered in the service profile
- [ ] Deputy of the technical owner named in the service profile
