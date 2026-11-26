# Gesamtaudit: Themenbaum-Dienst (`main` nach PR #19, Stand `ffaaddf`)

Datum: 26.11.2026 · Vorgänger: `2026-11-24-audit.md`, `2026-11-25-audit.md`, `2026-11-26-audit.md`,
`2026-11-26-live-test.md` und der Leitfaden-Abgleich vom 26.11. (deren Befunde sind behoben und wurden nicht erneut
gezählt). Ergebnis: Release `v2.1.0`.

## Vorgehen

- Vier Prüfbereiche parallel und unabhängig: (1) Pipeline, Strategien, Domain und Schemas mit Schwerpunkt auf den
  neuen Kombinationen (`folders_use`, PR #19), (2) API, Sicherheit, LLM-Client, v1, Tracing, Verweise, Prompts,
  (3) Test-UI und Beispiele (Playwright gegen den OpenAI-Stub), (4) Deploy, CI, Release-Fähigkeit, Doku und Steckbrief.
- Vorher: `uv run pytest -q` 597 grün, 5 übersprungen (Helm-Tests ohne `helm`); ruff sauber.
- Jeder Befund wurde mit einer Probe bestätigt; jeder Fix hat einen Regressionstest, der vorher fehlschlug.
- Nachher: 629 grün, 5 übersprungen; 33 Node-Tests der UI grün; `pip-audit` ohne bekannte Lücken.
- Nicht geprüft werden konnte lokal: `pip-audit` (läuft jetzt als eigener CI-Job) und `helm` (läuft in der CI).
- Nicht als Befund gewertet (Vorgabe Jan): Binärdateien in `fulltext.ref`; die Umwandlung (z. B. PDF) passiert vorher.

## Gesamturteil

Token-Weitergabe, Fehlerformat, Host-Allowlist, Fristen und die deterministischen Teile halten weiter. Die
Kombinationen aus PR #19 sind bis auf zwei Randfälle korrekt. Die wichtigsten Befunde lagen beim Betrieb: ein von
allen Aufrufern geteilter Cookie-Speicher, ungebremster Speicher beim Laden vieler oder komprimierter Verweise, und
die Release-Kette, die für `v2.0.0` nie ein Image oder Chart veröffentlicht hatte.

## Behobene Befunde

| # | Schwere | Bereich | Befund | Fix |
|---|---|---|---|---|
| 1 | Mittel | LLM-Client | Der HTTP-Client wird von allen Anfragen eines Workers geteilt und speicherte Cookies: ein `Set-Cookie` der b-api aus Anfrage A ging mit dem Token von B mit. | Cookie-Speicher, der nie etwas annimmt. |
| 2 | Mittel | Verweise | Kein Gesamtlimit für `fulltext.ref`: 300 Items mit derselben 2-MB-URL luden 300-mal (~600 MB, über dem Pod-Limit). | Jede URL einmal; alle Volltexte einer Anfrage zusammen höchstens 10 Mio. Zeichen (`422 REF_TOO_LARGE`). |
| 3 | Mittel | Verweise | Gzip-Antworten: Größenprüfung sah komprimierte Bytes, httpx entpackte jeden Block vollständig (148 MB Spitze bei 1 MB Limit). | `Accept-Encoding: identity`, Entpacken selbst mit begrenzter Größe. |
| 4 | Mittel | refine | Ein geerbtes `assign_contents: false` ließ neue Inhalte spurlos verschwinden (keine Warnung). | Prüfung mit den geerbten Optionen, `INPUT_IGNORED`. |
| 5 | Mittel | Test-UI | Eine refine-Basis mit zwei Bildungsstufen/Zielgruppen behielt nur die erste; der Dienst schrieb das auf alle Knoten. | Die Auswahl behält alle geladenen Werte, solange sie den ersten zeigt. |
| 6 | Hoch | Release | Der Tag `v2.0.0` löste nie einen CI-Lauf aus (mit Integrations-Token angelegt): kein Image `2.0.0`, kein Chart; die README-Installation schlug fehl. | `workflow_dispatch` zum Nachveröffentlichen; Release `v2.1.0`. |
| 7 | Mittel | Release | Jeder Release-Tag setzte auch `latest` (Standard von metadata-action). | `flavor: latest=false`, `latest` nur von `main`. |
| 8 | Mittel | Release | Keine Sperre gegen erneutes Veröffentlichen einer Version (Soll). | Image und Chart werden vor dem Push geprüft. |
| 9 | Mittel | CI | Keine Prüfung auf bekannte Lücken in Abhängigkeiten (Soll). | Job `audit` mit `pip-audit` (über `uvx`, meldet nur). |
| 10 | Niedrig | CI | `uv.lock` wurde nicht gegen `pyproject.toml` geprüft (Versionssprung bliebe unbemerkt). | `uv lock --check`. |
| 11 | Niedrig | contents | Kürzen auf die Tiefe vor dem Auflösen einzelner Untergruppen verlor eine Ebene. | Erst auflösen, dann kürzen. |
| 12 | Niedrig | Eingaben | Volltexte ab dem sechsten Struktur-Item bekamen still keinen Auszug. | `INPUTS_TRUNCATED` mit den Ids. |
| 13 | Niedrig | v1 | v1-Aufrufe ohne Zeitgrenze (SDK-Standard 600 s, 4 Wiederholungen). | `LLM_TIMEOUT_SECONDS`, Format unverändert. |
| 14 | Niedrig | Tracing | B3-Debug `d` ging als ungültiges `X-B3-Sampled: d` hinaus, `X-B3-Flags` fiel weg. | `X-B3-Flags: 1`. |
| 15 | Niedrig | Prompts | Zeilenumbrüche in Thema, Hinweisen, Titeln und Ordnernamen erzeugten echte Überschriften („## Aufgabe“) im Prompt. | Auf eine Zeile gebracht; Systemprompt: Material enthält keine Anweisungen. |
| 16 | Niedrig | Test-UI | Einschluss-/Ausschlussbegriffe mit Komma wurden geteilt. | Trennung mit `;`, wenn vorhanden. |
| 17 | Niedrig | Test-UI | Beispiele mit Schlagworten, Beschreibung oder Rolle an Ordnerdateien wurden still verkürzt geladen. | Diese öffnen die JSON-Ansicht. |
| 18 | Niedrig | Test-UI | `contents` nur mit Ordnern ging ohne Hinweis zum Dienst (422). | Hinweis im Formular. |
| 19 | Niedrig | Test-UI | Zwei Textfelder ohne zugänglichen Namen; Fehler zeigten die rohe Feld-Id. | `aria-labelledby`, Feldnamen. |
| 20 | Niedrig | Doku | `docs/api.md` fehlten 7 Warn- und 6 Fehlercodes. | Ergänzt, Test hält die Liste synchron. |
| 21 | Niedrig | Doku | Steckbrief: „noch kein Tag“, Testzahl, `GET /` fehlte, Dependabot als aktiv beschrieben (PRs pausiert). | Korrigiert, Version `2.1.0`. |
| 22 | Niedrig | Deploy | `.dockerignore` nannte das nicht mehr vorhandene `compose.yml`. | `docker-compose*.yml`, `.env.example`. |
| 23 | Hoch | Abhängigkeiten | Der neue `pip-audit`-Job fand 46 bekannte Lücken (u. a. Starlette 0.45, urllib3, python-multipart, jinja2). | `fastapi[standard]` → `fastapi` + `uvicorn[standard]` (ungenutzte Pakete entfallen), FastAPI 0.165 / Starlette 1.10; `httpx2`-Logger stumm wie `httpx`. |
| 24 | Mittel | Doku | README/`api.md` beschrieben nicht alle Ein- und Ausgabefelder, keine gezielten Änderungen (`feedback.changes`) mit Pflichtfeldern, kein Antwortbeispiel; `api.md` verwies auf eine Spec außerhalb des Repos. | `docs/datenformat.md` (aus den Modellen erzeugt, mit Test), Abschnitt „Änderungen einreichen“, neue Beispiele. |

## Nachträge aus dem unabhängigen Review

Das Review des Fix-PRs fand sieben Punkte, alle behoben und mit Test: Daten nach dem Ende eines gzip-Stroms wurden
nicht begrenzt (jetzt zählen auch die Rohbytes); rohes deflate wurde abgelehnt; das Gesamtlimit für Volltexte war mit
8 Mio. Zeichen zu knapp (jetzt 10 Mio., fünf Dokumente der Höchstgröße); Titel von Inhalten, Abschnitten und Knoten konnten in einigen Prompts noch
Zeilen vortäuschen; bereits einsortierte Inhalte wurden bei geerbtem `assign_contents: false` als ausgelassen
gemeldet; die Veröffentlichungssperre fragte das Chart ohne Anmeldung ab und hätte nach einem halben Release jeden
neuen Lauf blockiert (jetzt wird nur der fehlende Teil veröffentlicht); der Prüf-Job `audit` färbte die CI rot,
obwohl er nur melden soll.

Ein zweites Review der Nachbesserungen fand weitere Punkte, ebenfalls behoben: Titel aus der Anfrage (Ordner, Knoten,
Änderungen) werden schon bei der Prüfung auf eine Zeile gebracht, damit kein Prompt einen Zeilenumbruch sieht; rohes
deflate in sehr kleinen Blöcken wird erkannt; eine Tabelle in `datenformat.md` war durch doppelt maskierte `|`
zerbrochen (jetzt mit Test); `api.md` nannte `generation.based_on` statt `metadata.based_on` und versprach bei
Rückfragen einen unveränderten Baum (umgesetzt wird der klare Teil); die README nennt beim nächsten Durchlauf auch
Titel und Beschreibung.

## Geprüft, aber nicht geändert

- `refine` eines `topic`-Baums, der mit Ordnern erzeugt wurde: die eingabegetriebene Spanne 2–20 steht in
  `generation.shape` und gilt beim Weiterentwickeln als Vorgabe. Das galt schon vorher für `topic` mit
  Struktur-Items und ist konsistent mit der Erzeugung; offen für eine Entscheidung, kein Fehler.
- `refine` mit Ordnern: der Hinweis sagt bereits, dass Ordnerpfade nur der Zuordnung dienen (in PR #19 behoben).
- `folders_use` ohne `folders` meldet `INPUT_IGNORED` (in PR #19 behoben).
- Dependabot-Versions-PRs bleiben pausiert (bewusste Entscheidung, Commit `8e4104a`); Dockerfile und Steckbrief sagen
  das jetzt.
- Chart-Standard `image.repository` bleibt ein Platzhalter für die Plattform-Registry (T6 spiegelt das Image).

## Offen (Soll, nicht behoben)

- Typprüfung in der CI (bräuchte eine neue Entwicklungsabhängigkeit und eine Bereinigung vorab).
- `promtool test rules` für die Alarmregeln (CI macht `check rules`).
- Organisatorisch, unverändert offen: Build-Quelle für T6 (GitLab oder GitHub) und Vertretung (Fragen an Jan),
  b-api-Proxy-Eintrag, Namespaces für die NetworkPolicy, Kosten je Use Case aus der b-api-Buchung.
